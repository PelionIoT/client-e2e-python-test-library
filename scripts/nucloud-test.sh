#!/bin/sh
# Runs the client tests against the stage in NUCLOUD_API_URL, with a simulated device as
# --local_binary. Other stages than k3s run read-only: scripts/nucloud_plugin.py skips the device
# cases and guards every request. SUITES holds pytest arguments; a word NAME=value sets an
# environment variable.
set -eu
: "${NUCLOUD_API_URL:?make test sets it}" "${NUCLOUD_API_KEY:?make test sets it}"
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
case "${NUCLOUD_STAGE:-}" in
    k3s-*) ;;
    *)
        export NUCLOUD_READ_ONLY=1
        exec scripts/nucloud-run.py pytest -v -rs -p no:cacheprovider -p nucloud_plugin $suite $selection ;;
esac
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
