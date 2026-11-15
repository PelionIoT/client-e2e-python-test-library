"""Build and run original SDK device cases with a private native MCCE."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

source = Path('/root/mbed-cloud-client-example')
credentials = source / 'mbed_cloud_dev_credentials.c'
credentials.write_bytes(Path('/tmp/native-credentials.c').read_bytes())
credentials.chmod(0o600)
with (source / 'define.txt').open('a') as handle:
    handle.write('\nadd_definitions(-DMBED_CONF_APP_DEVELOPER_MODE=1)\n')
subprocess.run(['cmake', '--build', str(source / '__x86_x64_NativeLinux_mbedtls'), '--target', 'mbedCloudClientExample.elf', '--', '-j4'], check=True)
binary = source / '__x86_x64_NativeLinux_mbedtls/Release/mbedCloudClientExample.elf'
private = Path('/tmp/sdk-native-device')
private.mkdir(mode=0o700)
shutil.copyfile(binary, private / 'client.elf')
(private / 'client.elf').chmod(0o700)
launcher = private / 'client.sh'
launcher.write_text('#!/bin/sh\ncd /tmp/sdk-native-device\nexec ./client.elf\n')
launcher.chmod(0o700)
receipt = {'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'binary_bytes': binary.stat().st_size, 'client_ref': '660b30701cc27a412d9e7ec88b885b3caaff3dd2', 'console_field_mapping': 'Device ID -> endpoint_id; no synthetic output', 'scope': 'native registration; no firmware activation proof'}
Path('/nucloud-evidence/native.json').write_text(json.dumps(receipt))
words = shlex.split(os.environ['SUITES'])
selection = [x for x in words if x != 'NATIVE_MCCE=1']
allowed = {'tests/dev-client-tests.py::test_01_get_device_id'}
if not selection or not set(selection) <= allowed:
    raise ValueError('native MCCE first proof requires the explicit original registration case')
os.environ['CLOUD_API_GW'] = os.environ['NUCLOUD_API_URL'].rstrip('/')
os.environ['CLOUD_API_KEY'] = os.environ['NUCLOUD_API_KEY']
raise SystemExit(subprocess.call([sys.executable, 'scripts/nucloud-run.py', sys.executable, '-m', 'pytest', '-v', '-rs', '-p', 'no:cacheprovider', '-p', 'nucloud_plugin', '-p', 'nucloud_native_mcce', '--local_binary=' + str(launcher)] + selection))
