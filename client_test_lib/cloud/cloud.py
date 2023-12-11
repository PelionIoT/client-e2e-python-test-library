"""
Copyright 2019-2020 Pelion.
Copyright (c) 2023 Izuma Networks

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

from client_test_lib.cloud.libraries.account import AccountManagementAPI
from client_test_lib.cloud.libraries.connect import ConnectAPI
from client_test_lib.cloud.libraries.device_directory import DeviceDirectoryAPI
from client_test_lib.cloud.libraries.rest_api.rest_api import RestAPI
from client_test_lib.cloud.libraries.update import UpdateAPI


class PelionCloud:
    """
    Pelion Cloud class to provide handles for all rest api libraries
    :param api_gw: api gateway url
    :param api_key: api-key
    """

    def __init__(self, api_gw, api_key):
        self._api_gw = api_gw
        self._api_key = api_key
        self._rest_api = RestAPI(api_gw, api_key)
        self._account = AccountManagementAPI(self._rest_api)
        self._connect = ConnectAPI(self._rest_api)
        self._device_directory = DeviceDirectoryAPI(self._rest_api)
        self._update = UpdateAPI(self._rest_api)

    @property
    def api_gw(self):
        """
        Returns API gateway url
        """
        return self._api_gw

    @property
    def api_key(self):
        """
        Returns used API key
        """
        if self.rest_api:
            return self.rest_api.api_key
        return self._api_key

    @property
    def account(self):
        """
        Returns Account API class
        """
        return self._account

    @property
    def connect(self):
        """
        Returns Connect API class
        """
        return self._connect

    @property
    def device_directory(self):
        """
        Returns Device directory API class
        """
        return self._device_directory

    @property
    def rest_api(self):
        """
        Returns Rest API class
        """
        return self._rest_api

    @property
    def update(self):
        """
        Returns Update API class
        """
        return self._update
