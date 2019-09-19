"""
Copyright 2017 ARM Limited
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

import pytest

pytest_plugins = ['pelion_test_lib.fixtures.client_fixtures',
                  'pelion_test_lib.fixtures.cloud_fixtures']


def pytest_addoption(parser):
    """
    Function to enable pytest commandline arguments
    :param parser: argparser
    :return:
    """
    parser.addoption('--target_id', action='store', help='mbed device target id')
    parser.addoption('--update_bin', action='store', help='mbed device update binary')
