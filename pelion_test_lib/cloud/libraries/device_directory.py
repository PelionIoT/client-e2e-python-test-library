class DeviceDirectoryAPI:
    """
    A class that provides Device directory related functionality.
    https://www.pelion.com/docs/device-management/current/service-api-references/device-directory.html

    """

    def __init__(self, rest_api):
        """
        Initializes the Device Directory library
        :param rest_api: RestAPI object
        """
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
