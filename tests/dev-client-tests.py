"""
Copyright 2019-2020 ARM Limited
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import logging
import pytest
from pelion_test_lib.helpers.connect_helper import get_async_device_request, put_async_device_request, \
    post_async_device_request, device_resource_exists
from pelion_test_lib.helpers.update_helper import wait_for_campaign_device_state, wait_for_campaign_state
from pelion_test_lib.tools.utils import get_bootstrap_time_and_execution_mode

log = logging.getLogger(__name__)

PATTERN = '1:2:3:4'
PATTERN2 = '500:500:500:500'
RESOURCE_PATH = '/3201/0/5853'
REBOOT_PATH = '/3/0/4'
FACTORY_RESET_PATH = '/3/0/5'


def test_01_get_device_id(cloud, client):
    log.info('Device registered to cloud with device ID: {}'.format(client.endpoint_id()))
    cloud.device_directory.get_device(client.endpoint_id(), expected_status_code=200)


def test_02_put_resource(cloud, client, websocket, temp_api_key):
    headers = {'Authorization': 'Bearer {}'.format(temp_api_key['key'])}
    async_id = put_async_device_request(cloud, RESOURCE_PATH, client.endpoint_id(), PATTERN, headers)
    log.info('Put value "{}" to resource "{}". Async-id: "{}"'.format(PATTERN, RESOURCE_PATH, async_id))

    async_response = websocket.wait_for_async_response(async_response_id=async_id, timeout=180, assert_errors=True)
    assert async_response['decoded_payload'] == b'', 'Invalid payload received from the device!'


def test_03_get_resource(cloud, client, websocket, temp_api_key):
    headers = {'Authorization': 'Bearer {}'.format(temp_api_key['key'])}
    async_id = get_async_device_request(cloud, RESOURCE_PATH, client.endpoint_id(), headers)
    log.info('Get value from resource "{}". Async-id: "{}"'.format(RESOURCE_PATH, async_id))

    async_response = websocket.wait_for_async_response(async_response_id=async_id, timeout=180, assert_errors=True)
    assert async_response['decoded_payload'] == PATTERN.encode('ascii'), 'Invalid payload received from the device!'


def test_04_subscribe_resource(cloud, client, websocket, temp_api_key):
    headers = {'Authorization': 'Bearer {}'.format(temp_api_key['key'])}
    r = cloud.connect.set_subscription_for_resource(client.endpoint_id(), '3201/0/5853', headers,
                                                    expected_status_code=[200, 202])
    if r.status_code == 202:
        async_id = r.json()['async-response-id']
        log.info('Set subscription for resource "/3201/0/5853". Async-id: "{}"'.format(async_id))
        async_response = websocket.wait_for_async_response(async_response_id=async_id, timeout=180, assert_errors=True)
        assert async_response['status'] == 200, 'Invalid subscription status received from the device!'

    cloud.connect.get_subscription_status(client.endpoint_id(), '3201/0/5853', headers, expected_status_code=200)

    async_id = put_async_device_request(cloud, RESOURCE_PATH, client.endpoint_id(), PATTERN2, headers)
    log.info('Put value "{}" to resource "{}". Async-id: "{}"'.format(PATTERN2, RESOURCE_PATH, async_id))
    websocket.wait_for_notification(client.endpoint_id(), RESOURCE_PATH, PATTERN2, timeout=180, assert_errors=True)


def test_05_factory_reset(cloud, client, websocket, temp_api_key):
    headers = {'Authorization': 'Bearer {}'.format(temp_api_key['key'])}
    endpoint_id = client.endpoint_id()

    # store bootstrap time and execution mode
    bootstrap_time, is_developer_device = get_bootstrap_time_and_execution_mode(cloud, endpoint_id, headers)

    # send factory reset
    if device_resource_exists(cloud, FACTORY_RESET_PATH, endpoint_id, headers):
        async_id = post_async_device_request(cloud, FACTORY_RESET_PATH, endpoint_id, headers)
        async_response = websocket.wait_for_async_response(async_response_id=async_id, timeout=180, assert_errors=True)
        assert async_response['decoded_payload'] == b'', 'Invalid payload received from the device!'
    else:
        skip_msg = 'TEST SKIPPED - client might not have "{}" resource for factory reset'.format(FACTORY_RESET_PATH)
        log.warning(skip_msg)
        pytest.skip(skip_msg)

    # send reboot
    async_id = post_async_device_request(cloud, REBOOT_PATH, endpoint_id, headers)
    async_response = websocket.wait_for_async_response(async_response_id=async_id, timeout=180, assert_errors=True)
    assert async_response['decoded_payload'] == b'', 'Invalid payload received from the device!'

    # wait for new device id and check if it changed
    # (it should change in developer mode, but should not in factory mode)
    new_id = client.wait_for_output('Device ID: ', timeout=900)
    new_id = new_id.split()[2]
    if is_developer_device:
        assert endpoint_id != new_id
        client._ep_id = new_id  # update device id for tests running after this one
    else:
        assert endpoint_id == new_id

    # check that bootstrap time is bigger now since factory reset should result in re-bootstrapping
    new_bootstrap_time, _ = get_bootstrap_time_and_execution_mode(cloud, new_id, headers)
    assert new_bootstrap_time > bootstrap_time, 'New bootstrap time not bigger than old'


def test_06_update_device(cloud, client, update_device):
    campaign_id = update_device
    client.wait_for_output('New active firmware is valid', timeout=900)
    client_id = client.endpoint_id(120)
    wait_for_campaign_state(cloud, campaign_id)
    wait_for_campaign_device_state(cloud, campaign_id, client_id)
