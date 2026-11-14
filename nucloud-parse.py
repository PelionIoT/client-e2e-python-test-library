#!/usr/bin/env python3
"""nucloud-parse.py: one run's per-case verdicts from the output a suite already prints and the report files it
already writes. Stamped into every test repo by nucloud; nucloud's runner (scripts/testing-full-run.py) and the
repo's report builder (nucloud-report.py) both use it, so a run is parsed one way everywhere. No test changes to
suit it: it reads pytest, behave, Cucumber-JVM, Maven/JUnit XML, Go test, mocha/karma, unittest, icetea and robot
output, and judges a suite it cannot read by its exit code.

A repo whose output none of these read carries its own report-parser.py with
    parse(text, repo, stage, since, snapshot, inventory, ms, result) -> (summary, rows, never_ran)
the same contract as parse_run() below. Python 3, standard library only."""
import datetime
import json
import os
import re
import time

NEVER_RAN = [
    (r'^setup: .* failed on \S+ \(exit \d+\); the suite did not run', 'setup failed; no case ran'),
    (r'^missing local FCC/FCU provider image: ', 'FCC/FCU provider image missing on the Docker host; no case ran'),
    (r'^cv part: no (?:case ran|behave summary)', 'secsrv cv part ran no case'),
    (r'Docker engine SSH socket tunnel exited before readiness', 'docker host refused the session; no case ran'),
    (r'Session open refused by peer|dial-stdio\b.*exit(ed with)? status 255|Cannot connect to the Docker daemon',
     'docker host refused the session; no case ran'),
    (r'Permission denied \(publickey\)', 'SSH key refused before any case ran'),
    (r'^ERROR: failed to (?:solve|build)\b|^ERROR: error during connect', 'image build failed; no case ran'),
]



def never_ran(text):
    """The reason a log shows no case ran (Docker host refused, SSH key refused, image build failed), or None."""
    if case_verdicts(text):
        return None
    for pattern, why in NEVER_RAN:
        if re.search(pattern, text, re.M):
            return why
    return None


