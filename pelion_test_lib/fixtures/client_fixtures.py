import logging
from time import sleep
import pytest
from pelion_test_lib.tools.client_runner import Client
from pelion_test_lib.tools.serial_conn import SerialConnection
from pelion_test_lib.tools.utils import get_serial_port_for_mbed

log = logging.getLogger(__name__)


@pytest.fixture(scope='module')
def client(request):
    """
    Initializes and starts up the cloud client.
    :return: Running client instance
    """
    address = get_serial_port_for_mbed(request.config.getoption('target_id'))
    if address:
        conn = SerialConnection(address, 115200)
    else:
        err_msg = 'No serial connection to open for test device'
        log.error(err_msg)
        assert False, err_msg
    sleep(2)
    ser_cli = Client(conn)
    ser_cli.wait_for_output(b'Client registered', 300)
    ep_id = ser_cli.endpoint_id(120)

    yield ser_cli

    log.info('Closing client "{}"'.format(ep_id))
    sleep(2)
    ser_cli.kill()
    conn.close()
