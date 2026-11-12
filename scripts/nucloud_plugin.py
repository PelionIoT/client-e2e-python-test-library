"""Binds the suite to a read-only stage. Loaded with -p nucloud_plugin.

Every case that needs a device stays collected and skipped with its cause, so a
run reports the whole suite, and the guard refuses any request but GET and OPTIONS
at the requests layer, so a selection mistake cannot reach the stage.
"""
import os

import pytest
import requests

READ_ONLY = os.environ.get("NUCLOUD_READ_ONLY") == "1"
DEVICE_CASES = "blocked: bootstrapping a device is a write: the stage is read-only"


def guard_writes():
    send = requests.sessions.Session.request

    def request(self, method, url, *args, **kwargs):
        if method.upper() not in ("GET", "OPTIONS"):
            raise AssertionError(
                "read-only stage: refusing {} {}".format(method, url)
            )
        return send(self, method, url, *args, **kwargs)

    requests.sessions.Session.request = request


if READ_ONLY:
    guard_writes()


def pytest_collection_modifyitems(items):
    if READ_ONLY:
        for item in items:
            if "dev-client-tests" in str(item.fspath):
                item.add_marker(pytest.mark.skip(reason=DEVICE_CASES))
