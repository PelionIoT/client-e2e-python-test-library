"""
Copyright 2019-2020 Pelion.
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

import logging
import os
import pytest

pytest_plugins = ['pelion_test_lib.fixtures.client_fixtures',
                  'pelion_test_lib.fixtures.cloud_fixtures']

log = logging.getLogger(__name__)
pytest.global_test_results = []


def pytest_addoption(parser):
    """
    Function to enable pytest commandline arguments
    :param parser: argparser
    :return:
    """
    parser.addoption('--target_id', action='store', help='mbed device target id')
    parser.addoption('--update_bin', action='store', help='mbed device update binary path')
    parser.addoption('--ext_conn', action='store_true', default=False, help='use external connection')
    parser.addoption('--manifest_tool', action='store', default=os.getcwd(), help='manifest-tool init path')
    parser.addoption('--no_cleanup', action='store_true', default=False,
                     help='set true to keep update image, manifest and campaign')
    parser.addoption('--delta_manifest', action='store', default=False,
                     help='set true if given update_bin is a delta image')
    parser.addoption('--local_binary', action='store', help='local linux client binary path')
    parser.addoption('--use_one_apikey', action='store_true', default=False, help='do not create temp api key')
    parser.addoption('--manifest_version', action='store', default='v1', help='manifest template version')
    parser.addoption('--fw_version', action='store', default=None, help='firmware version')

def pytest_report_teststatus(report):
    """
    Hook for collecting test results during the test run for the summary
    :param report: pytest test report
    :return:
    """
    error_rep = ''
    test_result = {'test_name': report.nodeid,
                   'result': report.outcome,
                   'when': report.when,
                   'duration': report.duration,
                   'error_msg': error_rep}
    if report.outcome == 'failed':
        if report.longrepr:
            for line in str(report.longrepr).splitlines():
                if line.startswith('E       '):
                    error_rep += '{}\n'.format(line)
            error_rep += '{}\n'.format(str(report.longrepr).splitlines()[-1])
        test_result['error_msg'] = error_rep
        if report.when == 'teardown':
            pytest.global_test_results.pop()
        pytest.global_test_results.append(test_result)
    else:
        if report.when == 'call':
            pytest.global_test_results.append(test_result)


def pytest_sessionfinish():
    """
    Hook for writing the test result summary to console log after the test run
    """
    if pytest.global_test_results != []:
        log.info('-----  TEST RESULTS SUMMARY  -----')
        if any(resp['result'] == 'failed' for resp in pytest.global_test_results):
            log.info('[ check the complete fail reasons and code locations from this log or html report ]')
        for resp in pytest.global_test_results:
            result = resp['result']
            if result == 'failed':
                result = result.upper()
            log.info('[{}] - {} - ({:.3f}s)'.format(result, resp['test_name'], resp['duration']))
            if resp['error_msg'] != '':
                take_these = 3
                for line in resp['error_msg'].splitlines():
                    if take_these > 0:
                        log.info(line)
                    else:
                        log.info('E ---8<--- Error log summary cut down to few lines, '
                                 'check full log above or from html report ---8<---\n')
                        break
                    take_these -= 1
