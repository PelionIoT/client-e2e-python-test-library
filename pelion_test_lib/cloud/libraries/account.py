import json


class AccountManagementAPI:
    """
    A class that provides Account management related functionality.
    https://www.pelion.com/docs/device-management/current/service-api-references/account-management.html

    """

    def __init__(self, rest_api):
        """
        Initializes the Account Management library
        :param rest_api: RestAPI object
        """
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
        r = self.cloud_api.post(api_url, json.dumps(request_data), headers, expected_status_code)
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