def summary(text):
    """(passed, failed, errors, skipped, label) from the last framework summary in the log, or None."""
    found = []
    for m in re.finditer(r'^(?:=+ | ?)(\d+ (?:passed|failed|error|skipped|deselected).*?|.*?no tests ran.*?) in [\d.]+ ?s(?:econds)?\b', text, re.M):
        c = dict((k, int(n)) for n, k in re.findall(r'(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)', m.group(1)))
        found.append((c.get('passed', 0) + c.get('xpassed', 0), c.get('failed', 0), c.get('error', 0) + c.get('errors', 0),
                      c.get('skipped', 0) + c.get('xfailed', 0), 'pytest'))
    part_re = r'^([a-z][\w-]*): (\d+) scenarios? passed, (\d+) failed, (\d+) skipped\s*$'
    for m in re.finditer(part_re, text, re.M):  # a multi-part runner's own total per part: `hsm: 5 scenarios passed, ...`
        blocked = re.findall(rf'^{re.escape(m.group(1))} blocked: (\d+)\s*$', text, re.M)
        found.append((int(m.group(2)), int(m.group(3)), int(blocked[-1]) if blocked else 0, int(m.group(4)), 'part'))
    for m in re.finditer(r'(?<!\d)(\d+) scenarios? passed, (\d+) failed, (?:(\d+) error, )?(\d+) skipped', text):
        if re.match(part_re, text[text.rfind('\n', 0, m.start()) + 1:].split('\n', 1)[0]):
            continue  # a part total, counted above
        found.append((int(m.group(1)), int(m.group(2)), int(m.group(3) or 0), int(m.group(4)), 'behave'))
    for m in re.finditer(r'^(\d+) Scenarios? \(([^)]*)\)', text, re.M):
        c = dict((k, int(n)) for n, k in re.findall(r'(\d+) (passed|failed|skipped|undefined|pending)', m.group(2)))
        found.append((c.get('passed', 0), c.get('failed', 0), c.get('undefined', 0) + c.get('pending', 0), c.get('skipped', 0), 'cucumber'))
    tr = [m for m in re.finditer(r'Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)(?!.*- in )', text)]
    if tr:
        m = tr[-1]
        run_, f, e, s = map(int, m.groups())
        # Cucumber-JVM under surefire prints its scenarios twice, as Cucumber's line and in JUnit's total: keep JUnit's
        cuc = [row for row in found if row[4] == 'cucumber']
        if cuc and run_ >= sum(sum(row[:4]) for row in cuc):
            found = [row for row in found if row[4] != 'cucumber']
        found.append((run_ - f - e - s, f, e, s, 'junit'))
    for m in re.finditer(r'^junit total: (\d+) run, (\d+) failed\s*$', text, re.M):  # nucloud-junit.sh beside a pytest suite
        found.append((int(m.group(1)) - int(m.group(2)), int(m.group(2)), 0, 0, 'junit'))
    for m in re.finditer(r'^counts: pass (\d+) fail (\d+) blocked (\d+)(?: disabled-upstream (\d+))?\s*$', text, re.M):  # nucloud_cases.js
        found.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4) or 0), 'summary'))
    for m in re.finditer(r'^RESULT pass=(\d+) fail=(\d+)(?: not_run=(\d+))?', text, re.M):  # nucloud exit runners
        found.append((int(m.group(1)), int(m.group(2)), 0, int(m.group(3) or 0), 'summary'))
    for m in re.finditer(r'^nucloud-summary passed=(\d+) failed=(\d+) skipped=(\d+)\s*$', text, re.M):  # connect-tests, unit tests included
        found.append((int(m.group(1)), int(m.group(2)), 0, int(m.group(3)), 'summary'))
    for m in re.finditer(r'^nucloud-summary: \d+ run, (\d+) passed, (\d+) failed, (\d+) skipped', text, re.M):
        found.append((int(m.group(1)), int(m.group(2)), 0, int(m.group(3)), 'summary'))
    for m in re.finditer(r'^(?:\w+: )?(\d+) passed, (\d+) failed, (\d+) blocked\s*$', text, re.M):  # per-section exit runners
        found.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), 0, 'summary'))
    if re.search(r'^part +pass +fail +skip +notrun\s*$', text, re.M):  # nucloud-summary.py's per-part table
        for m in re.finditer(r'^total +(\d+) +(\d+) +(\d+) +(\d+)\s*$', text, re.M):
            found.append((int(m.group(1)), int(m.group(2)), 0, int(m.group(3)) + int(m.group(4)), 'summary'))
    karma = {}
    for m in re.finditer(r'^TOTAL: (?:(\d+) FAILED, )?(\d+) SUCCESS', text, re.M):  # karma prints its total once per reporter
        karma[m.group(0)] = (int(m.group(2)), int(m.group(1) or 0), 0, 0, 'karma')
    found.extend(karma.values())
    for m in re.finditer(r'^Ran (\d+) tests? in [\d.]+s\s*\n\s*\n?(OK|FAILED)(?: \(([^)]*)\))?', text, re.M):  # unittest
        c = dict((k, int(n)) for k, n in re.findall(r'(failures|errors|skipped|expected failures)=(\d+)', m.group(3) or ''))
        n = int(m.group(1))
        found.append((n - c.get('failures', 0) - c.get('errors', 0) - c.get('skipped', 0), c.get('failures', 0), c.get('errors', 0), c.get('skipped', 0), 'unittest'))
    for m in re.finditer(r'^SUMMARY (.*)$', text, re.M):  # nucloud runners' own line: SUMMARY passed=N failed=M ...
        c = dict((k, int(n)) for k, n in re.findall(r'(passed|failed|errors?|skipped|not_run)=(\d+)', m.group(1)))
        found.append((c.get('passed', 0), c.get('failed', 0), c.get('error', 0) + c.get('errors', 0), c.get('skipped', 0) + c.get('not_run', 0), 'summary'))
    for m in re.finditer(r'leaf counts: (\{[^}]*\})', text):  # runners that report per suite family as JSON
        try:
            c = json.loads(m.group(1))
        except ValueError:
            continue
        found.append((c.get('passed', 0), c.get('failed', 0), c.get('errors', 0), c.get('skipped', 0) + c.get('not_run', 0), 'summary'))
    go = re.findall(r'^\s*--- (PASS|FAIL|SKIP): ', text, re.M)
    if go:
        found.append((go.count('PASS'), go.count('FAIL'), 0, go.count('SKIP'), 'go'))
    p, f = re.findall(r'^\s*(\d+) passing', text, re.M), re.findall(r'^\s*(\d+) failing', text, re.M)
    if p or f:
        pend = re.findall(r'^\s*(\d+) pending', text, re.M)
        found.append((sum(map(int, p)), sum(map(int, f)), 0, sum(map(int, pend)), 'mocha'))
    if not found:
        return None
    if any(row[4] == 'part' for row in found):  # per-part totals cover every framework line inside the parts
        found = [row for row in found if row[4] == 'part']
    elif any(row[4] == 'summary' for row in found):  # the runner's own total already covers its frameworks' lines
        found = [row for row in found if row[4] == 'summary']
    # several summaries in one log (one per suite folder): add them up per framework
    total = [0, 0, 0, 0]
    labels = set()
    for row in found:
        for i in range(4):
            total[i] += row[i]
        labels.add(row[4])
    return (*total, '+'.join(sorted(labels)))


