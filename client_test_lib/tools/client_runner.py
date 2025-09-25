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

from copy import deepcopy
import logging
import queue
import threading
from time import time
import client_test_lib.tools.utils as utils

flog = logging.getLogger("ClientRunner")
flog.setLevel(logging.DEBUG)
fh = logging.FileHandler("client.log")
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s:%(name)s:%(threadName)s:%(levelname)s: %(message)s"
)
fh.setFormatter(formatter)
flog.addHandler(fh)

log = logging.getLogger(__name__)


class Client:
    """
    Client runner class that handles communication for given dut object
    :param dut: Running client object
    :param trace: Log the raw client output
    :param name: Logging name for the client
    :param filter_debug: Filter out debug messages to reduce log noise (default: True)
    """

    def __init__(self, dut, trace=False, name="0", filter_debug=True):
        self._ep_id = None
        self.name = name
        self.trace = trace
        self.filter_debug = filter_debug
        self.run = True
        self.iq = queue.Queue()
        self.dut = dut

        input_thread_name = "<-- D{}".format(name)
        it = threading.Thread(
            target=self._input_thread, name=input_thread_name
        )
        it.setDaemon(True)
        log.info('Starting runner threads for client "D{}"'.format(self.name))
        it.start()

    def _input_thread(self):
        """
        Runner's input thread
        """
        while self.run:
            line = self.dut.readline()
            if line:
                plain_line = self._parse_serial_line(line)
                if plain_line:  # Only process non-empty lines
                    flog.info("<--|D{}| {}".format(self.name, plain_line.strip()))
                    if self.trace:
                        log.debug("Raw output: {}".format(line))
                    self._check_for_errors(line, plain_line)
                    self.iq.put(plain_line)
            else:
                pass

    def _parse_serial_line(self, line):
        """
        Parse serial line to extract clean content
        :param line: Raw serial line bytes
        :return: Cleaned string or None if line should be ignored
        """
        if not line or line == b'':
            return None

        # Strip escape sequences first
        plain_line = utils.strip_escape(line)

        # Handle multiple carriage returns and newlines
        # Split on \r\n or \r\r\n patterns and take the last meaningful part
        if b"\r" in plain_line:
            # Split on carriage returns and filter out empty parts
            parts = plain_line.split(b"\r")
            # Find the last non-empty part that contains actual content
            for part in reversed(parts):
                if part.strip() and not part.startswith(b"\n"):
                    plain_line = part
                    break

        # Remove leading/trailing newlines and whitespace
        plain_line = plain_line.strip(b"\n\r\t ")

        # Skip empty lines
        if not plain_line:
            return None

        # Convert tabs to spaces and decode to string
        plain_line = plain_line.replace(b"\t", b"  ").decode("utf-8", "replace")

        # Skip lines that are just whitespace or control characters
        if not plain_line.strip():
            return None

        # Filter debug output if enabled
        if self.filter_debug and self._is_debug_line(plain_line):
            return None

        return plain_line

    def _is_debug_line(self, line):
        """
        Check if a line is debug output that should be filtered
        :param line: Parsed line string
        :return: True if line should be filtered out
        """
        line_lower = line.lower().strip()

        # log.info("Checking if line is debug: {}".format(line_lower))
        # Common debug patterns to filter
        debug_patterns = [
            "[trace][paal]",
            "debug: ",
        ]

        for pattern in debug_patterns:
            if pattern in line_lower:
                return True

        return False

    def _check_for_errors(self, raw_line, parsed_line):
        """
        Check for error conditions in the serial output
        :param raw_line: Raw bytes from serial
        :param parsed_line: Parsed string line
        """
        # Check for various error patterns (case insensitive)
        error_patterns = [
            b"Error ",
            b"ERROR:",
            b"error:",
            b"Error:",
            b"FAIL",
            b"fail",
            b"Exception",
            b"exception",
            b"Fatal",
            b"fatal",
            b"Critical",
            b"critical"
        ]

        # Check raw line for error patterns
        for pattern in error_patterns:
            if pattern in raw_line:
                log.error("Output: {}".format(raw_line))
                return

        # Also check parsed line for error keywords
        parsed_lower = parsed_line.lower()
        error_keywords = [
            "error", "fail", "exception", "fatal", "critical",
            "timeout", "abort", "crash", "panic"
        ]

        for keyword in error_keywords:
            if keyword in parsed_lower:
                log.error("Output: {}".format(raw_line))
                return

    def _read_line(self, timeout):
        """
        Read data from input queue
        :param timeout: Timeout
        :return: Data from queue
        """
        return self.iq.get(timeout=timeout)

    def clear_input(self):
        """
        Clear input queue messages
        """
        with self.iq.mutex:
            self.iq.queue.clear()

    def kill(self):
        """
        Kill the client runner
        """
        log.debug('Killing client "D{}" runner...'.format(self.name))
        self.run = False

    def reset(self):
        """
        Send reset to client
        """
        self.dut.reset()

    def endpoint_id(self, wait_for_response=10):
        """
        Get endpoint id from client
        :param wait_for_response: Timeout waiting the response
        :return: Endpoint id
        """
        if self._ep_id is None:
            ep_id = self.wait_for_output("Device Id:", wait_for_response)
            if ep_id is not None:
                ep_array = ep_id.split()
                if len(ep_array) > 1:
                    self._ep_id = ep_array[2]
        return self._ep_id

    def wait_for_output(
        self,
        search,
        timeout=60,
        assert_errors=True,
        ignore_case=True,
        errors=None,
    ):
        """
        Wait for expected output response
        :param search: Expected response string
        :param timeout: Response waiting time
        :param assert_errors: Assert on error situations
        :param ignore_case: Ignore client output's casing
        :param errors: String(s) that should cause error
        :return: Response line with expected string or None if either line containing
                 one of the errors strings was found or timeout was reached (and assert_errors was False)
        """

        if errors is None:
            errors = []
        elif isinstance(errors, str):
            errors = [errors]

        if ignore_case:
            search = search.lower()
            errors = deepcopy(errors)
            for i, error in enumerate(errors):
                errors[i] = error.lower()

        return self._do_wait_for_output(
            search, errors, timeout, assert_errors, ignore_case
        )

    def _do_wait_for_output(
        self, search, errors, timeout, assert_errors, ignore_case
    ):
        start = time()
        now = 0
        time_to_wait = timeout
        timeout_error_msg = "Didn't find {} in {} s".format(
            search, time_to_wait
        )

        while True:
            try:
                line = self._read_line(1)
                if line:
                    if ignore_case:
                        line = line.lower()
                    if search in line:
                        end = time()
                        log.debug(
                            'Expected string "{}" found! [time][{:.4f} s]'.format(
                                search, end - start
                            )
                        )
                        return line
                    for error in errors:
                        if error in line:
                            end = time()
                            log.debug(
                                'Expected error string "{}" found! [time][{:.4f} s]'.format(
                                    error, end - start
                                )
                            )
                            break
                    else:
                        continue

                    if assert_errors:
                        assert (
                            False
                        ), 'Error string found from line "{}"'.format(line)
                    else:
                        return None
                else:
                    last = now
                    now = time()
                    if now - start >= timeout:
                        if assert_errors:
                            assert False, timeout_error_msg
                        else:
                            log.warning(timeout_error_msg)
                            break
                    if now - last > 1:
                        log.debug(
                            'Waiting for "{}" string... Timeout in {:.0f} s'.format(
                                search, abs(now - start - timeout)
                            )
                        )
            except queue.Empty:
                last = now
                now = time()
                if now - start >= timeout:
                    if assert_errors:
                        assert False, timeout_error_msg
                    else:
                        log.warning(timeout_error_msg)
                        break
                if now - last > 1:
                    log.debug(
                        'Waiting for "{}" string... Timeout in {:.0f} s'.format(
                            search, abs(now - start - timeout)
                        )
                    )
