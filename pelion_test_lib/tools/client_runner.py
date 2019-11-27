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
import queue
import threading
from time import time
import pelion_test_lib.tools.utils as utils

flog = logging.getLogger('ClientRunner')
flog.setLevel(logging.DEBUG)
fh = logging.FileHandler('client.log')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s:%(name)s:%(threadName)s:%(levelname)s: %(message)s')
fh.setFormatter(formatter)
flog.addHandler(fh)

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class Client:

    def __init__(self, dut, trace=False, name='0'):
        """
        Client runner class that handles communication for given dut object
        :param dut: Running client object
        :param trace: Log the raw client output
        :param name: Logging name for the client
        """
        self._ep_id = None
        self.name = name
        self.trace = trace
        self.run = True
        self.iq = queue.Queue()
        self.dut = dut

        input_thread_name = '<-- D{}'.format(name)
        it = threading.Thread(target=self._input_thread, name=input_thread_name)
        it.setDaemon(True)
        log.info('Starting runner threads for client "D{}"'.format(self.name))
        it.start()

    def _input_thread(self):
        while self.run:
            line = self.dut.readline()
            if line:
                plain_line = utils.strip_escape(line)
                if b'\r' in line and line.count(b'\r') > 1:
                    plain_line = plain_line.split(b'\r')[-2]
                plain_line = plain_line.replace(b'\t', b'  ').decode('utf-8')
                flog.info('<--|D{}| {}'.format(self.name, plain_line.strip()))
                if self.trace:
                    log.debug('Raw output: {}'.format(line))
                if b'Error' in line:
                    log.error('Output: {}'.format(line))
                self.iq.put(plain_line)
            else:
                pass

    def _read_line(self, timeout):
        return self.iq.get(timeout=timeout)

    def kill(self):
        """
        Kill the client runner
        """
        log.debug('Killing client "D{}" runner...'.format(self.name))
        self.run = False

    def endpoint_id(self, wait_for_response=10):
        """
        Get endpoint id from client
        :param wait_for_response: Timeout waiting the response
        :return: Endpoint id
        """
        if self._ep_id is None:
            ep_id = self.wait_for_output('Device Id:', wait_for_response)
            if ep_id is not None:
                log.debug(ep_id)
                ep_array = ep_id.split()
                if len(ep_array) > 1:
                    self._ep_id = ep_array[2]

        return self._ep_id

    def wait_for_output(self, search, timeout=60, assert_errors=True, ignore_case=True):
        """
        Wait for expected output response
        :param search: Expected response string
        :param timeout: Response waiting time
        :param assert_errors: Assert on error situations
        :param ignore_case: Ignore client output's casing
        :return: Response line with expected string
        """
        start = time()
        now = 0
        time_to_wait = timeout
        timeout_error_msg = 'Didn\'t find {} in {} s'.format(search, time_to_wait)

        while True:
            try:
                line = self._read_line(1)
                if line:
                    if ignore_case:
                        search = search.lower()
                        line = line.lower()
                    if search in line:
                        end = time()
                        log.debug('Expected string "{}" found! [time][{:.4f} s]'.format(search, end - start))
                        return line
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
                        log.debug('Waiting for "{}" string... Timeout in {:.0f} s'.format(search,
                                                                                          abs(now - start - timeout)))
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
                    log.debug('Waiting for "{}" string... Timeout in {:.0f} s'.format(search,
                                                                                      abs(now - start - timeout)))
