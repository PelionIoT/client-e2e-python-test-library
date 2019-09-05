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
    parser.addoption('--ext_conn', action='store_true', default=False, help='use external connection')
