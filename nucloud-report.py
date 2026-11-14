#!/usr/bin/env python3
"""nucloud-report.py: build, check and send this repo's reports and inventory in trackHammer's standard.

Stamped from IzumaNetworks/nucloud templates/nucloud-report.py; identical in every repo. trackHammer owns the
standard; nucloud pins it in nucloud-schemas/ and parses each suite's existing output with nucloud-parse.py (or the
repo's own report-parser.py when nucloud.env says REPORT_PARSER=own). No test changes to be reported.

  nucloud-report.py build --stage S --log FILE --started T --ended T --exit N [--outcome O] [--image REF]
                          [--producer manual|runner|ci] [--run-id ID] --out FILE
      one run as trackhammer.report/v1: cases from the log and the report files it left in .nucloud-logs/<S>/
  nucloud-report.py inventory --out FILE      this repo's cases, tags, vocabulary and about text
  nucloud-report.py validate FILE...          check against the pinned standard (and `trackhammer validate` if found)
  nucloud-report.py send FILE --to URL [--stage S]
      POST to URL/api/v1/<reports|inventory|voids>; on failure keep it in .nucloud-logs/reports/pending/
  nucloud-report.py deliver FILE --to DEST [--stage S]
      validate, then send (DEST is http(s)://...) or copy (DEST is a directory or a .json path); an invalid file
      goes to .nucloud-logs/reports/invalid/ with its violations and is never sent
  nucloud-report.py flush --to URL            send every pending report

REPORT_TOKEN in the environment is sent as a bearer token and never printed. Exit status: 0 when the document
reached its destination or was kept for a later send; 1 when it is invalid; 2 on a usage error. Python 3 standard
library only."""
import argparse
import base64
import datetime
import gzip
import importlib.util
import json
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.dont_write_bytecode = True  # importing the repo's parser leaves no __pycache__ in the repo
ROOT = Path(os.environ.get('NUCLOUD_REPORT_ROOT') or Path.cwd())
HERE = Path(__file__).resolve().parent
SCHEMAS = HERE / 'nucloud-schemas'
SELECTION_VARS = ('SUITES', 'TAGS', 'EXCLUDE_TAGS', 'ACCOUNT', 'ACCOUNTS', 'HSM_FROM', 'HSM_TO')
VERDICT_COUNT = {'pass': 'passed', 'fail': 'failed', 'skipped': 'skipped', 'error': 'errors', 'blocked': 'blocked', 'not_run': 'not_run'}
MAX_DOC = 30 * 1024 * 1024  # trackHammer refuses over 32 MiB; attachments are trimmed below that
ENDPOINT = {'trackhammer.report/v1': 'reports', 'trackhammer.inventory/v1': 'inventory', 'trackhammer.void/v1': 'voids'}


def say(msg):
    print(f'==> report: {msg}', flush=True)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- identity -------------------------------------------------------------------------------------------------

CROCKFORD = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'


def ulid():
    n = (int(time.time() * 1000) << 80) | random.SystemRandom().getrandbits(80)
    return ''.join(CROCKFORD[(n >> (5 * i)) & 31] for i in reversed(range(26)))


def git(*args):
    r = subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ''


def env_file(name):
    """KEY=VALUE lines of a make-style file (nucloud.env, Makefile.nucloud), first assignment wins."""
    out = {}
    p = ROOT / name
    for line in p.read_text(errors='replace').splitlines() if p.exists() else []:
        m = re.match(r'^\s*([A-Z_][A-Z0-9_]*)\s*[:?]?=\s*(.*?)\s*$', line)
        if m and m.group(1) not in out:
            value = re.sub(r'\s+#.*$', '', m.group(2)).strip()  # a trailing comment is not part of the value
            out[m.group(1)] = value[1:-1] if len(value) > 1 and value[0] == value[-1] and value[0] in '"\'' else value
    return out


def repo_identity(image=''):
    remote = git('remote', 'get-url', 'origin')
    remote = re.sub(r'//[^/@]+@', '//', remote)  # never a token embedded in an https remote
    dirty = bool([l for l in git('status', '--porcelain', '--untracked-files=no').splitlines() if l.strip()])
    return {'name': os.environ.get('NUCLOUD_REPO_NAME') or ROOT.name, 'remote': remote,
            'branch': git('rev-parse', '--abbrev-ref', 'HEAD'), 'commit': git('rev-parse', 'HEAD') or 'unknown',
            'dirty': dirty, 'template': env_file('Makefile.nucloud').get('NUCLOUD_VERSION', ''), 'image': image}


