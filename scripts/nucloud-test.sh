#!/bin/sh
# Runs the client tests against the stage in NUCLOUD_API_URL, with a simulated device as
# --local_binary on every stage. A stage listed under [nucloud] read_only sets NUCLOUD_READ_ONLY=1:
# scripts/nucloud_plugin.py then skips the device cases and guards every request. SUITES holds pytest arguments; a word NAME=value sets an
# environment variable.
set -eu
: "${NUCLOUD_API_URL:?make test sets it}" "${NUCLOUD_API_KEY:?make test sets it}"
# The simulated device uses TCP unless the stage's TCP bootstrap host has no DNS answer; UDP reaches
# the same bootstrap service.
if [ -z "${MBED_CLOUD_CLIENT_TRANSPORT:-}" ] && ! python3 - <<'PY'
import json, os, socket, sys, urllib.request
from urllib.parse import urlsplit
request = urllib.request.Request(os.environ['NUCLOUD_API_URL'].rstrip('/') + '/v3/server-credentials',
                                 headers={'Authorization': 'Bearer ' + os.environ['NUCLOUD_API_KEY']})
with urllib.request.urlopen(request, timeout=30) as response:
    boot = json.load(response)['bootstrap']
uri = boot.get('urls', {}).get('coaps', {}).get('tcp') or boot['url']
try:
    socket.getaddrinfo(urlsplit(uri).hostname, None)
except socket.gaierror:
    print('tcp bootstrap host does not resolve: ' + uri + ' - the simulated device uses UDP', file=sys.stderr)
    sys.exit(1)
PY
then
    export MBED_CLOUD_CLIENT_TRANSPORT=UDP
fi
scripts/nucloud-setup.py >/dev/null
export CLOUD_API_GW="${NUCLOUD_API_URL%/}" CLOUD_API_KEY="$NUCLOUD_API_KEY"
selection=
for word in ${SUITES:-}; do
    case $word in
        [A-Z]*=*) export "$word" ;;
        *) selection="$selection $word" ;;
    esac
done
suite="tests/dev-client-tests.py tests/read-only-tests.py"
if [ "${NUCLOUD_READ_ONLY:-}" = 1 ]; then
    exec scripts/nucloud-run.py pytest -v -rs -p no:cacheprovider -p nucloud_plugin $suite $selection
fi
work=$(mktemp -d)
export SIMULATED_CLIENT_CERT_DIR=$work
python3 simulated_client/provision.py create "$work"
trap 'python3 simulated_client/provision.py delete "$work"' EXIT
# A simulated device applies no firmware and checks no signature, so random bytes serve.
head -c 65536 /dev/urandom > "$work/update.bin"
(cd "$work" && manifest-dev-tool init -u "$CLOUD_API_GW" >/dev/null)
scripts/nucloud-run.py pytest -v -rs -p no:cacheprovider -p nucloud_plugin $suite \
    --local_binary="$PWD/simulated_client/client0" --update_bin="$work/update.bin" \
    --manifest_tool="$work" --manifest_version=v1 $selection
