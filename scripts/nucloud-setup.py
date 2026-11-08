#!/usr/bin/env python3
"""make setup: verify the stage is not production and serves a non-production bootstrap.

The suite owns no persistent fixtures: nucloud-test.sh provisions a simulated
device certificate per run on k3s-* stages and deletes it on exit.
"""
import json, os, sys, urllib.request
from urllib.parse import urlparse

api = os.environ['NUCLOUD_API_URL'].rstrip('/')
# client_test_lib defaults to production; this suite never runs there.
if (urlparse(api).hostname or '').endswith('mbedcloud.com'):
    sys.exit('setup: refusing production API ' + api)
request = urllib.request.Request(api + '/v3/server-credentials',
                                 headers={'Authorization': 'Bearer ' + os.environ['NUCLOUD_API_KEY']})
with urllib.request.urlopen(request, timeout=30) as response:
    bootstrap = json.load(response)['bootstrap']['url']
if 'mbedcloud.com' in bootstrap:
    sys.exit('setup: refusing production bootstrap ' + bootstrap)
print('setup: ' + api + ' serves bootstrap ' + bootstrap)
