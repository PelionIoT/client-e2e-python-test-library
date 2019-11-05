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

import inspect
import logging
import requests
from pelion_test_lib.tools.utils import assert_status

logging.basicConfig(format="%(asctime)s:%(name)s:%(threadName)s:%(levelname)s: %(message)s")
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

urllib3_logger = logging.getLogger('urllib3')
urllib3_logger.setLevel(logging.WARNING)


class RestAPI:
    """
    Rest API connection class - uses requests

    """
    def __init__(self, api_gw, api_key):
        """
        Initializes the RestAPI request class
        :param api_gw: api gateway url
        :param api_key: api-key
        """

        self.api_gw = api_gw
        self._api_key = api_key
        user_agent = 'pelion-e2e-test-library'
        default_content_type = 'application/json'

        self.headers = {'User-Agent': '{}'.format(user_agent),
                        'Content-type': '{}'.format(default_content_type),
                        'Authorization': 'Bearer {}'.format(self._api_key)}

    def set_default_api_key(self, key):
        """
        Set the default api key for REST API calls
        :param key: Api key

        """
        log.debug('Set default api key to: {}...{}'.format(key[:5], key[-5:]))
        self._api_key = key
        self.headers['Authorization'] = 'Bearer {}'.format(self._api_key)

    @staticmethod
    def _write_log_response(method, api_url, r):
        """
        Function handling the response logging
        :param method: GET, PUT, POST, etc to be written in short response log
        :param api_url: API endpoint url where the response came from
        :param r: The response itself

        """
        log.debug('Request headers: {}'.format(r.request.headers))
        log.debug('Request body: {}'.format(r.request.body))
        log.debug('Response headers: {}'.format(r.headers))
        log.debug('Response: [{}]  {} {}'.format(r.status_code, method, api_url))
        log.debug('Response text: {}'.format(r.text))

    def _combine_headers(self, additional_header):
        """
        Merge header dictionaries together
        :param additional_header: Headers to merge with default ones
        :return: Merged header dictionary
        """
        return {**self.headers, **additional_header}

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
        if headers is not None:
            request_headers = self._combine_headers(headers)
        else:
            request_headers = self.headers

        r = requests.get(url, headers=request_headers, **kwargs)
        self._write_log_response('GET', api_url, r)
        if expected_status_code is not None:
            assert_status(r, inspect.stack()[1][3], expected_status_code)

        return r

    def put(self, api_url, data=None, headers=None, expected_status_code=None, **kwargs):
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
        if headers is not None:
            request_headers = self._combine_headers(headers)
        else:
            request_headers = self.headers

        r = requests.put(url, headers=request_headers, data=data, **kwargs)
        self._write_log_response('PUT', api_url, r)
        if expected_status_code is not None:
            assert_status(r, inspect.stack()[1][3], expected_status_code)

        return r

    def post(self, api_url, data=None, headers=None, expected_status_code=None, **kwargs):
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
        if headers is not None:
            request_headers = self._combine_headers(headers)
        else:
            request_headers = self.headers

        r = requests.post(url, headers=request_headers, data=data, **kwargs)
        self._write_log_response('POST', api_url, r)
        if expected_status_code is not None:
            assert_status(r, inspect.stack()[1][3], expected_status_code)

        return r

    def delete(self, api_url, headers=None, expected_status_code=None, **kwargs):
        """
        DELETE
        :param api_url: API URL
        :param headers: Custom header
        :param expected_status_code: Asserts the result's status code
        :param kwargs: Other arguments used in the requests. http://docs.python-requests.org/en/master/api/
        :return: Request response
        """
        url = self.api_gw + api_url
        if headers is not None:
            request_headers = self._combine_headers(headers)
        else:
            request_headers = self.headers

        r = requests.delete(url, headers=request_headers, **kwargs)
        self._write_log_response('DELETE', api_url, r)
        if expected_status_code is not None:
            assert_status(r, inspect.stack()[1][3], expected_status_code)

        return r
