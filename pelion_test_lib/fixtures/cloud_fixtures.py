# pylint: disable=redefined-outer-name
"""
Copyright 2019-2020 Pelion.
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
import pytest
from pelion_test_lib.cloud.cloud import PelionCloud
from pelion_test_lib.helpers.update_helper import wait_for_campaign_phase
import pelion_test_lib.helpers.websocket_handler as websocket_handler
import pelion_test_lib.tools.manifest_tool as manifest_tool
from pelion_test_lib.tools.utils import build_random_string

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

    yield cloud_api


@pytest.fixture(scope='module')
def api_key(cloud, request):
    """
    Create new temporary module level developer API key
    When running testset with 'use_one_apikey' argument this doesn't create new one but returns current API key!
    :param cloud: Cloud fixture
    :return: API key
    """
    use_current = request.config.getoption('use_one_apikey', False)
    temp_key_id = None

    payload = {'name': 'pelion_e2e_dynamic_api_key'}
    if use_current:
        log.info('Using current API key, not creating temporary one')
        key = cloud.rest_api.api_key
    else:
        log.info('Creating new developer API key')
        r = cloud.account.create_api_key(payload, expected_status_code=201)
        resp = r.json()
        key = resp['key']
        temp_key_id = resp['id']
        log.info('Created new developer API key for the test run, ID: {}'.format(temp_key_id))

    yield key

    if temp_key_id:
        log.info('Cleaning out the generated test set developer API key, ID: {}'.format(temp_key_id))
        cloud.account.delete_api_key(temp_key_id, expected_status_code=204)


@pytest.fixture(scope='module')
def websocket(cloud, api_key):
    log.info('Register and open WebSocket notification channel')
    headers = {'Authorization': 'Bearer {}'.format(api_key)}
    cloud.connect.register_websocket_channel(headers=headers, expected_status_code=[200, 201])
    sleep(5)
    # Get host part from api address
    host = cloud.api_gw.split('//')[1]

    log.info('Opening WebSocket handler')
    ws = websocket_handler.WebSocketRunner('wss://{}/v2/notification/websocket-connect'.format(host), api_key)
    handler = websocket_handler.WebSocketHandler(ws)
    yield handler

    ws.close()
    sleep(2)
    log.info('Deleting WebSocket channel')
    cloud.connect.delete_websocket_channel(headers=headers, expected_status_code=204)


@pytest.fixture(scope='function')
def update_device(cloud, client, request):
    """
    Fixture for updating device.
    This uploads firmware image, creates manifest, uploads manifest, and creates and starts the update campaign.
    :param cloud: Cloud fixture
    :param client: Client fixture
    :param request: Requests fixture
    :return: Campaign ID
    """
    binary_path = request.config.getoption('update_bin', None)
    manifest_tool_path = request.config.getoption('manifest_tool')
    manifest_version = request.config.getoption('manifest_version', 'v3')
    no_cleanup = request.config.getoption('no_cleanup', False)
    delta_manifest = request.config.getoption('delta_manifest', None)
    local_bin = request.config.getoption('local_binary', None)
    
    if local_bin:
        skip_msg = 'Update test is not supported when using local linux binary!'
        log.info(skip_msg)
        pytest.skip(skip_msg)

    log.info('Update image: "{}"'.format(binary_path))
    log.info('Path for manifest-tool init: "{}"'.format(manifest_tool_path))
    if not binary_path:
        skip_msg = 'Provide missing binary image in startup arguments to run update case\n' \
                   '--update_bin={}'.format(binary_path if binary_path else 'MISSING!')
        log.warning(skip_msg)
        pytest.skip(skip_msg)

    sleep(5)
    resp = cloud.device_directory.get_device(client.endpoint_id(), expected_status_code=200).json()
    assert resp['state'] == 'registered'

    fw_image = cloud.update.upload_firmware_image(binary_path, expected_status_code=201).json()
    fw_image_id = fw_image['id']
    log.info('Firmware image uploaded! Image ID: {}'.format(fw_image_id))

    if not manifest_version:
        manifest_version = 'v3'
    manifest_file = manifest_tool.create_manifest(path=manifest_tool_path,
                                                  firmware_url=fw_image['datafile'],
                                                  update_image_path=binary_path,
                                                  delta_manifest=delta_manifest,
                                                  manifest_version=manifest_version)
    assert manifest_file is not None, 'Manifest file was not created'

    manifest = cloud.update.upload_firmware_manifest(manifest_file, expected_status_code=201).json()
    manifest_id = manifest['id']
    log.info('Firmware manifest uploaded! Manifest ID: {}'.format(manifest_id))

    campaign_name = 'pelion_e2e_update_test_{}'.format(build_random_string(8, True))
    campaign_data = {'name': campaign_name,
                     'device_filter': 'id__eq={}'.format(client.endpoint_id()),
                     'root_manifest_id': manifest['id']}

    campaign = cloud.update.create_update_campaign(campaign_data, expected_status_code=201).json()
    campaign_id = campaign['id']
    assert campaign['phase'] == 'draft'
    log.info('Update campaign created! Campaign ID: {}'.format(campaign_id))

    cloud.update.start_update_campaign(campaign['id'], expected_status_code=202)
    log.info('Update campaign started! Campaign ID: {}'.format(campaign_id))

    yield campaign_id

    if not no_cleanup:
        if campaign_id:
            cloud.update.stop_update_campaign(campaign_id, expected_status_code=[202, 409])
            wait_for_campaign_phase(cloud, campaign_id, ['draft', 'stopped', 'archived'])
            log.info('Deleting update campaign. ID: {}'.format(campaign_id))
            cloud.update.delete_update_campaign(campaign_id, expected_status_code=204)
        if fw_image_id:
            log.info('Deleting firmware image. ID: {}'.format(fw_image_id))
            cloud.update.delete_firmware_image(fw_image_id, expected_status_code=204)
        if manifest_id:
            log.info('Deleting firmware manifest. ID: {}'.format(manifest_id))
            cloud.update.delete_firmware_manifest(manifest_id, expected_status_code=204)


@pytest.fixture(scope='function')
def update_campaign(cloud, request):
    """
    Fixture for running update campaign for multiple devices.
    :param cloud: Cloud fixture
    :param request: Request fixture
    :return: Campaign ID
    """
    campaign_id = None
    fw_image_id = None
    manifest_id = None

    binary_path = request.config.getoption('update_bin', None)
    log.info('Update image: "{}"'.format(binary_path))

    if request.config.getoption('local_binary', None):
        skip_msg = 'Update test is not supported when using local linux binary!'
        log.info(skip_msg)
        pytest.skip(skip_msg)
    if not binary_path:
        skip_msg = 'Provide missing binary image in startup arguments to run update case\n' \
                   '--update_bin={}'.format(binary_path if binary_path else 'MISSING!')
        log.warning(skip_msg)
        pytest.skip(skip_msg)

    def create_campaign(device_filter):
        nonlocal campaign_id
        nonlocal fw_image_id
        nonlocal manifest_id

        fw_image = cloud.update.upload_firmware_image(binary_path, expected_status_code=201).json()
        fw_image_id = fw_image['id']
        log.info('Firmware image uploaded! Image ID: {}'.format(fw_image_id))

        manifest_tool_path = request.config.getoption('manifest_tool')
        log.info('Path for manifest-tool init: "{}"'.format(manifest_tool_path))

        delta_manifest = request.config.getoption('delta_manifest', None)
        manifest_file = manifest_tool.create_manifest(path=manifest_tool_path,
                                                      firmware_url=fw_image['datafile'],
                                                      update_image_path=binary_path,
                                                      delta_manifest=delta_manifest)
        assert manifest_file is not None, 'Manifest file was not created'

        manifest = cloud.update.upload_firmware_manifest(manifest_file, expected_status_code=201).json()
        manifest_id = manifest['id']
        log.info('Firmware manifest uploaded! Manifest ID: {}'.format(manifest_id))

        campaign_name = 'pelion_e2e_update_test_{}'.format(build_random_string(8, True))
        campaign_data = {'name': campaign_name,
                         'device_filter': device_filter,
                         'root_manifest_id': manifest['id']}

        campaign = cloud.update.create_update_campaign(campaign_data, expected_status_code=201).json()
        campaign_id = campaign['id']
        assert campaign['phase'] == 'draft'
        log.info('Update campaign created! Campaign ID: {}'.format(campaign_id))

        cloud.update.start_update_campaign(campaign['id'], expected_status_code=202)
        log.info('Update campaign started! Campaign ID: {}'.format(campaign_id))

        return campaign_id

    yield create_campaign

    if not request.config.getoption('no_cleanup', False):
        if campaign_id:
            cloud.update.stop_update_campaign(campaign_id, expected_status_code=[202, 409])
            wait_for_campaign_phase(cloud, campaign_id, ['draft', 'stopped', 'archived'])
            log.info('Deleting update campaign. ID: {}'.format(campaign_id))
            cloud.update.delete_update_campaign(campaign_id, expected_status_code=204)
        if fw_image_id:
            log.info('Deleting firmware image. ID: {}'.format(fw_image_id))
            cloud.update.delete_firmware_image(fw_image_id, expected_status_code=204)
        if manifest_id:
            log.info('Deleting firmware manifest. ID: {}'.format(manifest_id))
            cloud.update.delete_firmware_manifest(manifest_id, expected_status_code=204)
