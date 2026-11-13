#!/usr/bin/env python3
"""Clouds and their credentials for a nucloud repo.

Stamped from IzumaNetworks/nucloud templates/nucloud-cloud.py; identical in every
repo. makehelp-nucloud.sh calls it. It reads .iz, then .izlocal, as structured
TOML: a stage is a top-level [machine.<key>] entry with at least one field of its
own; nested tables (.labels, .facts, .functions, .resources) are that machine's
metadata. Credentials are encrypted izmachine facts on each cloud, read through
`izmachine fact get --file`; nothing reads izmachine's store or a credential file.

Commands (tab-separated output):
  stages                  <stage> <file> <remote> <note> per machine
  production              one production stage per line
  endpoints               <stage> <api url> per [nucloud] endpoints entry
  clouds                  every stage and endpoint, once each
  api <cloud>             the cloud's API URL
  value <cloud> <FIELD>   one credential value (FIELD as in FIELDS below)
  extra-fields            the fields EXTRA_ACCOUNTS passes per extra account
  kubeconfig <cloud> <path>  the cloud's kubeconfig fact, written mode 600
  check <cloud>...        prereqs lines for each cloud's credentials and API access
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

try:
    import tomllib
except ImportError:  # Python < 3.11
    import tomli as tomllib

LAYERS = ('.iz', '.izlocal')
# Credential field -> fact name under cloud. (ACCOUNT=<name> selects cloud.accounts.<name>.).
FIELDS = {'API_KEY': 'api_key', 'API_URL': 'api_url', 'USER': 'admin_user',
          'PASSWORD': 'admin_password', 'ROOT_USER': 'root_user',
          'ROOT_PASSWORD': 'root_password', 'CONFIG_JSON': 'config_json',
          'ACCOUNT_ID': 'account_id'}
PUBLIC = {'API_URL'}  # every other field must be an encrypted fact
# EXTRA_ACCOUNTS=(<stage>=<name>) in nucloud.env: these fields of cloud.accounts.<name>. reach the suite
# as NUCLOUD_ACCOUNT_<NAME>_<FIELD>, beside the run's own account.
EXTRA_FIELDS = ('API_KEY', 'USER', 'PASSWORD', 'CONFIG_JSON')
# An account without its own root login (both facts) uses the stage's cloud.root_user and cloud.root_password.
ROOT_PAIR = ('ROOT_USER', 'ROOT_PASSWORD')
METADATA = {'labels', 'facts', 'functions', 'resources'}


class Problem(Exception):
    pass


def layers(root='.'):
    """[(filename, parsed TOML)] for the layers present, in merge order."""
    out = []
    for name in LAYERS:
        path = Path(root) / name
        if path.is_file():
            try:
                out.append((name, tomllib.loads(path.read_text())))
            except tomllib.TOMLDecodeError as exc:
                raise Problem(name + ': ' + str(exc))
    return out


def notes(path):
    """{machine: the comment line directly above its [machine.<key>] header}."""
    found, last = {}, ''
    for line in Path(path).read_text().splitlines():
        s = line.strip()
        if s.startswith('#'):
            last = s.lstrip('#').strip()
            continue
        m = re.match(r'\[machine\.("?)([^".\]]+)\1\]$', s)
        if m:
            found[m.group(2)] = last
        if not s or s.startswith('['):
            last = ''
    return found


def machines(root='.'):
    """{stage: {'file', 'remote', 'note', 'fields', 'labels', 'facts'}} merged over the layers.

    A later layer replaces an earlier one field by field; a key whose merged
    table has no field of its own (only nested tables) is not a machine."""
    merged = {}
    for name, data in layers(root):
        table = data.get('machine', {})
        if not isinstance(table, dict):
            raise Problem(name + ': [machine] must be a table')
        comment = notes(Path(root) / name)
        for key, body in table.items():
            if not isinstance(body, dict):
                continue
            row = merged.setdefault(key, {'file': '', 'remote': '', 'note': '', 'fields': {}, 'labels': {}, 'facts': {}})
            own = {k: v for k, v in body.items() if not isinstance(v, dict)}
            if own:
                row['file'] = name
                row['fields'].update(own)
                if comment.get(key):
                    row['note'] = comment[key]
            for sub in ('labels', 'facts'):
                if isinstance(body.get(sub), dict):
                    row[sub].update(body[sub])
    return {k: v for k, v in merged.items() if v['fields']}


def nucloud(root='.'):
    """The merged [nucloud] table: production list and endpoints, a later layer replacing a key."""
    out = {'production': [], 'endpoints': [], 'read_only': []}
    for _, data in layers(root):
        table = data.get('nucloud', {})
        for key in out:
            if key in table:
                if not isinstance(table[key], list) or not all(isinstance(x, str) for x in table[key]):
                    raise Problem('[nucloud] ' + key + ' must be a list of strings')
                out[key] = table[key]
    return out


def endpoints(root='.'):
    out = {}
    for entry in nucloud(root)['endpoints']:
        name, sep, url = entry.partition('=')
        if not sep or not name or not url:
            raise Problem('[nucloud] endpoints entry must be <stage>=<api url>: ' + entry)
        out[name] = url
    return out


def clouds(root='.'):
    seen = list(machines(root))
    return seen + [s for s in endpoints(root) if s not in seen]


def fact_name(field):
    if field not in FIELDS:
        raise Problem('unknown credential field ' + field + ' (one of ' + ' '.join(FIELDS) + ')')
    account = os.environ.get('ACCOUNT')
    return 'cloud.' + ('accounts.' + account + '.' if account else '') + FIELDS[field]


_FACTS = {}


def facts(cloud):
    """{name: metadata row} for the cloud's facts (`izmachine fact list`); no values."""
    if cloud not in _FACTS:
        r = subprocess.run(['izmachine', 'fact', 'list', cloud, '--format', 'json'],
                           capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        if r.returncode:
            raise Problem('izmachine fact list ' + cloud + ' failed')
        _FACTS[cloud] = {row['name']: row for row in json.loads(r.stdout or '{}').get('facts', [])}
    return _FACTS[cloud]


def read_fact(cloud, name, secret):
    """One fact's value through the supported private export; '' when the cloud has no such fact."""
    row = facts(cloud).get(name)
    if not row:
        return ''
    if secret and not row.get('secret'):
        raise Problem(cloud + '/' + name + ' must be an encrypted fact (izmachine fact set --secret)')
    with tempfile.TemporaryDirectory(prefix='nucloud-fact-') as d:
        path = Path(d) / 'value'
        r = subprocess.run(['izmachine', 'fact', 'get', cloud, name, '--file', str(path), '--format', 'json'],
                           capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
        if r.returncode or not path.is_file():
            raise Problem('izmachine fact get ' + cloud + ' ' + name + ' failed')
        return path.read_text().rstrip('\n')


def source(cloud, field):
    """The fact a credential field reads: the account's own, except a root field of an account that lacks
    either root fact, which reads the stage's cloud.root_* (one copy of the root login per stage)."""
    name = fact_name(field)
    if field in ROOT_PAIR and os.environ.get('ACCOUNT') and not all(fact_name(f) in facts(cloud) for f in ROOT_PAIR):
        return 'cloud.' + FIELDS[field]
    return name


def value(cloud, field):
    return read_fact(cloud, source(cloud, field), secret=field not in PUBLIC)


def api(cloud, root='.'):
    return value(cloud, 'API_URL') or endpoints(root).get(cloud) or 'https://api.' + cloud + '.izuma.io'


def lan_address(cloud, root='.'):
    """The machine's LAN address: the source of its default route (guest.ip is a CNI address on k3s).
    The guest and its remote come from `izmachine info`, as stage_vm reads them."""
    info = ['izmachine', 'info', cloud, '--format', 'json'] + (['-f', '.iz'] if (Path(root) / '.iz').is_file() else [])
    r = subprocess.run(info, capture_output=True, text=True, timeout=60, cwd=root, stdin=subprocess.DEVNULL)
    hit = next((g for g in (json.loads(r.stdout).get('guests', []) if not r.returncode and r.stdout.strip() else [])
                if g.get('definition') == cloud and g.get('remote')), None)
    if not hit:
        raise Problem(cloud + ' kubeconfig names the loopback address and ' + cloud + ' is no machine in .iz or .izlocal')
    guest, remote = hit.get('guest', cloud), hit['remote']
    r = subprocess.run(['izmachine', 'direct', 'run', guest, '--provider', 'incus', '--remote', remote, '--format', 'json',
                        '--', 'ip', '-4', 'route', 'get', '1.1.1.1'], capture_output=True, text=True, timeout=180,
                       stdin=subprocess.DEVNULL)
    m = re.search(r'\bsrc (\d+\.\d+\.\d+\.\d+)', json.loads(r.stdout or '{}').get('stdout', '') if not r.returncode else '')
    if not m:
        raise Problem('cannot read ' + guest + "'s address on " + remote + '; is the VM running? (izmachine list)')
    return m.group(1)


def write_kubeconfig(cloud, out, root='.'):
    """The kubeconfig fact, its loopback server replaced by the machine's LAN address and its
    k3s `default` names by the cloud's, written mode 600."""
    text = read_fact(cloud, 'kubeconfig', secret=True)
    if not text.startswith('apiVersion'):
        raise Problem(cloud + ' has no kubeconfig fact: label the machine class = "kubernetes" with a '
                      'kubeconfig_path fact, or izmachine fact set ' + cloud + ' kubeconfig --secret')
    if re.search(r'server: https://(127\.0\.0\.1|localhost)[:/]', text):
        text = re.sub(r'server: https://(127\.0\.0\.1|localhost)', 'server: https://' + lan_address(cloud, root), text)
    text = re.sub(r'(?m)^(\s*(?:- )?(?:name|cluster|user)|current-context): default$',
                  lambda m: m.group(1) + ': ' + cloud, text)
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(text if text.endswith('\n') else text + '\n')


def account_get(url, key):
    """HTTP status of the read-only GET /v3/accounts/me with the key, or an error word.

    curl reads the Authorization header from stdin, so the key is never in a process list."""
    if not url.startswith('https://'):
        return 'not https'
    r = subprocess.run(['curl', '-sS', '-o', '/dev/null', '-w', '%{http_code}', '--proto', '=https', '--max-redirs', '0',
                        '--max-time', '15', '-H', '@-', url.rstrip('/') + '/v3/accounts/me'],
                       input='Authorization: Bearer ' + key + '\n', capture_output=True, text=True, timeout=30)
    code = r.stdout.strip()
    return int(code) if code.isdigit() and code != '000' else 'unreachable'


def color(name):
    return os.environ.get('NUCLOUD_CHECK_' + name, '')


def line(ok, name, text):
    word = 'ok  ' if ok else 'FAIL'
    print('  {}{}{}  {}{:<11}{} {}'.format(color('OK' if ok else 'FAIL'), word, color('OFF'),
                                            color('NAME'), name, color('OFF'), text), flush=True)
    return ok


def check(names, root='.'):
    """One credential line and one access line per cloud; exit status 1 on any failure."""
    wanted = os.environ.get('NUCLOUD_CREDENTIALS', 'API_KEY').split()
    given = os.environ.get('ACCOUNT')
    per_stage = dict(p.split('=', 1) for p in os.environ.get('NUCLOUD_ACCOUNTS', '').split() if '=' in p)
    failed = 0
    for cloud in names:
        account = given or per_stage.get(cloud)  # each stage's own account (ACCOUNTS in nucloud.env)
        if account:
            os.environ['ACCOUNT'] = account
        else:
            os.environ.pop('ACCOUNT', None)
        try:
            rows = facts(cloud)
            missing, plain = [], []
            for field in wanted:
                name = 'kubeconfig' if field == 'KUBECONFIG' else source(cloud, field)
                row = rows.get(name)
                if not row:
                    missing.append(name)
                elif field not in PUBLIC and not row.get('secret'):
                    plain.append(name)
            if missing or plain:
                failed += not line(False, cloud, '; '.join(
                    ([('missing ' + ', '.join(missing))] if missing else []) +
                    ([('not encrypted ' + ', '.join(plain))] if plain else [])))
                continue
            denied = []
            if 'API_KEY' in wanted:
                status = account_get(api(cloud, root), value(cloud, 'API_KEY'))
                if status != 200:
                    denied.append('GET /v3/accounts/me ' + str(status))
            if 'KUBECONFIG' in wanted:
                with tempfile.TemporaryDirectory(prefix='nucloud-kc-') as d:
                    kc = Path(d) / 'kubeconfig'
                    write_kubeconfig(cloud, kc)
                    r = subprocess.run(['kubectl', '--kubeconfig', str(kc), '--request-timeout=10s', 'get', '--raw=/readyz'],
                                       capture_output=True, text=True, timeout=20)
                    if r.returncode or r.stdout.strip() != 'ok':
                        denied.append('kubernetes /readyz')
            what = ', '.join(f.lower() for f in wanted) or 'no credentials'
            if denied:
                failed += not line(False, cloud, what + ' present; denied: ' + ', '.join(denied))
            else:
                failed += not line(True, cloud, what + (' (encrypted facts), read access verified' if wanted else ''))
        except (Problem, OSError, subprocess.SubprocessError, ValueError) as exc:
            failed += not line(False, cloud, str(exc))
    return 1 if failed else 0


def main(argv):
    cmd, args = (argv[0], argv[1:]) if argv else ('', [])
    if cmd == 'stages':
        for name, row in machines().items():
            print('\t'.join((name, row['file'], str(row['fields'].get('remote', '')), row['note'])))
    elif cmd == 'production':
        print('\n'.join(nucloud()['production']))
    elif cmd == 'read-only':
        print('\n'.join(nucloud()['read_only']))
    elif cmd == 'endpoints':
        for name, url in endpoints().items():
            print(name + '\t' + url)
    elif cmd == 'clouds':
        print('\n'.join(clouds()))
    elif cmd == 'api' and len(args) == 1:
        print(api(args[0]))
    elif cmd == 'value' and len(args) == 2:
        print(value(*args), end='')
    elif cmd == 'extra-fields':
        print(' '.join(EXTRA_FIELDS))
    elif cmd == 'env' and len(args) == 1:
        # KEY=VALUE for each credential field the cloud (or ACCOUNT=<name>) holds, for scripts
        # that parse env-style input; read on stdin or a pipe, never written to a file
        for field in FIELDS:
            v = value(args[0], field)
            if v:
                print(field + '=' + v)
    elif cmd == 'kubeconfig' and len(args) == 2:
        write_kubeconfig(*args)
    elif cmd == 'check' and args:
        return check(args)
    else:
        raise Problem('usage: nucloud-cloud.py stages|production|read-only|endpoints|clouds|api <cloud>|value <cloud> <FIELD>|extra-fields|env <cloud>|kubeconfig <cloud> <path>|check <cloud>...')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except (Problem, subprocess.TimeoutExpired) as exc:
        print('error: ' + str(exc), file=sys.stderr)
        sys.exit(1)