def split_tags(value):
    return [t for t in re.split(r'[\s,]+', value or '') if t]


def selection():
    env = {k: os.environ[k] for k in os.environ if (k in SELECTION_VARS or k.endswith('_PARTS')) and os.environ[k]}
    tags, exclude = split_tags(os.environ.get('TAGS')), split_tags(os.environ.get('EXCLUDE_TAGS'))
    env.pop('TAGS', None), env.pop('EXCLUDE_TAGS', None)
    return {'tags': tags, 'exclude_tags': exclude, 'default': not (tags or exclude or env), 'env': env}


def utc(value):
    """An RFC 3339 / epoch value as YYYY-MM-DDTHH:MM:SSZ."""
    if re.fullmatch(r'\d+(\.\d+)?', str(value)):
        d = datetime.datetime.fromtimestamp(float(value), datetime.timezone.utc)
    else:
        d = datetime.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        d = d.replace(tzinfo=d.tzinfo or datetime.timezone.utc)
    return d.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


# --- cases ----------------------------------------------------------------------------------------------------

def tags_module():
    return load(HERE / 'nucloud-tags.py', 'nucloud_tags')


def inventory_ids():
    try:
        t = tags_module()
        return {c: c for c in t.cases(t.vocabulary())}
    except Exception:  # an unreadable tag set leaves ids as the log names them
        return {}


def parser():
    """nucloud-parse.py, or the repo's report-parser.py when REPORT_PARSER=own."""
    which = os.environ.get('REPORT_PARSER') or env_file('nucloud.env').get('REPORT_PARSER', '')
    if which == 'own':
        mod = load(ROOT / 'report-parser.py', 'report_parser')
        return mod.parse
    return load(HERE / 'nucloud-parse.py', 'nucloud_parse').parse_run


def redacted(data):
    """Bytes through nucloud-redact.py (this run's secret values, API keys, private keys masked)."""
    r = subprocess.run([sys.executable, str(HERE / 'nucloud-redact.py')], input=data, capture_output=True)
    if r.returncode != 0:
        raise SystemExit('nucloud-redact.py failed; no report leaves this host unmasked')
    return r.stdout


def packed(kind, data):
    return {'kind': kind, 'encoding': 'gzip+base64', 'data': base64.b64encode(gzip.compress(redacted(data), mtime=0)).decode()}


def run_cases(text, stage, since, exit_code, outcome, ms):
    logs = ROOT / '.nucloud-logs' / stage
    result = 'pass' if exit_code == 0 and outcome == 'completed' else 'timeout' if outcome == 'timeout' else 'fail'
    s, rows, why = parser()(text, ROOT, stage, since, None, inventory_ids(), ms, result)
    if why:  # the log shows no case ran (setup failed, Docker refused): one not-run case says so
        return [{'id': f'suite.{stage}', 'verdict': 'not_run', 'duration_ms': 0, 'message': why}], 'not_run'
    if not rows and s and any(s[:4]):  # the output prints totals but names no case: one case for the whole suite
        verdict = 'pass' if exit_code == 0 and outcome == 'completed' else 'fail'
        return [{'id': f'suite.{stage}', 'verdict': verdict, 'duration_ms': ms,
                 'message': f'the output names no case; its summary: {s[0]} passed, {s[1]} failed, {s[2]} errors, {s[3]} skipped'}], outcome
    if not rows:  # a parser that finds nothing gives a report outside the standard, which is never sent
        return [], outcome
    merged = {}
    for r in rows:
        c = {'id': r['case'], 'verdict': r['verdict'], 'duration_ms': int(r['ms']) if str(r.get('ms', '')).isdigit() else 0}
        if r.get('message'):
            c['message'] = r['message']
        merged.pop(c['id'], None)
        merged[c['id']] = c  # a case the log names twice keeps its last verdict, as nucloud's ledger does
    return list(merged.values()), outcome


def summary(cases):
    out = dict.fromkeys(VERDICT_COUNT.values(), 0)
    for c in cases:
        out[VERDICT_COUNT[c['verdict']]] += 1
    return out