def case_verdicts(text):
    out = {}
    for case, v in re.findall(r'^(\S+::[^\s\[]+(?:\[[^\n]*?\])?)(?: <- \S+)? (PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\b', text, re.M):  # `<- base.py`: inherited test
        out[case] = v
    pending = None  # pytest live logging: the id line, the case's log output, then the verdict on a line of its own
    for line in text.split('\n'):
        # pytest -s: the case's own output can follow its id on the same line (`x.py::test read EC key`)
        m = (re.match(r'^(\S+::[^\s\[]+?(?:\[[^\n]*?\])?)(?: (PASSED|FAILED|ERROR|SKIPPED)\b.*)?\s*$', line)
             or re.match(r'^([\w./-]+\.py::[^\s\[]+(?:\[[^\n]*?\])?)() (?!<- )(?!.*\b(?:PASSED|FAILED|ERROR|SKIPPED)\b)', line))
        if m and '::' in m.group(1) and not m.group(1).startswith(('go::', 'case::')):
            pending = None if m.group(2) else m.group(1)
            continue
        # a pytest log record (`ERROR    helper:helper.py:175 Output: ...`) is not the pending case's verdict
        v = re.match(r'^(PASSED|FAILED|ERROR|SKIPPED)\b(?! \S+::)(?!\s+\S+:\S+\.py:\d+)', line)
        if v and pending:
            out.setdefault(pending, v.group(1))
            pending = None
    for v, case in re.findall(r'^(PASSED|FAILED|ERROR|SKIPPED) (\S+::[^\s\[]+(?:\[[^\n]*?\])?)', text, re.M):
        out.setdefault(case, v)
    for v, case in re.findall(r'^\s*--- (PASS|FAIL|SKIP): (\S+)', text, re.M):
        out['go::' + case] = v
    tiered = re.compile(r'^(PASS|FAIL|BLOCKED|SKIP) (\w+: [^:\n]+?)(?::|\s*$)', re.M)
    for v, case in tiered.findall(text):  # exit runners' per-case lines: `PASS <tier>: <name>`
        out['case::' + case] = {'PASS': 'PASSED', 'FAIL': 'FAILED', 'BLOCKED': 'ERROR', 'SKIP': 'SKIPPED'}[v]
    for line in text.split('\n'):  # `FAIL edge kaas: <reason>`: a lower-case probe name, then its reason
        m = re.match(r'^(PASS|FAIL|BLOCKED|SKIP) ([a-z][a-z0-9 _-]{2,40}): ', line)
        if m and not tiered.match(line):
            out.setdefault('case::' + m.group(2), {'PASS': 'PASSED', 'FAIL': 'FAILED', 'BLOCKED': 'ERROR', 'SKIP': 'SKIPPED'}[m.group(1)])
    for v, case in re.findall(r'^(PASS|FAIL|BLOCKED|SKIP) ([\w./-]+(?:::[\w.-]+)?(?:\[[^\]\s]*\])?)\s*$', text, re.M):
        out.setdefault(case, {'PASS': 'PASSED', 'FAIL': 'FAILED', 'BLOCKED': 'ERROR', 'SKIP': 'SKIPPED'}[v])  # `PASS id` result lines
    tails = {k[i + 1:] for k in out for i, c in enumerate(k.split('::', 1)[0]) if c == '/'}  # each id under every parent dir
    for v, case in re.findall(r'\[(passed|failed|skipped|error)\] - (\S+::[^\s\[]+(?:\[[^\n]*?\])?) - \(\d', text, re.M | re.I):  # pelion_systest_lib logger
        if case in tails:
            continue  # the logger repeats a case pytest already keyed under its rootdir path
        out.setdefault(case, {'passed': 'PASSED', 'failed': 'FAILED', 'skipped': 'SKIPPED', 'error': 'ERROR'}[v.lower()])
    for v, case in re.findall(r'^[\d:.]+ (PASS|FAIL|BLOCKED|SKIP) \[\d+\] (\S+)\s*$', text, re.M):  # onprem API checks
        out['api::' + case] = {'PASS': 'PASSED', 'FAIL': 'FAILED', 'BLOCKED': 'ERROR', 'SKIP': 'SKIPPED'}[v]
    seen = {}
    for v, method, path in re.findall(r'^(PASS|FAIL|BLOCKED|SKIP) (GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD) (\S+) \d{3}\b', text, re.M):
        # Status-page probes, keyed by route: a record id the run created reads {id}, so two runs name the same case.
        key = 'http::' + method + ' ' + re.sub(r'(?<=/)[0-9a-f]{32}(?=/|$|\?)', '{id}', path)
        seen[key] = seen.get(key, 0) + 1
        out[key + ('' if seen[key] == 1 else f'#{seen[key]}')] = {'PASS': 'PASSED', 'FAIL': 'FAILED', 'BLOCKED': 'ERROR', 'SKIP': 'SKIPPED'}[v]
    for v, case in re.findall(r'^(PASS|FAIL|BLOCKED) (device [^:]+): ', text, re.M):  # pelion-status simulated device probe
        out['probe::' + case] = {'PASS': 'PASSED', 'FAIL': 'FAILED', 'BLOCKED': 'ERROR'}[v]
    for name, where, v in re.findall(r'^(\w+) \(([\w.]+)\) \.\.\. (ok|FAIL|ERROR|skipped|expected failure|unexpected success)\b', text, re.M):
        parts = where.split('.')  # unittest -v: `test_x (module.Class) ... ok`; Python 3.11+ appends `.test_x`
        if parts[-1] == name:
            parts = parts[:-1]
        if parts and parts[0] == '__main__':
            parts = parts[1:]
        out['unittest::' + '::'.join(parts + [name])] = {'ok': 'PASSED', 'FAIL': 'FAILED', 'ERROR': 'ERROR', 'skipped': 'SKIPPED',
                                                         'expected failure': 'SKIPPED', 'unexpected success': 'PASSED'}[v]
    seen_js = {}
    for v, path, rest in re.findall(r'^(PASS|FAIL|BLOCKED) (\S+\.[cm]?[jt]s): (.+)$', text, re.M):  # nucloud_cases.js mocha runner
        title = rest.split('\t', 1)[0] if '\t' in rest else (rest.split(': ', 1)[0] if v != 'PASS' else rest)  # reason after a tab
        key = f'{path}::{title.strip()}'
        seen_js[key] = seen_js.get(key, 0) + 1
        out[key + ('' if seen_js[key] == 1 else f'#{seen_js[key]}')] = {'PASS': 'PASSED', 'FAIL': 'FAILED', 'BLOCKED': 'ERROR'}[v]
    for path, n in re.findall(r'^BLOCKED (\S+\.[cm]?[jt]s) \((\d+)\): ', text, re.M):  # a whole file blocked: one row per case in it
        for k in range(1, int(n) + 1):
            out[f'{path}::case {k}'] = 'ERROR'
    for case, v in re.findall(r'^CASE (\S+) (PASS|FAIL|BLOCKED)\s*$', text, re.M):  # nucloud device-runner `CASE <name> <verdict>`
        out['case::' + case] = {'PASS': 'PASSED', 'FAIL': 'FAILED', 'BLOCKED': 'ERROR'}[v]
    for case, v in re.findall(r'^Gradle suite > Gradle test > (\S+ > .+?) (PASSED|FAILED|SKIPPED)\s*$', text, re.M):
        out['gradle::' + case.replace(' > ', '::')] = v
    cypress = re.split(r'^\s*Running:\s+(\S+\.(?:spec|cy)\.[jt]sx?)\b.*$', text, flags=re.M)
    for spec, block in zip(cypress[1::2], cypress[2::2]):  # Cypress: each spec's block, cases keyed <spec file>::<title>
        block = re.split(r'^\s*\d+ passing\b', block, maxsplit=1, flags=re.M)[0]  # the failure details follow
        seen = {}
        for mark, title in re.findall(r'^ +(✓|✗|\d+\)) (.+?)(?: \(\d+ ?m?s\))?\s*$', block, re.M):
            if not re.match(r'"(?:before|after) (?:each|all)" hook', title):  # a hook failure is not a case
                key = spec + '::' + title.rstrip()
                seen[key] = seen.get(key, 0) + 1  # two cases with one title in a spec: the second is #2
                out[key + ('' if seen[key] == 1 else f'#{seen[key]}')] = 'PASSED' if mark == '✓' else 'FAILED'
    if len(cypress) == 1 and re.search(r'^\s*\d+ passing|^TOTAL: |Executed \d+ of \d+', text, re.M):  # mocha/karma spec reporters: ✓ passed, ✗ failed
        seen = {}
        # mocha marks a failure in the spec tree `N) title`, indented under its describe; the failure details after
        # `N failing` repeat it at two spaces with the suite name, and are not cases
        for indent, mark, case in re.findall(r'^( +)([✓✗]|\d+\)) (.+?)(?: \(\d+ ?ms\))?(?: FAILED| SKIPPED)?\s*$', text, re.M):
            if mark[0].isdigit() and len(indent) < 4:
                continue
            seen[case] = seen.get(case, 0) + 1  # karma prints no file or suite: a repeated title gets #<n> so each case counts
            out['spec::' + case + ('' if seen[case] == 1 else f'#{seen[case]}')] = 'PASSED' if mark == '✓' else 'FAILED'
    if re.search(r'\d+ scenarios? passed, \d+ failed, (?:\d+ error, )?\d+ skipped', text):
        # behave's plain format prints no status per scenario. Its own verdicts: the `Failing scenarios:` and
        # `Errored scenarios:` lists after each run (`  path.feature:12  name`), and a suite's after_scenario hook
        # line (`End scenario <name> , Status=Status.failed`). A scenario printed in neither passed.
        listed = {}
        for head, section in re.findall(r'^(Failing|Errored) scenarios:\n((?:[ \t]+\S+\.feature:\d+[ \t]+.*\n?)+)', text, re.M):
            for path, name in re.findall(r'^[ \t]+(\S+\.feature):\d+[ \t]+(.+?)[ \t]*$', section, re.M):
                listed[name] = (path, 'FAILED' if head == 'Failing' else 'ERROR')
        hooked = {name.strip(): st for name, st in re.findall(r'End scenario (.+?) ?, Status=Status\.(\w+)', text)}
        for block in re.split(r'^[ \t]*Scenario(?: Outline)?: ', text, flags=re.M)[1:]:
            name = block.split('\n', 1)[0].strip()
            if not name:
                continue
            if name in listed:
                path, v = listed.pop(name)
                out[f'{path}::{name}'] = v
                continue
            st = hooked.get(name, 'passed')
            out['behave::' + name] = {'failed': 'FAILED', 'error': 'ERROR', 'skipped': 'SKIPPED', 'untested': 'SKIPPED'}.get(st, 'PASSED')
        for name, (path, v) in listed.items():  # listed, but its block was not printed
            out[f'{path}::{name}'] = v
    for case in re.findall(r'^BDD_RESULT (\{.*\})\s*$', text, re.M):  # nucloud BDD process runner: {"id": "<feature>::<name>", ...}
        try:
            j = json.loads(case)
        except ValueError:
            continue
        if j.get('id'):
            out['bdd::' + j['id']] = {'passed': 'PASSED', 'failed': 'FAILED', 'error': 'ERROR', 'skipped': 'SKIPPED'}.get(j.get('result'), 'ERROR')
    seen_ice = {}
    for table in ([] if out else re.split(r'^\| *Testcase +\| *Verdict +\|.*$', text, flags=re.M)[1:]):  # icetea results table, when no other line keyed the cases
        for name, v in re.findall(r'^\| (\S+) +\| +(pass|fail|inconclusive|skip) +\|', table.split('\n\n', 1)[0], re.M):
            seen_ice[name] = seen_ice.get(name, 0) + 1  # a case run twice (factory_reset) is a row per execution
            out['icetea::' + name + ('' if seen_ice[name] == 1 else f'#{seen_ice[name]}')] = {
                'pass': 'PASSED', 'fail': 'FAILED', 'inconclusive': 'ERROR', 'skip': 'SKIPPED'}[v]
    if any(k.startswith('apitester::') for k in out):  # onprem prints each API check twice; its pytest result list is the count
        out = {k: v for k, v in out.items() if not k.startswith('api::')}
    if any(k.startswith('case::') for k in out):  # a CASE runner wraps its unit tests: go::/--- lines are inside a CASE
        out = {k: v for k, v in out.items() if not k.startswith('go::')}
    norm = {'PASSED': 'pass', 'XPASS': 'pass', 'PASS': 'pass', 'FAILED': 'fail', 'FAIL': 'fail', 'ERROR': 'blocked',
            'SKIPPED': 'not_run', 'SKIP': 'not_run', 'XFAIL': 'not_run'}
    return {k: norm[v] for k, v in out.items()}


