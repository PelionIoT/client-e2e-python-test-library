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
from time import sleep, time

logging.basicConfig(format="%(asctime)s:%(name)s:%(threadName)s:%(levelname)s: %(message)s")
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


def wait_for_campaign_state(cloud, campaign_id, expected_state='autostopped', timeout=300, delay=10):
    """
    Wait campaign to reach expected state
    :param cloud: Cloud API object
    :param campaign_id: Campaign id
    :param expected_state: Expected state
    :param timeout: timeout in seconds
    :param delay: delay in seconds per each check
    :raises: Assert fail if timeout is reached
    """
    cutout_time = time() + timeout
    campaign_state = ''
    log.info('Waiting update campaign to reach "{}" state in next {} seconds'.format(expected_state, timeout))
    while time() < cutout_time:
        r = cloud.update.get_update_campaign(campaign_id, expected_status_code=200)
        campaign_data = r.json()
        campaign_state = campaign_data['state']
        if campaign_state == expected_state:
            log.info('Update campaign reached the "{}" state. Campaign: {}'.format(expected_state, campaign_id))
            return
        log.info('Campaign state "{}" - waiting {} seconds...'.format(campaign_state, delay))
        sleep(delay)
    assert False, 'Timeout while waiting update campaign to reach "{}" state. ' \
                  'Campaign: {} - "{}"'.format(expected_state, campaign_id, campaign_state)


def wait_for_campaign_phase(cloud, campaign_id, expected_phases, timeout=300, delay=10):
    """
    Wait campaign to reach expected phase
    :param cloud: Cloud API object
    :param campaign_id: Campaign id
    :param expected_phases: List of phases e.g. ['draft', 'stopped']
    :param timeout: timeout in seconds
    :param delay: delay in seconds per each check
    :raises: Assert fail if timeout is reached
    """
    cutout_time = time() + timeout
    campaign_phase = ''
    log.info('Waiting update campaign to reach "{}" phase(s) in next {} seconds'.format(expected_phases, timeout))
    while time() < cutout_time:
        r = cloud.update.get_update_campaign(campaign_id, expected_status_code=200)
        campaign_data = r.json()
        campaign_phase = campaign_data['phase']
        if campaign_phase in expected_phases:
            log.info('Update campaign reached the "{}" phase. Campaign: {}'.format(campaign_phase, campaign_id))
            return
        log.info('Campaign phase "{}" - waiting {} seconds...'.format(campaign_phase, delay))
        sleep(delay)
    assert False, 'Timeout while waiting update campaign to reach "{}" phase. ' \
                  'Campaign: {} - "{}"'.format(campaign_phase, campaign_id, campaign_phase)


def wait_for_campaign_device_state(cloud, campaign_id, device_id, expected_state='deployed', timeout=300, delay=10):
    """
    Wait campaign device state to reach expected state
    :param cloud: Cloud API object
    :param campaign_id: campaign id
    :param device_id: device id
    :param expected_state: Expected state
    :param timeout: timeout in seconds
    :param delay: delay in seconds per each check
    :raises: Assert fail if timeout is reached
    """
    cutout_time = time() + timeout
    campaign_device_state = ''
    log.info('Waiting update campaign device state to reach "{}" state in next {} seconds'.format(expected_state,
                                                                                                  timeout))
    while time() < cutout_time:
        r = cloud.update.get_update_campaign_metadata(campaign_id, expected_status_code=200)
        resp_data = r.json()['data']
        campaign_device_state = resp_data[0]
        if device_id == campaign_device_state['device_id']:
            campaign_device_state = campaign_device_state['deployment_state']
            if campaign_device_state == expected_state:
                log.info('Update campaign device reached the "{}" state. Campaign: {}'.format(expected_state,
                                                                                              campaign_id))
                return
            log.info('Device state "{}" - waiting {} seconds...'.format(campaign_device_state, delay))
            sleep(delay)
    assert False, 'Timeout while waiting update campaign device state to reach "{}". ' \
                  'Campaign: {} - "{}"'.format(expected_state, campaign_id, campaign_device_state)
