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


class AccountManagementAPI:
    """
    A class that provides Account management related functionality.
    https://www.pelion.com/docs/device-management/current/service-api-references/account-management.html
    :param rest_api: RestAPI object
    """

    def __init__(self, rest_api):
        self.api_version = 'v3'
        self.cloud_api = rest_api

    def create_api_key(self, request_data, headers=None, expected_status_code=None):
        """
        Generate API key
        :param request_data: API key payload
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: POST /api-key response
        """
        api_url = '/{}/api-keys'.format(self.api_version)
        r = self.cloud_api.post(api_url, request_data, headers, expected_status_code)
        return r

    def delete_api_key(self, api_key_id, headers=None, expected_status_code=None):
        """
        Delete API key
        :param api_key_id: API key id
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: DELETE /api-keys/{api key_id} response
        """
        api_url = '/{}/api-keys/{}'.format(self.api_version, api_key_id)
        r = self.cloud_api.delete(api_url, headers, expected_status_code)
        return r
