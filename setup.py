"""
Copyright 2019-2022 Pelion.
Copyright 2022-2023 Izuma Networks

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

from setuptools import setup

PACKAGE_NAME = "client_test_lib"
PACKAGE_LIST = [
    "client_test_lib",
    "client_test_lib.cloud",
    "client_test_lib.cloud.libraries",
    "client_test_lib.cloud.libraries.rest_api",
    "client_test_lib.fixtures",
    "client_test_lib.helpers",
    "client_test_lib.tools",
]

AUTHORS = "DM devops and SRE"
AUTHOR_EMAILS = "opensource@izumanetworks.com"

with open("requirements.txt") as f:
    required = f.read().splitlines()

setup(
    name=PACKAGE_NAME,
    use_scm_version={"root": "."},
    setup_requires=["setuptools_scm==3.2.0"],
    description="Client E2E Python Test Library",
    author=AUTHORS,
    author_email=AUTHOR_EMAILS,
    maintainer=AUTHORS,
    maintainer_email=AUTHOR_EMAILS,
    url="git@github.com:PelionIoT/client-e2e-python-test-library.git",
    license="Apache-2.0",
    packages=PACKAGE_LIST,
    install_requires=required,
)
