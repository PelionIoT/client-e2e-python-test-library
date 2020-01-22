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

from datetime import datetime
import logging
import os
import random
import re
import string
import mbed_lstools

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


def get_bootstrap_time_and_execution_mode(cloud_api, endpoint_id, headers):
    """
    Query Device directory for latest bootstrap time and execution mode (whether device
    is developer or production device) of a device.
    https://www.pelion.com/docs/device-management/current/service-api-references/device-directory.html#DeviceData
    :param cloud_api: Cloud api object to be used in the query
    :param endpoint_id: endpoint to be queried
    :param headers: headers to be added to the device query
    :return: A tuple with latest bootstrap timestamp as datetime and True/False
             whether the queried device is developer device or not
    """
    response = cloud_api.device_directory.get_device(endpoint_id, headers)
    assert_status(response, 'get_bootstrap_time_and_execution_mode', 200)
    response = response.json()
    assert 'bootstrapped_timestamp' in response, 'Missing bootstrap time in device directory'
    assert 'device_execution_mode' in response, 'Missing device execution mode in device directory'
    bootstrap_time = datetime.strptime(response['bootstrapped_timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')
    is_developer_device = response['device_execution_mode'] == 1
    return bootstrap_time, is_developer_device


def assert_status(response, func, expected_resp):
    """
    Function for asserting response and creating proper msg on fail situation
    :param response: Rest API response
    :param func: Calling function
    :param expected_resp: Expected response or list of expected responses
    :return: Nothing
    """
    if _assert_status(expected_resp, response) is False:
        error_msg = 'ERROR: {} failed!\n' \
                    'Expected result {} -> actual response was: {}\n\n' \
                    'Response body: {}\n\n' \
                    'Response headers: {}'.format(func,
                                                  expected_resp,
                                                  response.status_code,
                                                  response.text,
                                                  response.headers)
        log.error(error_msg)
        assert False, error_msg


def _assert_status(expected_resp, response):
    if isinstance(expected_resp, list):
        return response.status_code in expected_resp
    return response.status_code == expected_resp


def build_random_string(str_length, use_digits=False, use_punctuations=False):
    r"""
    Create random string
    :param str_length: String length
    :param use_digits: Takes string.digits as well
    :param use_punctuations: Takes string.punctuation without \, ", '
    :return: Random string
    """
    letters = string.ascii_letters
    if use_digits:
        letters = letters + string.digits
    if use_punctuations:
        letters = letters + string.punctuation.replace(" ", "").replace("\\", "").replace("\"", "").replace("\'", "")
    return ''.join(random.choice(letters) for c in range(str_length))


def strip_escape(string_to_escape):
    """
    Strip escape characters from string.
    :param string_to_escape: string to work on
    :return: stripped string
    """
    raw_ansi_pattern = r'\033\[((?:\d|;)*)([a-zA-Z])'
    ansi_pattern = raw_ansi_pattern.encode()
    ansi_eng = re.compile(ansi_pattern)
    matches = []
    for match in ansi_eng.finditer(string_to_escape):
        matches.append(match)
    matches.reverse()
    for match in matches:
        start = match.start()
        end = match.end()
        string_to_escape = string_to_escape[0:start] + string_to_escape[end:]
    return string_to_escape


def get_serial_port_for_mbed(target_id):
    """
    Gets serial port address for the device with Mbed LS tool
    :param target_id: mbed device target_id
    :return: Serial port address
    """
    selected_mbed = None
    mbeds = mbed_lstools.create()
    mbed_devices = mbeds.list_mbeds(unique_names=True)
    if target_id:
        for dev in mbed_devices:
            if dev['target_id'] == target_id:
                selected_mbed = dev
                break
    else:
        if mbed_devices:
            log.debug('Found {} mbed device(s), taking the first one for test - '
                      'give "--target_id" argument to get specific device'.format(len(mbed_devices)))
            selected_mbed = mbed_devices[0]

    if selected_mbed:
        log.info('Using "{}: {}" device at "{}" port for tests'.format(selected_mbed['platform_name_unique'],
                                                                       selected_mbed['target_id'],
                                                                       selected_mbed['serial_port']))
        return selected_mbed['serial_port']
    log.error('Could not find any mbed devices, please make sure you have connected one with power on')
    return None


def get_path(path):
    if 'WORKSPACE' in os.environ:
        log.debug('$WORKSPACE: {}'.format(os.environ['WORKSPACE']))
        p = os.path.join(os.sep, os.environ['WORKSPACE'], path)
        return p
    return path
