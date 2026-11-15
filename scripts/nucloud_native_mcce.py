"""Read the native MCCE endpoint field through its console protocol."""
import re
from client_test_lib.tools.client_runner import Client


def endpoint_id(self, wait_for_response=10):
    if self._ep_id is None:
        line = self.wait_for_output('Device ID:', wait_for_response)
        if line is not None:
            match = re.search(r'Device ID:\s*([a-fA-F0-9]{32})', line)
            if not match:
                raise ValueError('native MCCE returned a malformed endpoint field')
            self._ep_id = match.group(1)
    return self._ep_id


def pytest_configure(config):
    # Native MCCE spells its real console field ID; the library parser spells Id.
    Client.endpoint_id = endpoint_id