def attachments(stage, log, since):
    logs = ROOT / '.nucloud-logs' / stage
    out, size = [], 0
    files = [('suite-log', log)] if log.exists() else []
    for p in sorted(logs.rglob('*')) if logs.is_dir() else []:
        if not p.is_file() or 'reports' in p.relative_to(logs).parts or p == log or p.stat().st_mtime < since:
            continue
        head = p.read_bytes()[:2048]
        kind = ('robot-xml' if p.suffix == '.xml' and b'<robot' in head else 'junit-xml' if p.suffix == '.xml' and b'<test' in head
                else 'http-log' if p.name == 'http.log' else 'k6-summary' if p.name.startswith('k6') and p.suffix == '.json' else None)
        if kind:
            files.append((kind, p))
    for kind, p in files:
        a = packed(kind, p.read_bytes())
        if size + len(a['data']) > MAX_DOC:  # keep the end of an oversize log, where the summary is
            keep = max(0, MAX_DOC - size) * 3 // 4
            a = packed(kind, b'[trimmed by nucloud-report.py to fit trackHammer\'s size limit]\n' + p.read_bytes()[-keep * 4:])
            if size + len(a['data']) > MAX_DOC:
                continue
        size += len(a['data'])
        out.append(a)
    return out


def build(a):
    log = Path(a.log)
    text = re.sub(r'\x1b\[[0-9;]*m', '', log.read_text(errors='replace')) if log.exists() else ''
    started, ended = utc(a.started), utc(a.ended)
    since = datetime.datetime.fromisoformat(started.replace('Z', '+00:00')).timestamp() - 5
    ms = max(0, int((datetime.datetime.fromisoformat(ended.replace('Z', '+00:00')) - datetime.datetime.fromisoformat(started.replace('Z', '+00:00'))).total_seconds() * 1000))
    cases, outcome = run_cases(text, a.stage, since, a.exit, a.outcome, ms)
    rid = ulid()
    producer = {'kind': a.producer, 'host': socket.gethostname().split('.')[0] or 'host', 'run_id': a.run_id or rid}
    if a.producer == 'ci':
        producer['ci'] = {'provider': os.environ.get('CI_PROVIDER', ''), 'run_url': os.environ.get('CI_RUN_URL', ''), 'job': os.environ.get('CI_JOB', '')}
    doc = {'schema': 'trackhammer.report/v1', 'report_id': rid, 'producer': producer, 'repo': repo_identity(a.image),
           'stage': {'name': a.stage, 'api_url': os.environ.get('NUCLOUD_API_URL', '')}, 'selection': selection(),
           'started_at': started, 'ended_at': ended, 'exit_code': a.exit, 'outcome': outcome,
           'summary': summary(cases), 'cases': cases, 'attachments': attachments(a.stage, log, since)}
    write(a.out, doc)


def write(path, doc):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + '\n')


# --- inventory ------------------------------------------------------------------------------------------------

def readme_paragraph():
    for name in ('README.md', 'README.rst', 'README.txt', 'README'):
        p = ROOT / name
        if not p.is_file():
            continue
        for block in re.split(r'\n\s*\n', p.read_text(errors='replace')):
            raw = block.strip().splitlines()
            lines = [l.strip() for l in raw if l.strip() and not re.match(r'^(#|[=~-]{3,}$|\[!\[|!\[|<|\||```|\.\. |Build and deploy:|(git|source|pip3?|make|cd|python3?|\$) )', l.strip())
                     and not re.match(r'^( {4}|\t)', l)]
            if len(lines) > 1 and raw and re.fullmatch(r'[=~-]{3,}', raw[-1].strip()):
                continue
            if lines and not (len(lines) == 1 and len(lines[0]) < 40 and not lines[0].endswith('.')):
                text = ' '.join(lines)
                return text[:600] + ('…' if len(text) > 600 else '')
    return ''


def derived(tag, voc):
    """A description for a tag neither the vocabulary nor nucloud's facts describe, worded as nucloud's dashboard
    words them (scripts/testing-status.py tag_model)."""
    group, _, name = tag.partition(':')
    if group not in voc.get('open', set()):
        return f'Repository tag of {ROOT.name} (test-tags.local.toml)'
    if group == 'api':
        return f'Calls the `{name}` route family'
    if group == 'service':
        return f'Calls a route the {name} service serves'
    if group == 'fixture':
        return f'Uses the {name} fixture (matched from imports or the case path)'
    return f'Source file or directory `{name}`'


