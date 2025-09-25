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

from datetime import datetime
import logging
import os
import random
import re
import string
import mbed_lstools
import serial.tools.list_ports

log = logging.getLogger(__name__)


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
    assert_status(response, "get_bootstrap_time_and_execution_mode", 200)
    response = response.json()
    assert (
        "bootstrapped_timestamp" in response
    ), "Missing bootstrap time in device directory"
    assert (
        "device_execution_mode" in response
    ), "Missing device execution mode in device directory"
    bootstrap_time = datetime.strptime(
        response["bootstrapped_timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    is_developer_device = response["device_execution_mode"] == 1
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
        error_msg = (
            "ERROR: {} failed!\n"
            "Expected result {} -> actual response was: {}\n\n"
            "Response body: {}\n\n"
            "Response headers: {}".format(
                func,
                expected_resp,
                response.status_code,
                response.text,
                response.headers,
            )
        )
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
        letters = letters + string.punctuation.replace(" ", "").replace(
            "\\", ""
        ).replace('"', "").replace("'", "")
    return "".join(random.choice(letters) for c in range(str_length))


def strip_escape(string_to_escape):
    """
    Strip escape characters from string.
    :param string_to_escape: string to work on
    :return: stripped string
    """
    raw_ansi_pattern = r"\033\[((?:\d|;)*)([a-zA-Z])"
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
            if dev["target_id"] == target_id:
                selected_mbed = dev
                break
    else:
        if mbed_devices:
            log.debug(
                "Found {} mbed device(s), taking the first one for test - "
                'give "--target_id" argument to get specific device'.format(
                    len(mbed_devices)
                )
            )
            selected_mbed = mbed_devices[0]

    if selected_mbed:
        log.info(
            'Using "{}: {}" device at "{}" port for tests'.format(
                selected_mbed["platform_name_unique"],
                selected_mbed["target_id"],
                selected_mbed["serial_port"],
            )
        )
        return selected_mbed["serial_port"]
    log.error(
        "Could not find any mbed devices, please make sure you have connected one with power on"
    )
    return None


def get_serial_port_for_pyocd(target_id):
    """
    Gets serial port address for the device using pyocd for device discovery
    Falls back to mbed-ls if pyocd is not available or fails
    :param target_id: device target_id (can be pyocd board ID or mbed target_id)
    :return: Serial port address
    """
    try:
        from pyocd.core.helpers import ConnectHelper

        log.debug("Attempting to discover devices using pyocd")

        # Try to create a session with pyocd
        session = ConnectHelper.session_with_chosen_probe()

        if session is None:
            log.warning("No devices found with pyocd, falling back to mbed-ls")
            return get_serial_port_for_mbed(target_id)

        # Get the probe from the session
        probe = session.probe
        if probe:
            # Map pyocd probe to serial port
            serial_port = _map_pyocd_probe_to_serial_port(probe)
            if serial_port:
                log.info(
                    'Using pyocd-discovered device "{}" at "{}" port for tests'.format(
                        getattr(probe, 'unique_id', 'Unknown'),
                        serial_port
                    )
                )
                session.close()
                return serial_port
            else:
                log.warning("Could not map pyocd probe to serial port, falling back to mbed-ls")
                session.close()
                return get_serial_port_for_mbed(target_id)
        else:
            log.warning("No probe found in pyocd session, falling back to mbed-ls")
            session.close()
            return get_serial_port_for_mbed(target_id)

    except ImportError:
        log.debug("pyocd not available, falling back to mbed-ls")
        return get_serial_port_for_mbed(target_id)
    except Exception as e:
        log.warning("pyocd device discovery failed: {}, falling back to mbed-ls".format(e))
        return get_serial_port_for_mbed(target_id)


def _map_pyocd_probe_to_serial_port(probe):
    """
    Maps a pyocd probe to its corresponding serial port
    :param probe: pyocd probe object
    :return: Serial port path or None if not found
    """
    try:
        # Get all available serial ports
        ports = serial.tools.list_ports.comports()

        # Try to match based on USB VID/PID if available
        if hasattr(probe, 'vid') and hasattr(probe, 'pid'):
            target_vid = probe.vid
            target_pid = probe.pid

            for port in ports:
                if port.vid == target_vid and port.pid == target_pid:
                    log.debug("Matched pyocd probe to serial port {} by VID/PID".format(port.device))
                    return port.device

        # Prioritize USB serial ports over system serial ports
        # Common patterns for ARM development boards (in order of preference)
        arm_patterns = [
            'ttyACM',      # Linux USB CDC-ACM (most common for ARM boards)
            'ttyUSB',      # Linux USB serial
            'cu.usbmodem', # macOS USB
            'COM',         # Windows
        ]

        # First pass: look for USB serial ports
        for port in ports:
            port_name = port.device.lower()
            for pattern in arm_patterns:
                if pattern in port_name:
                    log.debug("Matched pyocd probe to USB serial port {} by name pattern".format(port.device))
                    return port.device

        # Second pass: exclude system serial ports and use first available USB port
        usb_ports = []
        for port in ports:
            port_name = port.device.lower()
            # Skip system serial ports (ttyS*) and virtual ports
            if not any(skip in port_name for skip in ['ttys', 'pts', 'ttyprintk']):
                usb_ports.append(port)

        if usb_ports:
            log.debug("Using first available USB serial port {} for pyocd probe".format(usb_ports[0].device))
            return usb_ports[0].device

        # Last resort: return None to fall back to mbed-ls
        log.debug("No suitable USB serial port found for pyocd probe")
        return None

    except Exception as e:
        log.debug("Error mapping pyocd probe to serial port: {}".format(e))

    return None


def get_path(path):
    if "WORKSPACE" in os.environ:
        log.debug("$WORKSPACE: {}".format(os.environ["WORKSPACE"]))
        p = os.path.join(os.sep, os.environ["WORKSPACE"], path)
        return p
    return path


def remove_first_slash_from(resource_path):
    """
    Some REST API calls are written to have resource path without the '/' in the beginning, so this removes it
    :param resource_path: e.g. /1/0/1
    :return: Resource path without the first '/'
    """
    if resource_path[0] == "/":
        return resource_path[1:]
    return resource_path
