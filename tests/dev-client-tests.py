"""
Copyright 2019 ARM Limited
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
from pelion_test_lib.helpers.connect_helper import get_async_device_request, put_async_device_request

logging.basicConfig(format="%(asctime)s:%(name)s:%(threadName)s:%(levelname)s: %(message)s")
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

PATTERN = '1:2:3:4'
PATTERN2 = '500:500:500:500'
RESOURCE_PATH = '/3201/0/5853'


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
                                                    expected_status_code=202)
    log.info('Set subscription for resource "/3201/0/5853". Async-id: "{}"'.format(r.json()['async-response-id']))

    async_id = put_async_device_request(cloud, RESOURCE_PATH, client.endpoint_id(), PATTERN2, headers)
    log.info('Put value "{}" to resource "{}". Async-id: "{}"'.format(PATTERN2, RESOURCE_PATH, async_id))
    websocket.wait_for_notification(client.endpoint_id(), RESOURCE_PATH, PATTERN2, timeout=180, assert_errors=True)