def inventory(a):
    t = tags_module()
    voc = t.vocabulary()
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib
    shared = tomllib.loads((HERE / 'test-tags.toml').read_text())
    facts_path = HERE / 'nucloud-report-facts.json'
    facts = json.loads(facts_path.read_text()) if facts_path.exists() else {'tags': {}, 'repos': {}, 'template_history': []}
    found = t.cases(voc)
    cases = [{'id': c, 'kind': t.KIND.get(c, ''), 'tags': list(tags)} for c, (tags, _, _) in found.items()]
    used = sorted({x for c in cases for x in c['tags']})
    vocabulary = {}
    for name in sorted(set(voc['tags']) | set(used)):
        row = voc['tags'].get(name)
        listed = name in shared.get('tags', {})
        desc = (row or {}).get('means') if listed else (facts['tags'].get(name) or (row or {}).get('means') or derived(name, voc))
        vocabulary[name] = {'group': name.split(':', 1)[0], 'description': desc or '',
                            'default': (row or {}).get('default', 'include'), 'source': (row or {}).get('source', 'classifier' if not row else 'author'),
                            'aliases': list((row or {}).get('aliases', [])), 'listed': listed}
    name = os.environ.get('NUCLOUD_REPO_NAME') or ROOT.name
    about_f = facts['repos'].get(name, {})
    doc = {'schema': 'trackhammer.inventory/v1', 'repo': repo_identity(), 'cases': cases, 'vocabulary': vocabulary,
           'groups': dict(shared.get('groups', {})),
           'about': {'tests': about_f.get('tests', ''), 'readme': about_f.get('readme') or readme_paragraph(),
                     'framework': about_f.get('framework', ''), 'fixtures': list(about_f.get('fixtures', []))}}
    if about_f.get('ledger'):
        doc['ledger'] = {k: about_f['ledger'][k] for k in ('state', 'note', 'name') if k in about_f['ledger']}
    if facts.get('template_history'):
        doc['template_history'] = facts['template_history']
    write(a.out, doc)


# --- validation -----------------------------------------------------------------------------------------------

TYPES = {'object': dict, 'array': list, 'string': str, 'boolean': bool}


def check(value, schema, path, errors):
    """A JSON Schema subset: type, required, properties, additionalProperties, items, enum, const, pattern,
    minLength, minimum, minItems, format date-time."""
    ty = schema.get('type')
    if ty == 'integer':
        if not isinstance(value, int) or isinstance(value, bool):
            return errors.append(f'{path}: must be an integer')
    elif ty == 'number':
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return errors.append(f'{path}: must be a number')
    elif ty and not isinstance(value, TYPES.get(ty, object)):
        return errors.append(f'{path}: must be {ty}')
    if 'const' in schema and value != schema['const']:
        errors.append(f'{path}: must be {schema["const"]!r}')
    if 'enum' in schema and value not in schema['enum']:
        errors.append(f'{path}: {value!r} is not one of {schema["enum"]}')
    if isinstance(value, str):
        if len(value) < schema.get('minLength', 0):
            errors.append(f'{path}: must not be empty')
        if 'pattern' in schema and not re.search(schema['pattern'], value):
            errors.append(f'{path}: {value!r} does not match {schema["pattern"]}')
        if schema.get('format') == 'date-time':
            try:
                datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                errors.append(f'{path}: {value!r} is not an RFC 3339 time')
    if isinstance(value, (int, float)) and not isinstance(value, bool) and 'minimum' in schema and value < schema['minimum']:
        errors.append(f'{path}: must be at least {schema["minimum"]}')
    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0):
            errors.append(f'{path}: needs at least {schema["minItems"]} item(s)')
        for i, item in enumerate(value):
            if isinstance(schema.get('items'), dict):
                check(item, schema['items'], f'{path}[{i}]', errors)
    if isinstance(value, dict):
        props = schema.get('properties', {})
        for k in schema.get('required', []):
            if k not in value:
                errors.append(f'{path}.{k}: required')
        extra = schema.get('additionalProperties', True)
        for k, v in value.items():
            if k in props:
                check(v, props[k], f'{path}.{k}', errors)
            elif extra is False:
                errors.append(f'{path}.{k}: unknown field')
            elif isinstance(extra, dict):
                check(v, extra, f'{path}.{k}', errors)