def case_ms(text):
    """{logged case id: ms} from the per-case timings a log prints: pytest --durations (setup+call+teardown),
    Go `--- PASS: name (0.12s)`, mocha/karma spec `✓ name (12ms)`."""
    out = {}
    for sec, case in re.findall(r'^\s*([\d.]+)s (?:setup|call|teardown)\s+(\S+::[^\s\[]+(?:\[[^\n]*?\])?)\s*$', text, re.M):
        out[case] = out.get(case, 0) + float(sec) * 1000
    for case, sec in re.findall(r'^\s*--- (?:PASS|FAIL|SKIP): (\S+) \(([\d.]+)s\)', text, re.M):
        out['go::' + case] = float(sec) * 1000
    for case, ms in re.findall(r'^ +[✓✗] (.+?) \((\d+) ?ms\)\s*$', text, re.M):
        out['spec::' + case] = float(ms)
    return {k: int(round(v)) for k, v in out.items()}


def report_files(repo, stage):
    """The JUnit/robot XML files a run may leave: under .nucloud-logs/<stage>/ and the work tree."""
    seen = set()
    for root in (repo / '.nucloud-logs' / stage, repo):
        if root.is_dir():
            for path in root.rglob('*.xml'):
                if path not in seen and not any(p in path.parts for p in ('node_modules', '.git', '.venv')):
                    seen.add(path)
                    yield path


