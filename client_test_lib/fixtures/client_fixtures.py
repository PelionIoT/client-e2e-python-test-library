# pylint: disable=redefined-outer-name
"""
Copyright 2019-2020 Pelion.
Copyright (c) 2023 Izuma Networks

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
from time import sleep
import pytest
from client_test_lib.tools.client_runner import Client
from client_test_lib.tools.external_conn import ExternalConnection
from client_test_lib.tools.local_conn import LocalConnection
from client_test_lib.tools.serial_conn import SerialConnection
from client_test_lib.tools.utils import get_serial_port_for_mbed

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def client_internal(request):
    """
    Initializes and starts up the cloud client.
    :return: Running client instance
    """
    if request.config.getoption("ext_conn"):
        log.info("Using external connection")
        conn = ExternalConnection()
        sleep(2)
    elif request.config.getoption("local_binary"):
        log.info("Using local binary process")
        conn = LocalConnection(request.config.getoption("local_binary"))
    else:
        address = get_serial_port_for_mbed(
            request.config.getoption("target_id")
        )
        if address:
            conn = SerialConnection(address, 115200)
        else:
            err_msg = "No serial connection to open for test device"
            log.error(err_msg)
            assert False, err_msg

    cli = Client(conn)

    # reset the serial connection device
    if not request.config.getoption(
        "ext_conn"
    ) and not request.config.getoption("local_binary"):
        cli.reset()

    cli.wait_for_output("Client registered", 300)
    ep_id = cli.endpoint_id(120)

    yield cli

    log.info('Closing client "{}"'.format(ep_id))
    cli.kill()
    conn.close()
    sleep(2)


@pytest.fixture(scope="function")
def client(client_internal):
    """
    Makes sure client output from previous test doesn't
    interfere with current test
    :return: Running client instance
    """
    client_internal.clear_input()
    return client_internal