def semantic(doc, errors):
    if doc.get('schema') != 'trackhammer.report/v1':
        if doc.get('schema') == 'trackhammer.inventory/v1':
            ids = [c.get('id') for c in doc.get('cases', [])]
            for i in sorted({i for i in ids if ids.count(i) > 1}):
                errors.append(f'cases: duplicate id {i!r}')
        return
    ids = [c.get('id') for c in doc.get('cases', []) if isinstance(c, dict)]
    for i in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f'cases: duplicate id {i!r}')
    want = summary([c for c in doc.get('cases', []) if isinstance(c, dict) and c.get('verdict') in VERDICT_COUNT])
    if isinstance(doc.get('summary'), dict) and doc['summary'] != want:
        errors.append(f'summary: {doc["summary"]} does not equal the case verdict counts {want}')
    try:
        if doc['ended_at'] < doc['started_at']:
            errors.append('ended_at: before started_at')
    except (KeyError, TypeError):
        pass
    for i, att in enumerate(doc.get('attachments', [])):
        try:
            gzip.decompress(base64.b64decode(att.get('data', ''), validate=True))
        except Exception:
            errors.append(f'attachments[{i}].data: not base64 of a gzip stream')


def trackhammer_binary():
    for c in (os.environ.get('TRACKHAMMER'), shutil.which('trackhammer'), str(Path.home() / 'workspace/izuma/trackHammer/build/trackhammer')):
        if c and Path(c).is_file() and os.access(c, os.X_OK):
            return c
    return None


def violations(path):
    try:
        doc = json.loads(Path(path).read_text())
    except (OSError, ValueError) as e:
        return [f'not JSON: {e}']
    kind = {'trackhammer.report/v1': 'report', 'trackhammer.inventory/v1': 'inventory', 'trackhammer.void/v1': 'void'}.get(doc.get('schema'))
    if not kind:
        return [f'schema: unknown {doc.get("schema")!r}']
    errors = []
    check(doc, json.loads((SCHEMAS / f'{kind}.schema.json').read_text()), kind, errors)
    semantic(doc, errors)
    th = trackhammer_binary()
    if th and not errors:
        r = subprocess.run([th, 'validate', str(path)], capture_output=True, text=True)
        if r.returncode != 0:
            errors += [f'trackhammer: {l}' for l in (r.stdout + r.stderr).strip().splitlines()]
    return errors


# --- transport ------------------------------------------------------------------------------------------------

def post(path, url):
    doc = json.loads(Path(path).read_text())
    endpoint = url.rstrip('/') + '/api/v1/' + ENDPOINT[doc['schema']]
    req = urllib.request.Request(endpoint, data=Path(path).read_bytes(), method='POST', headers={'Content-Type': 'application/json'})
    if os.environ.get('REPORT_TOKEN'):
        req.add_header('Authorization', 'Bearer ' + os.environ['REPORT_TOKEN'])
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b'{}')
        except ValueError:
            return e.code, {}


def kept(stage, sub, path):
    """A copy of the document in .nucloud-logs/reports/<pending|invalid>/: outside the stage folders, which every
    make test empties, so a report kept for a later send survives the next run."""
    d = ROOT / '.nucloud-logs' / 'reports' / sub
    d.mkdir(parents=True, exist_ok=True)
    dest = d / Path(path).name
    if Path(path).resolve() != dest.resolve():
        shutil.copyfile(path, dest)
    return dest


def send(path, url, stage):
    """POST one document; a refusal by the server (400) is invalid, anything else unreachable keeps it pending."""
    try:
        code, body = post(path, url)
    except (OSError, urllib.error.URLError) as e:
        dest = kept(stage, 'pending', path)
        say(f'{url} unreachable ({getattr(e, "reason", e)}); kept for `make report-send`: {dest.relative_to(ROOT)}')
        return 0
    if code in (200, 201):
        say(f'{"already recorded" if code == 200 else "sent"} {what(path)}: {where(url, body, path)}')
        return 0
    if code == 400:
        dest = kept(stage, 'invalid', path)
        dest.with_suffix('.violations.txt').write_text('\n'.join(body.get('errors') or [str(body)]) + '\n')
        say(f'{url} refused it ({len(body.get("errors") or [])} violation(s)); see {dest.with_suffix(".violations.txt").relative_to(ROOT)}')
        return 1
    dest = kept(stage, 'pending', path)
    say(f'{url} answered {code}; kept for `make report-send`: {dest.relative_to(ROOT)}')
    return 0


