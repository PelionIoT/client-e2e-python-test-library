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

import base64
import datetime
import json
import logging
import queue
import threading
from time import sleep
from ws4py.client.threadedclient import WebSocketClient
from pelion_test_lib.tools.utils import build_random_string

logging.basicConfig(format='%(asctime)s:%(name)s:%(threadName)s:%(levelname)s: %(message)s')
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class WebSocketHandler:
    def __init__(self, ws):
        """
        Class to handle messages via websocket

        :param ws: Websocket Runner class
        """
        self.ws = ws

    def check_registration(self, device_id):
        """
        Check if websocket has registration message(s)

        :param device_id: string
        :return:
        """
        for item in self.ws.events['registrations']:
            # If asked device_id is found return its data. Otherwise return False
            if item['ep'] == device_id:
                return item
        return False

    def check_deregistration(self, device_id):
        """
        Check if websocket has de-registration message(s) for given device id

        :param device_id: string
        :return:
        """
        for item in self.ws.events['de-registrations']:
            # If asked device_id is found return its data. Otherwise return False
            if item['ep'] == device_id:
                return item
        return False

    def check_registration_updates(self, device_id):
        """
        Check if websocket has registration updates message(s) for given device id

        :param device_id: string
        :return: False / dict
        """
        for item in self.ws.events['reg-updates']:
            # If asked device_id is found return its data. Otherwise return False
            if item['ep'] == device_id:
                return item
        return False

    def check_registration_expiration(self, device_id):
        """
        Check if WEBSOCKET-HANDLER has registrations expired message(s) for given device id

        :param device_id: string
        :return: False / dict
        """
        for item in self.ws.events['registrations-expired']:
            # If asked device_id is found return its data. Otherwise return False
            if item['ep'] == device_id:
                return item
        return False

    def get_notifications(self):
        """
        Get all notifications from websocket data

        :return: dict
        """
        return self.ws.events['notifications']

    def get_async_response(self, async_response_id):
        """
        Get async-response from websocket data for given async_id

        :param async_response_id: string
        :return: dict
        """
        return self.ws.async_responses.get(async_response_id)

    def wait_for_multiple_notification(self, device_id, expected_notifications, timeout=30, assert_errors=False):
        """
        Wait for given device id + resource path(s) + expected value(s) to appear in WEBSOCKET-HANDLER

        :param device_id: string
        :param expected_notifications: list of dicts of resource paths with expected values
                                        [{'resource_path': 'expected_value'},
                                        {'resource_path_2}: {'excepted_value_2},
                                        ...
                                        ]
        :param timeout: int
        :param assert_errors: boolean for user if to fail test case in case of expected notifications not received
        :return: False / list of received notifications or fail the test case if confirm_resp=True
        """
        item_list = []
        for _ in range(timeout):
            notifications = self.get_notifications()
            for item in notifications:
                if item['ep'] == device_id:
                    # Check if received notification contains any combinations defined in expected_notifications.
                    # If found, append item to item_list. If as many items are found as are expected, return list.
                    if [expect_item for expect_item in expected_notifications if item['path'] in expect_item.keys()
                            and base64.b64decode(item['payload']).decode('utf8') in expect_item.values()]:
                        item_list.append(item)
                        if len(item_list) == len(expected_notifications):
                            return item_list
            sleep(1)
        log.debug('Expected {}, found only {}!'.format(expected_notifications, item_list))
        if assert_errors:
            assert False, 'Failed to receive notifications'
        return False

    def wait_for_notification(self, device_id, resource_path, expected_value, timeout=30, assert_errors=False):
        """
        Wait for given device id + resource path + expected value to appear in websocket

        :param device_id: string
        :param resource_path: string
        :param expected_value: string
        :param timeout: int
        :param assert_errors: boolean for user if to fail test case in case of expected notification not received
        :return: dict or fail the test case if confirm_resp=True
        """
        expected_value = str(expected_value)
        for _ in range(timeout):
            for item in self.ws.events['notifications']:
                if item['ep'] == device_id and item['path'] == resource_path and \
                        base64.b64decode(item['payload']).decode('utf8') == expected_value:
                    return item
            sleep(1)
        if assert_errors:
            assert False, 'Failed to receive notification'
        return False

    def wait_for_async_response(self, async_response_id, timeout=30, assert_errors=False):
        """
        Wait for given async-response to appear in websocket data

        :param async_response_id: string
        :param timeout: int
        :param assert_errors: boolean for user if to fail test case in case of expected response not received
        :return: dict or fail the test case if confirm_resp=True
        """
        for _ in range(timeout):
            async_response = self.ws.async_responses.get(async_response_id)
            if async_response:
                if 'payload' in async_response:
                    # decode original payload and append in received async response
                    async_response['decoded_payload'] = base64.b64decode(async_response['payload'])
                    log.info('Async response received: "{}"'.format(str(async_response['decoded_payload'])))
                return async_response
            sleep(1)
        if assert_errors:
            assert False, 'Failed to receive async response'
        return False

    def wait_for_registration(self, device_id, timeout=30):
        """
        Wait for given device id registration to appear in websocket

        :param device_id: string
        :param timeout: int
        :return: False / dict
        """
        for _ in range(timeout):
            registration = self.check_registration(device_id)
            if registration:
                return registration
            sleep(1)
        return False

    def wait_for_registration_updates(self, device_id, timeout=30):
        """
        Wait for given device id registration update notification to appear in websocket

        :param device_id: string
        :param timeout: int
        :return: False / dict
        """
        for _ in range(timeout):
            registration = self.check_registration_updates(device_id)
            if registration:
                return registration
            sleep(1)
        return False

    def wait_for_registration_expiration(self, device_id, timeout=30):
        """
        Wait for given device id registration expiration notification to appear in websocket

        :param device_id: string
        :param timeout: int
        :return: False / dict
        """
        for _ in range(timeout):
            registration = self.check_registration_expiration(device_id)
            if registration:
                return registration
            sleep(1)
        return False

    def wait_for_deregistration(self, device_id, timeout=30):
        """
        Wait for given device id de-registration to appear in websocket

        :param device_id: string
        :param timeout: int
        :return: False / dict
        """
        for _ in range(timeout):
            deregistration = self.check_deregistration(device_id)
            if deregistration:
                return deregistration
            sleep(1)
        return False


