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


class ConnectAPI:
    """
    A class that provides Device management connect related functionality.
    https://www.pelion.com/docs/device-management/current/service-api-references/device-management-connect.html

    """

    def __init__(self, rest_api):
        """
        Initializes the Device Management Connect library
        :param rest_api: RestAPI object
        """
        self.api_version = 'v2'
        self.cloud_api = rest_api

    def send_device_request(self, device_id, request_data, request_params, headers=None, expected_status_code=None):
        """
        Send async request to device
        :param device_id: Device id
        :param request_data: Request payload data
        :param request_params: Request parameters
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: POST /v2/device-requests/{device_id} response
        """
        api_url = '/{}/device-requests/{}'.format(self.api_version, device_id)
        r = self.cloud_api.post(api_url, request_data, headers, expected_status_code, params=request_params)
        return r

    def get_device_resource_value(self, device_id, resource_path, headers=None, expected_status_code=None):
        """
        Get device resource
        :param device_id: Device id
        :param resource_path: Resource path
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: GET /v2/endpoints/{device_id} response
        """
        api_url = '/{}/endpoints/{}/{}'.format(self.api_version, device_id, resource_path)
        r = self.cloud_api.get(api_url, headers, expected_status_code)
        return r

    def set_device_resource_value(self, device_id, resource_path, resource_data, headers=None,
                                  expected_status_code=None):
        """
        Write to a Resource
        :param device_id: Device id
        :param resource_path: Resource path
        :param resource_data: Resource data value
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: PUT /v2/endpoints/{device_id}/{resourcePath} response
        """
        api_url = '/{}/endpoints/{}/{}'.format(self.api_version, device_id, resource_path)

        # Set text/plain to be default content type for this request - content type from parameters will override this
        headers = {**{'Content-type': 'text/plain'}, **headers}

        r = self.cloud_api.put(api_url, resource_data, headers, expected_status_code)
        return r

    def set_subscription_for_resource(self, device_id, resource_path, headers=None, expected_status_code=None):
        """
        Subscribe to resource path
        :param device_id: Device id
        :param resource_path: Resource path
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: PUT /v2/subscriptions/{device_id}/{resource_path} response
        """
        api_url = '/{}/subscriptions/{}/{}'.format(self.api_version, device_id, resource_path)
        r = self.cloud_api.put(api_url, headers=headers, expected_status_code=expected_status_code)
        return r

    def register_websocket_channel(self, headers=None, expected_status_code=None):
        """
        Register websocket channel
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: PUT /v2/notification/websocket response
        """
        api_url = '/{}/notification/websocket'.format(self.api_version)
        r = self.cloud_api.put(api_url, headers=headers, expected_status_code=expected_status_code)
        return r

    def get_websocket_channel(self, headers=None, expected_status_code=None):
        """
        Get websocket channel info
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: GET /v2/notification/websocket response
        """
        api_url = '/{}/notification/websocket'.format(self.api_version)
        r = self.cloud_api.get(api_url, headers, expected_status_code)
        return r

    def open_websocket_channel(self, headers=None, expected_status_code=None):
        """
        Open the websocket
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: GET /v2/notification/websocket-connect response
        """
        api_url = '/{}/notification/websocket-connect'.format(self.api_version)
        r = self.cloud_api.get(api_url, headers, expected_status_code)
        return r

    def delete_websocket_channel(self, headers=None, expected_status_code=None):
        """
        Delete websocket channel
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: DELETE /v2/notification/websocket response
        """
        api_url = '/{}/notification/websocket'.format(self.api_version)
        r = self.cloud_api.delete(api_url, headers, expected_status_code)
        return r