def report_snapshot(repo, stage):
    """{path: sha256} of the report files present before a suite starts."""
    import hashlib
    out = {}
    for path in report_files(repo, stage):
        try:
            out[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            pass
    return out


def report_stamp(path):
    """The epoch times a report says it was written (JUnit testsuite(s)@timestamp, robot@generated), or None. A time
    without a zone is read both as UTC (a suite container) and as this host's local time (a suite on the host)."""
    try:
        head = path.read_bytes()[:4096].decode(errors='replace')
    except OSError:
        return None
    m = re.search(r'<(?:testsuites?|robot)\b[^>]*\b(?:timestamp|generated)="([^"]+)"', head)
    if not m:
        return None
    v = m.group(1).strip()
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y%m%d %H:%M:%S.%f'):
        try:
            d = datetime.datetime.strptime(v.replace('Z', '+0000'), fmt)
        except ValueError:
            continue
        if d.tzinfo is not None:
            return (d.timestamp(),)
        return (d.replace(tzinfo=datetime.timezone.utc).timestamp(), d.timestamp())
    return None


def fresh(path, since, snapshot=None):
    """Whether this run wrote the report. mtime alone is not proof: the template's redaction pass rewrites every
    file under .nucloud-logs and refreshes it. A report that was already there, byte for byte, when the snapshot was
    taken before the suite started is never this run's. A new or changed report counts, and when it carries its own
    timestamp that must also fall between the run's start and now (2 minutes of clock skew allowed)."""
    import hashlib
    try:
        if path.stat().st_mtime < since:
            return False
        if snapshot and path in snapshot and hashlib.sha256(path.read_bytes()).hexdigest() == snapshot[path]:
            return False
    except OSError:
        return False
    stamps = report_stamp(path)
    if stamps is not None:
        return any(since - 120 <= t <= time.time() + 120 for t in stamps)
    return True


def report_ms(repo, stage, since, snapshot=None):
    """{case name: ms} from the JUnit XML and robot output.xml files a run wrote (behave --junit, the Cucumber
    junit plugin, karma-junit-reporter, surefire, robot), under .nucloud-logs/<stage>/ or the work tree.
    Keys are `classname::name` and the bare `name`."""
    import xml.etree.ElementTree as ET
    out = {}
    roots = [repo / '.nucloud-logs' / stage, repo]
    seen = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob('*.xml'):
            if path in seen or any(p in path.parts for p in ('node_modules', '.git', '.venv')) or not fresh(path, since, snapshot):
                continue
            seen.add(path)
            try:
                tree = ET.parse(path)
            except (ET.ParseError, OSError):
                continue
            for tc in tree.iter('testcase'):
                t = tc.get('time')
                if t and tc.get('name'):
                    ms = int(round(float(t) * 1000))
                    out[tc.get('name')] = ms
                    if tc.get('classname'):
                        out[tc.get('classname') + '::' + tc.get('name')] = ms
            for test in tree.iter('test'):  # robot: <status elapsed="1.2"> (robot 7) or starttime/endtime (robot 3-6)
                st = test.find('status')
                if st is None or not test.get('name'):
                    continue
                if st.get('elapsed'):
                    out[test.get('name')] = int(round(float(st.get('elapsed')) * 1000))
                elif st.get('starttime') and st.get('endtime'):
                    f = '%Y%m%d %H:%M:%S.%f'
                    try:
                        d = datetime.datetime.strptime(st.get('endtime'), f) - datetime.datetime.strptime(st.get('starttime'), f)
                        out[test.get('name')] = int(d.total_seconds() * 1000)
                    except ValueError:
                        pass
    return out


def report_verdicts(repo, stage, since, snapshot=None):
    """{classname::name: verdict} from the JUnit XML a run wrote, for cases its log prints no line for
    (JUnitCore, surefire): <failure> fails, <error> is blocked, <skipped> is not_run, otherwise pass.
    robot output.xml gives {<suite file>::<test name>: verdict} from each test's status."""
    import xml.etree.ElementTree as ET
    out = {}
    for root in (repo / '.nucloud-logs' / stage, repo):
        if not root.is_dir():
            continue
        for path in root.rglob('*.xml'):
            if any(p in path.parts for p in ('node_modules', '.git', '.venv')) or not fresh(path, since, snapshot):
                continue
            try:
                tree = ET.parse(path)
            except (ET.ParseError, OSError):
                continue
            for tc in tree.iter('testcase'):
                if not tc.get('name'):
                    continue
                key = (tc.get('classname') + '::' if tc.get('classname') else '') + tc.get('name')
                v = ('fail' if tc.find('failure') is not None else 'blocked' if tc.find('error') is not None
                     else 'not_run' if tc.find('skipped') is not None else 'pass')
                out.setdefault(key, v)
            for suite in tree.iter('suite'):  # robot output.xml: <suite source=...><test name=...><status status=PASS|FAIL|SKIP|NOT RUN>
                src = os.path.basename(suite.get('source') or '') or suite.get('name') or ''
                for test in suite.findall('test'):
                    st = test.find('status')
                    if st is None or not test.get('name'):
                        continue
                    v = {'PASS': 'pass', 'FAIL': 'fail', 'SKIP': 'not_run', 'NOT RUN': 'not_run'}.get(st.get('status'), 'blocked')
                    out.setdefault(src + '::' + test.get('name'), v)
    return out


def merge_report(rows, reported, inv, reports, base):
    """Log rows plus a JUnit or robot report's cases (keyed classname::name or <file>::<test>). The report wins
    over karma's bare spec::<title> rows, and over a log row of the same test (names compared without case,
    spaces or underscores) that names no inventory case, when the report's names one or the report alone names
    the test's file; any other report case the log printed no line for is added."""
    if reported and any(r['case'].startswith('spec::') for r in rows):
        rows = [r for r in rows if not r['case'].startswith('spec::')]

    def has_file(case):
        return bool(re.search(r'\.(?:py|robot|feature|[jt]sx?|java)$', case.split('::')[0]))

    def norm(case):
        return re.sub(r'[\s_]+', ' ', case.split('::')[-1]).strip().lower()

    logged = {norm(r['case']): i for i, r in enumerate(rows)}
    for case, v in reported.items():
        row = dict(base, case=match(case, inv) or case, verdict=v, ms=reports.get(case, ''))
        i = logged.get(norm(case))
        if i is None:
            rows.append(row)
        elif rows[i]['case'] not in inv and (row['case'] in inv or (has_file(row['case']) and not has_file(rows[i]['case']))):
            rows[i] = row  # e.g. robot: the log's `Suite::Test_name` line beside output.xml's file::Test name
    return rows


def match(logged, inventory):
    """The inventory id a logged case id names: equal, the same path::name under a different root, or a
    bare module::name whose module is the inventory file's basename; a [param] suffix is dropped."""
    base = re.sub(r'\[.*\]$', '', logged)
    if base in inventory:
        return base
    if logged.startswith('bdd::'):  # <feature file stem>::<scenario>
        stem, _, name = logged[len('bdd::'):].partition('::')
        hits = [k for k in inventory if k.split('::', 1)[0].rsplit('/', 1)[-1] == stem + '.feature' and k.split('::', 1)[-1] == name]
        return hits[0] if len(hits) == 1 else None
    if logged.startswith('behave::'):
        name = logged[len('behave::'):]
        hits = [k for k in inventory if k.endswith('::' + name)]
        return hits[0] if len(hits) == 1 else None
    if logged.startswith('go::'):
        name = logged[4:].split('/')[0]
        hits = [k for k in inventory if k.endswith('::' + name)]
        return hits[0] if len(hits) == 1 else None
    if '::' in base and '/' not in base.split('::', 1)[0] and not base.split('::', 1)[0].endswith('.py'):
        module, name = base.split('::', 1)  # `PASS module::test[param]` lines name the module, not its file
        hits = [k for k in inventory if k.split('::', 1)[0].rsplit('/', 1)[-1] == module + '.py'
                and (k.split('::', 1)[1] == name or k.split('::', 1)[1].endswith('::' + name))]  # path::Class::test
        if len(hits) == 1:
            return hits[0]
    hits = [k for k in inventory if k.rstrip().endswith(base) or base.endswith(k.rstrip())]  # titles may end in a space
    return hits[0] if len(hits) == 1 else None


def resolve_path(repo, case):
    """A case id whose file part is relative to a spec folder (Cypress prints `functional/x.spec.ts`), rewritten
    to the repo path of the one file in the tree that ends with it; unchanged when it exists or is ambiguous."""
    if '::' not in case:
        return case
    path, rest = case.split('::', 1)
    if '.' not in path.rsplit('/', 1)[-1] or (repo / path).is_file():
        return case
    hits = [p for p in repo.rglob(path.rsplit('/', 1)[-1])
            if p.is_file() and '.git' not in p.parts and 'node_modules' not in p.parts and p.as_posix().endswith('/' + path)]
    return f'{hits[0].relative_to(repo).as_posix()}::{rest}' if len(hits) == 1 else case


def parse_run(text, repo, stage, since, snapshot, inventory, ms, result):
    """One run's cases from what it left: its log (already redacted, ANSI codes removed), the JUnit and robot reports
    it wrote under .nucloud-logs/<stage>/ or the work tree after `since` (not in `snapshot`), and its result
    (pass, fail, timeout, ...). Returns (summary, rows, never_ran): summary is (passed, failed, errors, skipped,
    label); each row is {case, verdict, ms, kind} with kind `log` or `exit`; never_ran is the reason no case ran, and
    then summary and rows are None and []. `inventory` is {case id: case id} of the repo's cases."""
    exit_ok = result == 'pass'
    s = summary(text)
    why = never_ran(text) if s is None or not any(s[:4]) else None  # a total of all zeros is no run either
    if why:
        return None, [], why
    rows, inv = [], inventory
    times, reports = case_ms(text), report_ms(repo, stage, since, snapshot)
    for case, v in case_verdicts(text).items():
        name = re.sub(r'^\w+::', '', case) if case.startswith(('behave::', 'bdd::', 'spec::', 'case::')) else case.split('::')[-1]
        rows.append({'case': match(case, inv) or resolve_path(repo, case), 'verdict': v,
                     'ms': times.get(case, reports.get(case, reports.get(name, ''))), 'kind': 'log'})
    rows = merge_report(rows, report_verdicts(repo, stage, since, snapshot), inv, reports, {'kind': 'log'})
    if s is None and rows:  # no framework total, but the log names each case's verdict (pytest -v, Gradle)
        vs = [r['verdict'] for r in rows]
        s = (vs.count('pass'), vs.count('fail'), vs.count('blocked'), vs.count('not_run'), 'cases')
    if s is None:
        s = (1, 0, 0, 0, 'exit') if exit_ok else (0, 1 if result in ('fail',) else 0, 0 if result == 'fail' else 1, 0, 'exit')
        if 'suite' in inv or not rows:
            rows.append({'case': 'suite' if 'suite' in inv else f'suite.{stage}',
                         'verdict': 'pass' if exit_ok else ('fail' if result == 'fail' else 'blocked'), 'ms': ms, 'kind': 'exit'})
    return s, rows, None
