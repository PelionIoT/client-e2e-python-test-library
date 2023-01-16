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

import base64
import logging
import uuid

log = logging.getLogger(__name__)


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
    request_params = {"async-id": async_id}
    request_payload = {"method": "GET", "uri": path}
    cloud.connect.send_device_request(
        device_id,
        request_payload,
        request_params,
        headers=headers,
        expected_status_code=202,
    )
    return async_id


def put_async_device_request(
    cloud, path, device_id, request_data, headers, content_type="text/plain"
):
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
    request_payload = {
        "method": "PUT",
        "uri": path,
        "content-type": content_type,
        "payload-b64": payload_data,
    }
    cloud.connect.send_device_request(
        device_id,
        request_payload,
        request_params,
        headers=headers,
        expected_status_code=202,
    )
    return async_id


def post_async_device_request(cloud, path, device_id, headers):
    """
    Sends POST async request to device
    https://www.pelion.com/docs/device-management/current/service-api-references/device-management-connect.html#createAsyncRequest
    :param cloud: Cloud object
    :param path: Device resource path
    :param device_id: Device ID
    :param headers: Request headers
    :return: Async_id
    """
    async_id = str(uuid.uuid4())
    request_params = {"async-id": async_id}
    request_payload = {"method": "POST", "uri": path}
    cloud.connect.send_device_request(
        device_id,
        request_payload,
        request_params,
        headers=headers,
        expected_status_code=202,
    )
    return async_id


def device_resource_exists(cloud, path, device_id, headers):
    """
    Checks if device has defined path by the GET async request
    :param cloud: Cloud object
    :param path: Device resource path
    :param device_id: Device ID
    :param headers: Request headers
    :return: False if cloud returns 400, RESOURCE_NOT_FOUND
    """
    async_id = str(uuid.uuid4())
    request_params = {"async-id": async_id}
    request_payload = {"method": "GET", "uri": path}
    r = cloud.connect.send_device_request(
        device_id,
        request_payload,
        request_params,
        headers=headers,
        expected_status_code=[202, 400],
    )
    if r.status_code == 400:
        if r.text == "RESOURCE_NOT_FOUND":
            return False
        log.error(r.text)
    return True
