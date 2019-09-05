from pelion_test_lib.cloud.libraries.account import AccountManagementAPI
from pelion_test_lib.cloud.libraries.connect import ConnectAPI
from pelion_test_lib.cloud.libraries.device_directory import DeviceDirectoryAPI
from pelion_test_lib.cloud.libraries.rest_api.rest_api import RestAPI


class PelionCloud:
    """
    Pelion Cloud class to provide handles for all rest api libraries

    """
    def __init__(self, api_gw, api_key):
        """
        Initializes the Pelion Cloud class
        :param api_gw: api gateway url
        :param api_key: api-key
        """
        self._api_gw = api_gw
        self._api_key = api_key
        self._rest_api = RestAPI(api_gw, api_key)
        self._account = AccountManagementAPI(self._rest_api)
        self._connect = ConnectAPI(self._rest_api)
        self._device_directory = DeviceDirectoryAPI(self._rest_api)

    @property
    def api_gw(self):
        return self._api_gw

    @property
    def api_key(self):
        return self._api_key

    @property
    def account(self):
        return self._account

    @property
    def connect(self):
        return self._connect

    @property
    def device_directory(self):
        return self._device_directory

    @property
    def rest_api(self):
        return self._rest_api
