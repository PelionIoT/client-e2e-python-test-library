"""
Copyright 2019-2020 ARM Limited
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


class DeviceDirectoryAPI:
    """
    A class that provides Device directory related functionality.
    https://www.pelion.com/docs/device-management/current/service-api-references/device-directory.html
    :param rest_api: RestAPI object
    """

    def __init__(self, rest_api):
        self.api_version = 'v3'
        self.cloud_api = rest_api

    def get_device(self, device_id, headers=None, expected_status_code=None):
        """
        Get device
        :param device_id: Device id
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: GET /devices/{device_id} response
        """
        api_url = '/{}/devices/{}'.format(self.api_version, device_id)
        r = self.cloud_api.get(api_url, headers, expected_status_code)
        return r

    def delete_device(self, device_id, headers=None, expected_status_code=None):
        """
        Delete device
        :param device_id: Device id
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: DELETE /devices/{device_id} response
        """
        api_url = '/{}/devices/{}'.format(self.api_version, device_id)
        r = self.cloud_api.delete(api_url, headers, expected_status_code)
        return r