class WebsocketRunner:
    """
    Class for handling websocket connection and storing data from notification service

    :param api: string URL for websocket connection endpoint
    :param api_key: string
    """

    def __init__(self, api, api_key):
        self.async_responses = {}
        self.events = dict()
        self.events['registrations'] = []
        self.events['notifications'] = []
        self.events['reg-updates'] = []
        self.events['de-registrations'] = []
        self.events['registrations-expired'] = []
        self.run = True
        self.message_queue = queue.Queue()

        it = threading.Thread(target=self.input_thread, args=(api, api_key),
                              name='websocket_{}'.format(build_random_string(3)))
        ht = threading.Thread(target=self.handle_thread, name='messages_{}'.format(build_random_string(3)))
        it.setDaemon(True)
        ht.setDaemon(True)
        log.info('Starting websocket threads')
        it.start()
        ht.start()

    def input_thread(self, api, api_key):
        while self.run:
            try:
                ws = CallbackClient(self.message_queue, api, protocols=['wss', 'pelion_{}'.format(api_key)])
                log.debug('Connecting websocket')
                ws.connect()
                log.debug('Run forever websocket handler')
                ws.run_forever()
                log.error('Websocket handler exited')
            except Exception as e:
                log.warning('Websocket failed, retrying! {}'.format(e))
                sleep(1)
            sleep(1)
        log.info('Websocket input thread was stopped.')

    def handle_thread(self):
        while self.run:
            data = self.message_queue.get()
            if data == {}:
                log.info('Received message is empty')
            for notification_type, notification_value in data.items():
                log.debug('Message contains %s', notification_type)
                self._handle_content(notification_type, notification_value)

    def _handle_content(self, notification_type, data):
        for content in data:
            date_now = datetime.datetime.utcnow().isoformat('T') + 'Z'
            # De-registrations is plain list, need to convert it to dict. Otherwise just add timestamp
            if notification_type in ('de-registrations', 'registrations-expired'):
                content = {'dt': date_now, 'ep': content}
            else:
                content['dt'] = date_now
            # Async-responses are saved by response, others are pushed to list
            if notification_type == 'async-responses':
                self.async_responses[content['id']] = content
            else:
                self.events[notification_type].append(content)


class CallbackClient(WebSocketClient):
    def __init__(self, mq, api, protocols):
        super().__init__(api, protocols=protocols)
        self.mq = mq
        self.api = api

    def opened(self):
        log.info('WebSocket opened to {}'.format(self.api))

    def closed(self, code, reason=None):
        log.error('WebSocket closed with code {} reason {}'.format(code, reason))

    def received_message(self, m):
        log.debug('Websocket Received: {}'.format(m))
        self.mq.put(json.loads(str(m)))
