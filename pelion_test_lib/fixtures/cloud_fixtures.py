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
import os
from time import sleep
from pelion_test_lib.cloud.cloud import PelionCloud
import pelion_test_lib.helpers.websocket_handler as websocket_handler
import pytest

log = logging.getLogger(__name__)


@pytest.fixture(scope='module')
def cloud():
    """
    Fixture for Pelion cloud
    Initializes the rest api with the api key given in config
    :return: Cloud API object
    """
    log.debug("Initializing Cloud API fixture")

    api_gw = os.environ.get('PELION_CLOUD_API_GW', 'https://api.us-east-1.mbedcloud.com')
    if os.environ.get('CLOUD_SDK_API_KEY'):
        api_key = os.environ.get('CLOUD_SDK_API_KEY')
    else:
        api_key = os.environ.get('PELION_CLOUD_API_KEY')

    if not api_gw or not api_key:
        pytest.exit('Set missing API gateway url and/or API key via environment variables before running tests!\n'
                    'API GW: PELION_CLOUD_API_GW={}\n'
                    'API KEY: CLOUD_SDK_API_KEY={} or '
                    'PELION_CLOUD_API_KEY={}'.format(os.environ.get('PELION_CLOUD_API_GW', 'MISSING!'),
                                                     os.environ.get('CLOUD_SDK_API_KEY', 'MISSING!'),
                                                     os.environ.get('PELION_CLOUD_API_KEY', 'MISSING!')))

    cloud_api = PelionCloud(api_gw, api_key)

    payload = {'name': 'pelion_e2e_dynamic_api_key'}
    r = cloud_api.account.create_api_key(payload, expected_status_code=201)
    resp = r.json()
    cloud_api.rest_api.set_default_api_key(resp['key'])

    yield cloud_api

    log.debug('Cleaning out the Cloud API fixture')
    headers = {'Authorization': 'Bearer {}'.format(api_key)}
    cloud_api.account.delete_api_key(resp['id'], headers=headers, expected_status_code=204)


@pytest.fixture(scope='module')
def temp_api_key(cloud):
    """
    Create new temporary function level developer api key
    :param cloud: Cloud API fixture
    :return: Rest API response for new developer api key
    """
    payload = {'name': 'pelion_e2e_dynamic_api_key'}
    r = cloud.account.create_api_key(payload, expected_status_code=201)
    resp = r.json()

    log.info('Created new developer api key for test case, id: {}'.format(resp['id']))

    yield resp

    log.info('Cleaning out the generated test case developer api key, id: {}'.format(resp['id']))
    cloud.account.delete_api_key(resp['id'], expected_status_code=204)


@pytest.fixture(scope='module')
def websocket(cloud, temp_api_key):
    log.info('Register and open WebSocket notification channel')
    headers = {'Authorization': 'Bearer {}'.format(temp_api_key['key'])}
    cloud.connect.register_websocket_channel(headers=headers, expected_status_code=[200, 201])
    sleep(5)
    # Get host part from api address
    host = cloud.api_gw.split('//')[1]

    log.info('Opening WebSocket handler')
    ws = websocket_handler.WebSocketRunner('wss://{}/v2/notification/websocket-connect'.format(host),
                                           temp_api_key['key'])
    handler = websocket_handler.WebSocketHandler(ws)
    yield handler

    ws.close()
    sleep(2)
    log.info('Deleting WebSocket channel')
    cloud.connect.delete_websocket_channel(headers=headers, expected_status_code=204)
