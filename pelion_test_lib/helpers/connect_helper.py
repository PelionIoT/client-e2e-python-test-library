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
import json
import logging
import uuid

logging.basicConfig(format="%(asctime)s:%(name)s:%(threadName)s:%(levelname)s: %(message)s")
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


def get_async_device_request(cloud, path, device_id, headers):
    """
    Sends GET async request to device
    https://www.pelion.com/docs/device-management/current/service-api-references/device-management-connect.html#createAsyncRequest
    :param cloud: Cloud object
    :param path: Device resource path
    :param device_id: Device ID
    :param headers: Request headers
    :return: Async_id
    """
    async_id = str(uuid.uuid4())
    request_params = {'async-id': async_id}
    request_payload = {'method': 'GET', 'uri': path}
    cloud.connect.send_device_request(device_id, json.dumps(request_payload), request_params, headers=headers,
                                      expected_status_code=202)
    return async_id


def put_async_device_request(cloud, path, device_id, request_data, headers, content_type="text/plain"):
    """
    Sends PUT async request to device
    https://www.pelion.com/docs/device-management/current/service-api-references/device-management-connect.html#createAsyncRequest
    :param cloud: Cloud object
    :param path: Device resource path
    :param device_id: Device ID
    :param request_data: Data sent to resource path
    :param headers: Request headers
    :param content_type: Data content type
    :return: Async_id
    """
    async_id = str(uuid.uuid4())
    payload_data = base64.b64encode(str.encode(request_data)).decode()
    request_params = {"async-id": async_id}
    request_payload = {"method": "PUT", "uri": path, "content-type": content_type,
                       "payload-b64": payload_data}
    cloud.connect.send_device_request(device_id, json.dumps(request_payload), request_params, headers=headers,
                                      expected_status_code=202)
    return async_id
