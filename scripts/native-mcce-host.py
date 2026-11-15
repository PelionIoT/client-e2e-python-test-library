"""Own the native SDK runtime and its exact developer certificate."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import uuid

PROVIDER = 'ghcr.io/izumanetworks/onprem-tester:pre-nucloud-nucloud.dev.1435f66.58dd282'
api_url = os.environ['NUCLOUD_API_URL'].rstrip('/')
parsed = urlsplit(api_url)
if parsed.scheme != 'https' or not parsed.hostname or parsed.hostname.endswith('mbedcloud.com'):
    raise ValueError('native SDK requires an authorized HTTPS test origin')
run = os.environ.get('NUCLOUD_RUN_ID') or uuid.uuid4().hex
if not all(c.isalnum() or c in '._-' for c in run):
    raise ValueError('invalid run identity')
root = Path.cwd()
evidence = root / '.nucloud-logs' / 'native-mcce' / run
evidence.mkdir(parents=True, exist_ok=True, mode=0o700)
for retained in evidence.parent.glob('*/ownership.json'):
    if json.loads(retained.read_text()).get('status') != 'certificate-absent':
        raise RuntimeError('unresolved native ownership receipt: ' + str(retained))
fence = evidence / 'ownership.json'
if fence.exists():
    raise RuntimeError('existing native ownership receipt requires reconciliation')
name = 'nucloud-sdk-mcce-' + uuid.uuid4().hex[:12]
receipt = {'container': name, 'api_origin': api_url, 'status': 'certificate-request-pending'}
def persist():
    descriptor = os.open(str(fence), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        json.dump(receipt, handle); handle.flush(); os.fsync(handle.fileno())
def api(method, path, body=None):
    request = urllib.request.Request(api_url + path, method=method, data=None if body is None else json.dumps(body).encode(), headers={'Authorization': 'Bearer ' + os.environ['NUCLOUD_API_KEY'], 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()
    return json.loads(data) if data else {}
persist()
account = api('GET', '/v3/accounts/me')
if os.environ.get('NUCLOUD_ACCOUNT_ID') and account['id'] != os.environ['NUCLOUD_ACCOUNT_ID']:
    raise ValueError('selected account identity differs from authenticated key')
receipt['expected_account_id'] = account['id']; persist()
certificate = api('POST', '/v3/developer-certificates', {'name': name})
receipt.update(certificate_id=certificate['id'], account_id=certificate['account_id'], status='certificate-created')
if certificate['account_id'] != account['id']:
    receipt['status'] = 'certificate-account-mismatch'; persist()
    raise RuntimeError('certificate creation returned another account; reconcile exact receipt')
persist()
created = False
code = 2
try:
    with tempfile.TemporaryDirectory(prefix='sdk-native-source-') as directory:
        work = Path(directory)
        archive = work / 'source.tar'
        with archive.open('wb') as handle:
            subprocess.run(['git', 'archive', 'HEAD'], stdout=handle, check=True)
        credentials = work / 'credentials.c'
        credentials.write_text(certificate['security_file_content']); credentials.chmod(0o600)
        command = ('mkdir -p /work/sdk /nucloud-evidence; tar -xf /tmp/sdk-source.tar -C /work/sdk; cd /work/sdk; '
                   'python3 -m pip install -q --no-cache-dir -r requirements.txt; '
                   'export PYTHONPATH=/work/sdk:/work/sdk/scripts; exec python3 scripts/native-mcce-runtime.py')
        args = ['docker', 'create', '--init', '--name', name, '--platform', 'linux/amd64', '--label', 'nucloud.owner=abidjan-sdk-native']
        for key in ('NUCLOUD_API_URL', 'NUCLOUD_API_KEY', 'NUCLOUD_STAGE', 'NUCLOUD_ACCOUNT_ID', 'NUCLOUD_RUN_ID', 'SUITES'):
            args += ['-e', key]
        args += [PROVIDER, 'sh', '-ec', command]
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL); created = True
        subprocess.run(['docker', 'cp', str(archive), name + ':/tmp/sdk-source.tar'], check=True)
        subprocess.run(['docker', 'cp', str(credentials), name + ':/tmp/native-credentials.c'], check=True)
        def stop(signum, frame):
            subprocess.run(['docker', 'stop', '-t', '20', name], stdout=subprocess.DEVNULL)
            raise SystemExit(128 + signum)
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(signum, stop)
        subprocess.run(['docker', 'start', '-a', name])
        code = int(subprocess.check_output(['docker', 'inspect', '-f', '{{.State.ExitCode}}', name], text=True))
finally:
    if created:
        subprocess.run(['docker', 'cp', name + ':/nucloud-evidence/.', str(evidence)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['docker', 'rm', '-fv', name], check=True, stdout=subprocess.DEVNULL)
        receipt['runtime_removed'] = True
    identity = receipt['certificate_id']
    try:
        api('DELETE', '/v3/trusted-certificates/' + identity)
    except urllib.error.HTTPError as error:
        if error.code != 404: raise
    try:
        api('GET', '/v3/trusted-certificates/' + identity)
    except urllib.error.HTTPError as error:
        if error.code != 404: raise
    else:
        raise RuntimeError('exact native certificate remains')
    receipt['status'] = 'certificate-absent'; receipt['exit_code'] = code; persist()
    print('NATIVE_MCCE_CLEANUP', identity, '404', name, flush=True)
raise SystemExit(code)
