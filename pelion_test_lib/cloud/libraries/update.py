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


class UpdateAPI:
    """
    A class that provides Update related functionality.
    https://www.pelion.com/docs/device-management/current/service-api-references/update-service.html

    """

    def __init__(self, rest_api):
        """
        Initializes the Update library
        :param rest_api: RestAPI object
        """
        self.api_version = 'v3'
        self.cloud_api = rest_api

    def create_update_campaign(self, request_data, headers=None, expected_status_code=None):
        """
        Create update campaign
        :param request_data: Campaign payload
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: POST /update-campaigns response
        """
        api_url = '/{}/update-campaigns'.format(self.api_version)
        r = self.cloud_api.post(api_url, request_data, headers, expected_status_code)
        return r

    def get_update_campaign(self, campaign_id, headers=None, expected_status_code=None):
        """
        Get the update campaign info
        :param campaign_id: Campaign id
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: GET /update-campaign/{campaign_id} response
        """
        api_url = '/{}/update-campaigns/{}'.format(self.api_version, campaign_id)
        r = self.cloud_api.get(api_url, headers, expected_status_code)
        return r

    def get_update_campaign_metadata(self, campaign_id, headers=None, expected_status_code=None):
        """
        Get update campaign device metadata
        :param campaign_id: Campaign id
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: GET /update-campaign/{campaign_id}/campaign-device-metadata response
        """
        api_url = '/{}/update-campaigns/{}/campaign-device-metadata'.format(self.api_version, campaign_id)
        r = self.cloud_api.get(api_url, headers, expected_status_code)
        return r

    def get_update_campaigns(self, query_params=None, headers=None, expected_status_code=None):
        """
        Get update campaigns
        :param query_params: e.g.{'limit': '1000', 'include': 'total_count'}
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: GET /update-campaigns response
        """
        api_url = '/{}/update-campaigns'.format(self.api_version)
        r = self.cloud_api.get(api_url, headers, expected_status_code, params=query_params)
        return r

    def start_update_campaign(self, campaign_id, headers=None, expected_status_code=None):
        """
        Start update campaign
        :param campaign_id: Campaign id
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: POST /update-campaigns/{campaign_id}/start response
        """
        api_url = '/{}/update-campaigns/{}/start'.format(self.api_version, campaign_id)
        r = self.cloud_api.post(api_url, headers=headers, expected_status_code=expected_status_code)
        return r

    def stop_update_campaign(self, campaign_id, headers=None, expected_status_code=None):
        """
        Stop update campaign
        :param campaign_id: Campaign id
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: POST /update-campaigns/{campaign_id}/stop response
        """
        api_url = '/{}/update-campaigns/{}/stop'.format(self.api_version, campaign_id)
        r = self.cloud_api.post(api_url, headers=headers, expected_status_code=expected_status_code)
        return r

    def delete_update_campaign(self, campaign_id, headers=None, expected_status_code=None):
        """
        Delete update campaign
        :param campaign_id: Campaign id
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: DELETE /update-campaigns/{campaign_id} response
        """
        api_url = '/{}/update-campaigns/{}'.format(self.api_version, campaign_id)
        r = self.cloud_api.delete(api_url, headers, expected_status_code=expected_status_code)
        return r

    def upload_firmware_image(self, firmware_binary_path, request_data=None, headers=None, expected_status_code=None):
        """
        Upload firmware image
        :param firmware_binary_path: Path to firmware binary
        :param request_data: Firmware payload (optional)
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: POST /firmware-images response
        """
        api_url = '/{}/firmware-images'.format(self.api_version)
        if not headers:
            headers = dict()
        headers = {**{'Content-type': 'multipart/form-data'}, **headers}
        fw_image = {'datafile': open(firmware_binary_path, 'rb')}
        r = self.cloud_api.post(api_url, request_data, headers, expected_status_code, files=fw_image)
        return r

    def delete_firmware_image(self, firmware_id, headers=None, expected_status_code=None):
        """
        Delete firmware image
        :param firmware_id: Firmware id
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result in the function
        :return: DELETE /firmware-images/{firmware_id} response
        """
        api_url = '/{}/firmware-images/{}'.format(self.api_version, firmware_id)
        r = self.cloud_api.delete(api_url, headers, expected_status_code=expected_status_code)
        return r

    def upload_firmware_manifest(self, manifest_file_path, request_data=None, headers=None, expected_status_code=None):
        """
        Upload firmware manifest
        :param manifest_file_path: Path to manifest file
        :param request_data: Manifest payload (optional)
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: POST /firmware-manifests response
        """
        api_url = '/{}/firmware-manifests'.format(self.api_version)
        if not headers:
            headers = dict()
        headers = {**{'Content-type': 'multipart/form-data'}, **headers}
        manifest_file = {'datafile': open(manifest_file_path, 'rb')}
        r = self.cloud_api.post(api_url, request_data, headers, expected_status_code, files=manifest_file)
        return r

    def delete_firmware_manifest(self, manifest_id, headers=None, expected_status_code=None):
        """
        Delete firmware manifest
        :param manifest_id: Manifest id
        :param headers: Override default header fields
        :param expected_status_code: Asserts the result's status code
        :return: DELETE /firmware-manifests/{manifest_id} response
        """
        api_url = '/{}/firmware-manifests/{}'.format(self.api_version, manifest_id)
        r = self.cloud_api.delete(api_url, headers, expected_status_code=expected_status_code)
        return r
