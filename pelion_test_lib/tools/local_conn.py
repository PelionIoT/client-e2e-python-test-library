"""
Copyright 2020 ARM Limited
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
from subprocess import Popen, PIPE

log = logging.getLogger(__name__)


class LocalConnection:
    """
    Connection class for local binary
    :param command: Command to start the local binary
    :param use_stderr: Use stderr output instead of stdout
    """

    def __init__(self, command, use_stderr=False):
        self.process = None
        self.command = command
        self.use_stderr = use_stderr
        self.open()

    def open(self):
        """
        Start the process
        """
        log.info('Starting local process: "{}"'.format(self.command))
        if not self.process:
            self.process = Popen(self.command, stdin=PIPE, stdout=PIPE, stderr=PIPE, bufsize=0)

    def readline(self):
        """
        Read line from the process
        :return: One line from stdout or stderr stream
        """
        if self.use_stderr:
            return self.process.stderr.readline()
        return self.process.stdout.readline()

    def write(self, data):
        """
        Write data to stdin
        :param data: Data to send
        """
        self.process.stdin.write(data)

    def reset(self):
        """
        Restart the process
        """
        self.close()
        self.open()

    def close(self):
        """
        Close running process
        """
        if self.process:
            self.process.kill()
            self.process = None
