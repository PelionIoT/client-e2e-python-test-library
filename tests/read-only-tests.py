"""
Cases that send only GET, so a stage that takes no writes can run the library.
Copyright (c) 2026 Izuma Networks

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

import os
import pytest

NO_DEVICE = "0" * 32


def test_get_device(cloud):
    listed = cloud.rest_api.get(
        "/v3/devices?limit=2", expected_status_code=200
    ).json()["data"]
    if not listed:
        pytest.skip("the account has no devices")
    device = cloud.device_directory.get_device(
        listed[0]["id"], expected_status_code=200
    ).json()
    assert device["id"] == listed[0]["id"]
    assert device["account_id"] == listed[0]["account_id"]


def test_get_missing_device(cloud):
    cloud.device_directory.get_device(NO_DEVICE, expected_status_code=404)


def test_get_update_campaigns(cloud):
    response = cloud.update.get_update_campaigns(
        expected_status_code=[200, 404]
    )
    if response.status_code == 404:
        pytest.skip("blocked: the stage has no /v3/update-campaigns route")
    assert response.json()["object"] == "list"


@pytest.mark.skipif(
    os.environ.get("NUCLOUD_READ_ONLY") != "1",
    reason="only a read-only stage has a guard",
)
def test_guard_refuses_a_write(cloud):
    with pytest.raises(AssertionError, match="read-only stage"):
        cloud.account.create_api_key({"name": "never-created"})