def what(path):
    """`run <id> (<n> cases)`, `inventory of <repo> (<n> cases)` or `void of <run>`, for the line a send prints."""
    doc = json.loads(Path(path).read_text())
    if doc.get('schema') == 'trackhammer.inventory/v1':
        return f"inventory of {doc['repo']['name']} ({len(doc.get('cases', []))} cases)"
    if doc.get('schema') == 'trackhammer.void/v1':
        return f"void of {doc.get('run_id') or doc.get('report_id')}"
    return f"run {doc.get('report_id')} ({len(doc.get('cases', []))} cases)"


def where(url, body, path=None):
    """The page that shows what was sent: the run's URL from the answer, or the repository's page for an inventory."""
    doc = json.loads(Path(path).read_text()) if path else {}
    if doc.get('schema') == 'trackhammer.inventory/v1':
        return url.rstrip('/') + '/#repo/' + doc['repo']['name']
    u = body.get('url') or ''
    return url.rstrip('/') + '/' + u.lstrip('/') if re.search(r'#run/\S+', u) else url


def deliver(path, dest, stage):
    errors = violations(path)
    if errors:
        bad = kept(stage, 'invalid', path)
        bad.with_suffix('.violations.txt').write_text('\n'.join(errors) + '\n')
        say(f'not sent: {len(errors)} violation(s) of the standard; see {bad.with_suffix(".violations.txt").relative_to(ROOT)}')
        return 1
    if re.match(r'^https?://', dest):
        return send(path, dest, stage)
    out = Path(dest)
    if not out.is_absolute():
        out = ROOT / out
    if out.suffix != '.json':
        out.mkdir(parents=True, exist_ok=True)
        out = out / Path(path).name
    out.parent.mkdir(parents=True, exist_ok=True)
    if Path(path).resolve() != out.resolve():
        shutil.copyfile(path, out)
    say(f'written: {out}')
    return 0


def flush(url):
    pending = sorted((ROOT / '.nucloud-logs/reports/pending').glob('*.json'))
    if not pending:
        say('nothing pending')
        return 0
    rc = 0
    for p in pending:
        stage = ''
        try:
            code, body = post(p, url)
        except (OSError, urllib.error.URLError) as e:
            say(f'{url} unreachable ({getattr(e, "reason", e)}); {len(pending)} report(s) stay pending')
            return 0
        if code in (200, 201):
            say(f'{"already recorded" if code == 200 else "sent"} {what(p)}: {where(url, body, p)}')
            p.unlink()
        elif code == 400:
            bad = kept(stage, 'invalid', p)
            bad.with_suffix('.violations.txt').write_text('\n'.join(body.get('errors') or [str(body)]) + '\n')
            p.unlink()
            say(f'{url} refused {p.name}; moved to {bad.relative_to(ROOT)}')
            rc = 1
        else:
            say(f'{url} answered {code} for {p.name}; it stays pending')
    return rc


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--stage', required=True)
    b.add_argument('--log', required=True)
    b.add_argument('--started', required=True)
    b.add_argument('--ended', required=True)
    b.add_argument('--exit', type=int, required=True)
    b.add_argument('--outcome', default='completed', choices=('completed', 'timeout', 'interrupted', 'not_run'))
    b.add_argument('--image', default='')
    b.add_argument('--producer', default=os.environ.get('REPORT_PRODUCER', 'manual'), choices=('manual', 'runner', 'ci'))
    b.add_argument('--run-id', default=os.environ.get('NUCLOUD_REPORT_RUN_ID', ''))
    b.add_argument('--out', required=True)
    i = sub.add_parser('inventory')
    i.add_argument('--out', required=True)
    v = sub.add_parser('validate')
    v.add_argument('files', nargs='+')
    for name in ('send', 'deliver'):
        s = sub.add_parser(name)
        s.add_argument('file')
        s.add_argument('--to', required=True)
        s.add_argument('--stage', default='')
    f = sub.add_parser('flush')
    f.add_argument('--to', required=True)
    a = ap.parse_args(argv)
    if a.cmd == 'build':
        build(a)
    elif a.cmd == 'inventory':
        inventory(a)
    elif a.cmd == 'validate':
        rc = 0
        for p in a.files:
            errors = violations(p)
            print(f'{p}: ' + ('valid' if not errors else f'{len(errors)} violation(s)'))
            for e in errors:
                print('  ' + e)
            rc |= bool(errors)
        return rc
    elif a.cmd == 'send':
        return send(a.file, a.to, a.stage)
    elif a.cmd == 'deliver':
        return deliver(a.file, a.to, a.stage)
    elif a.cmd == 'flush':
        return flush(a.to)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
