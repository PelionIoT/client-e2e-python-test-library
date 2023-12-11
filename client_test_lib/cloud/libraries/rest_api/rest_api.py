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

import copy
import inspect
import json
import logging
import requests
from client_test_lib.tools.utils import assert_status

log = logging.getLogger(__name__)

urllib3_logger = logging.getLogger("urllib3")
urllib3_logger.setLevel(logging.WARNING)


class RestAPI:
    """
    Rest API connection class - uses requests
    :param api_gw: api gateway url
    :param api_key: api-key
    """

    def __init__(self, api_gw, api_key):
        self.api_gw = api_gw
        self._api_key = api_key
        user_agent = "pelion-e2e-test-library"
        default_content_type = "application/json"

        self.headers = {
            "User-Agent": "{}".format(user_agent),
            "Content-type": "{}".format(default_content_type),
            "Authorization": "Bearer {}".format(self._api_key),
        }

    def set_default_api_key(self, key):
        """
        Set the default api key for REST API calls
        :param key: Api key
        """
        log.debug("Set default api key to: {}...{}".format(key[:5], key[-5:]))
        self._api_key = key
        self.headers["Authorization"] = "Bearer {}".format(self._api_key)

    @property
    def api_key(self):
        """
        Returns default API key
        """
        return self._api_key

    @staticmethod
    def _clean_request_body(req_body):
        """
        Cleans the password and binary data from request body for logging
        :param req_body: Request body
        :return: Cleaned body for logging
        """
        if req_body is not None:
            if isinstance(req_body, str):
                split_body = req_body.split("&")
                for param in split_body:
                    if "password=" in param:
                        pwd = param.split("=")[1]
                        req_body = req_body.replace(
                            "password={}".format(pwd), "password=*"
                        )
            if isinstance(req_body, bytes):
                req_body = "body content in binary data - removed from the log"
        return req_body

    @staticmethod
    def _data_content(headers, data):
        if "Content-type" in headers and data:
            if headers["Content-type"] == "application/json":
                return json.dumps(data)
        return data

    @staticmethod
    def _write_log_response(method, api_url, r):
        """
        Function handling the response logging
        :param method: GET, PUT, POST, etc to be written in short response log
        :param api_url: API endpoint url where the response came from
        :param r: The response itself
        """
        log.debug("Request headers: {}".format(r.request.headers))
        log.debug("Request body: {}".format(r.request.body))
        log.debug("Response headers: {}".format(r.headers))
        log.debug(
            "Response: [{}]  {} {}".format(r.status_code, method, api_url)
        )
        log.debug("Response text: {}".format(r.text))

    def _combine_headers(self, additional_header):
        """
        Merge header dictionaries together
        :param additional_header: Headers to merge with default ones
        :return: Merged header dictionary
        """
        if additional_header:
            _headers = copy.copy(self.headers)
            _headers.update(additional_header)
            return _headers
        return self.headers

    def get(self, api_url, headers=None, expected_status_code=None, **kwargs):
        """
        GET
        :param api_url: API URL
        :param headers: Custom header
        :param expected_status_code: Asserts the result's status code
        :param kwargs: Other arguments used in the requests. http://docs.python-requests.org/en/master/api/
        :return: Request response
        """
        url = self.api_gw + api_url
        request_headers = self._combine_headers(headers)
        r = requests.get(url, headers=request_headers, **kwargs)
        self._write_log_response("GET", api_url, r)
        if expected_status_code is not None:
            assert_status(r, inspect.stack()[1][3], expected_status_code)

        return r

    def put(
        self,
        api_url,
        data=None,
        headers=None,
        expected_status_code=None,
        **kwargs
    ):
        """
        PUT
        :param api_url: API URL
        :param data: PUT request payload
        :param headers: Custom header
        :param expected_status_code: Asserts the result's status code
        :param kwargs: Other arguments used in the requests. http://docs.python-requests.org/en/master/api/
        :return: Request response
        """
        url = self.api_gw + api_url
        request_headers = self._combine_headers(headers)
        request_data = self._data_content(request_headers, data)
        r = requests.put(
            url, headers=request_headers, data=request_data, **kwargs
        )
        self._write_log_response("PUT", api_url, r)
        if expected_status_code is not None:
            assert_status(r, inspect.stack()[1][3], expected_status_code)

        return r

    def post(
        self,
        api_url,
        data=None,
        headers=None,
        expected_status_code=None,
        **kwargs
    ):
        """
        POST
        :param api_url: API URL
        :param data: POST request payload
        :param headers: Custom header
        :param expected_status_code: Asserts the result's status code
        :param kwargs: Other arguments used in the requests. http://docs.python-requests.org/en/master/api/
        :return: Request response
        """
        url = self.api_gw + api_url
        request_headers = self._combine_headers(headers)
        if "files" in kwargs:
            request_headers.pop("Content-type")
        request_data = self._data_content(request_headers, data)
        r = requests.post(
            url, headers=request_headers, data=request_data, **kwargs
        )
        self._write_log_response("POST", api_url, r)
        if expected_status_code is not None:
            assert_status(r, inspect.stack()[1][3], expected_status_code)

        return r

    def delete(
        self, api_url, headers=None, expected_status_code=None, **kwargs
    ):
        """
        DELETE
        :param api_url: API URL
        :param headers: Custom header
        :param expected_status_code: Asserts the result's status code
        :param kwargs: Other arguments used in the requests. http://docs.python-requests.org/en/master/api/
        :return: Request response
        """
        url = self.api_gw + api_url
        request_headers = self._combine_headers(headers)
        r = requests.delete(url, headers=request_headers, **kwargs)
        self._write_log_response("DELETE", api_url, r)
        if expected_status_code is not None:
            assert_status(r, inspect.stack()[1][3], expected_status_code)

        return r
