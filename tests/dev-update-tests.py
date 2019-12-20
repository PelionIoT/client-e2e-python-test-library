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
from pelion_test_lib.helpers.update_helper import wait_for_campaign_device_state, wait_for_campaign_state

logging.basicConfig(format="%(asctime)s:%(name)s:%(threadName)s:%(levelname)s: %(message)s")
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


def test_01_update_device(cloud, client, update_device):
    campaign_id = update_device
    client.wait_for_output('New active firmware is valid', timeout=900, errors=['Error occurred'])
    client_id = client.endpoint_id(120)
    wait_for_campaign_state(cloud, campaign_id)
    wait_for_campaign_device_state(cloud, campaign_id, client_id)
