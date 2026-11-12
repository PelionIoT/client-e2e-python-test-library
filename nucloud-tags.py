#!/usr/bin/env python3
"""Test-case tags: vocabulary, selection and checks (docs/nucloud.md#tags).

Stamped from IzumaNetworks/nucloud templates/nucloud-tags.py; identical in every repo.

  nucloud-tags.py args <framework>   selection arguments for TAGS=, EXCLUDE_TAGS= and a read-only stage
  nucloud-tags.py cases              every case with its canonical tags, one per line: <case>\\t<tags>
  nucloud-tags.py check [--update]   fail on unknown, ungrouped, hand-set tier or silently dropped tags
  nucloud-tags.py vocabulary         the merged vocabulary as JSON

Frameworks: behave and cucumber (Gherkin @tags; cucumber is Cucumber-JVM run by JUnit), pytest (markers), none.
The vocabulary is test-tags.toml (shared) plus test-tags.local.toml (this repo's own tags,
under its [repo] prefix). Cases come from the framework's source, read statically, plus the
overlay test-tags.cases.tsv (<case>\\t<tag> <tag>…) for originals that must stay byte-identical.
test-tags.lock records each case's tags; a tag a case loses needs a line
`# removed <case> <tag>: <why>` in the lock, or check fails.
"""
import ast
import json
import os
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {'.git', 'node_modules', '.venv', 'venv', '.claude', '__pycache__', 'target', 'build', 'dist'}
PYTEST_BUILTIN = {'parametrize', 'skipif', 'usefixtures', 'xfail', 'filterwarnings', 'timeout', 'flaky', 'asyncio', 'order', 'dependency', 'run'}
TAG = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*:[a-z0-9]+(-[a-z0-9]+)*$')


class Problem(Exception):
    pass


def vocabulary():
    shared = ROOT / 'test-tags.toml'
    if not shared.exists():
        raise Problem('test-tags.toml missing; re-stamp from nucloud')
    v = tomllib.loads(shared.read_text())
    tags = dict(v['tags'])
    groups = set(v['groups'])
    prefix = None
    local = ROOT / 'test-tags.local.toml'
    if local.exists():
        lv = tomllib.loads(local.read_text())
        prefix = lv.get('repo', {}).get('prefix')
        if not prefix or prefix in groups:
            raise Problem('test-tags.local.toml needs [repo] prefix = "<name>", not a shared group')
        for name, row in lv.get('tags', {}).items():
            if name.split(':', 1)[0] != prefix:
                raise Problem(f'{name} in test-tags.local.toml must use the repo prefix {prefix}:')
            tags[name] = row
    alias = {}
    for name, row in tags.items():
        alias[name.replace(':', '.', 1)] = name  # the Gherkin spelling, @cloud.read-only (behave reads ':' as a limit)
        alias[re.sub(r'[^A-Za-z0-9_]', '_', name)] = name  # the pytest marker spelling, cloud_read_only
        for a in row.get('aliases', []):
            alias[a.removeprefix('pytest.mark.').lstrip('@')] = name
    return {'tags': tags, 'groups': groups, 'prefix': prefix, 'alias': alias}


def canonical(native, voc):
    """A native spelling's canonical tag: itself when canonical, its alias target, else None."""
    t = native.lstrip('@').removeprefix('pytest.mark.')
    if t in voc['tags']:
        return t
    return voc['alias'].get(t)


def native_spellings(tag, voc, framework):
    """Every native spelling that selects a canonical tag: the tag itself plus its aliases."""
    names = [tag] + [a.removeprefix('pytest.mark.').lstrip('@') for a in voc['tags'].get(tag, {}).get('aliases', [])]
    if framework == 'pytest':
        return sorted({re.sub(r'[^A-Za-z0-9_]', '_', n) for n in names})
    return sorted({n.replace(':', '.', 1) for n in names})


def split(value):
    return [t for t in re.split(r'[\s,]+', value or '') if t]


def selection(voc):
    """(include, exclude) canonical tag sets for this run."""
    include, exclude = split(os.environ.get('TAGS')), split(os.environ.get('EXCLUDE_TAGS'))
    for t in include + exclude:
        if t not in voc['tags']:
            raise Problem(f'unknown tag {t}; see test-tags.toml (or test-tags.local.toml)')
    held = [t for t, row in voc['tags'].items() if row.get('default') == 'exclude' and t not in include]
    return include, sorted(set(exclude) | set(held))


def args(framework, voc):
    include, exclude = selection(voc)
    read_only = os.environ.get('NUCLOUD_READ_ONLY') == '1'
    sp = lambda t: native_spellings(t, voc, framework)
    if framework in ('behave',):
        out = []
        if include:
            out.append('--tags=' + ','.join('@' + n for t in include for n in sp(t)))
        if read_only:
            out.append('--tags=' + ','.join('@' + n for n in sp('cloud:read-only')))
        out += ['--tags=~@' + n for t in exclude for n in sp(t)]
        return out
    if framework in ('cucumber', 'pytest'):
        at = '@' if framework == 'cucumber' else ''
        terms = []
        if include:
            terms.append('(' + ' or '.join(at + n for t in include for n in sp(t)) + ')')
        if read_only:
            terms.append('(' + ' or '.join(at + n for n in sp('cloud:read-only')) + ')')
        terms += ['not ' + at + n for t in exclude for n in sp(t)]
        expr = ' and '.join(terms)
        if framework == 'cucumber':  # Cucumber-JVM 2-6 read tag expressions from cucumber.options
            return ["-Dcucumber.options=--tags '" + expr + "'"] if expr else []
        return ['-m', expr] if expr else []
    if framework == 'none':
        return []
    raise Problem(f'unknown framework {framework}; one of behave cucumber pytest none')


def source_files(pattern):
    for p in ROOT.rglob(pattern):
        if p.is_file() and not SKIP_DIRS.intersection(p.relative_to(ROOT).parts):
            yield p


def gherkin_cases():
    """{case: [native tags]} from every .feature file: feature, rule, scenario and examples tags."""
    cases = {}
    for f in sorted(source_files('*.feature')):
        rel, feature_tags, pending, scenario, scen_tags, example = f.relative_to(ROOT).as_posix(), [], [], None, [], 0
        for line in f.read_text(errors='replace').splitlines():
            s = line.strip()
            if s.startswith('@'):
                pending += [t for t in s.split() if t.startswith('@')]
            elif re.match(r'(Feature|Funcionalidad|Fonctionnalité):', s):
                feature_tags, pending = pending, []
            elif re.match(r'(Scenario Outline|Scenario Template|Scenario|Example):', s):
                scenario = s.split(':', 1)[1].strip()
                scen_tags, pending, example = pending, [], 0
                cases[f'{rel}::{scenario}'] = feature_tags + scen_tags
            elif re.match(r'(Examples|Scenarios):', s) and scenario:
                example += 1
                key = f'{rel}::{scenario}'
                if pending:
                    cases[f'{key}::examples-{example}'] = feature_tags + scen_tags + pending
                pending = []
            elif s and not s.startswith('#'):
                pending = [] if not s.startswith('|') else pending
    return cases


def pytest_cases():
    cases = {}
    for f in sorted(list(source_files('test_*.py')) + list(source_files('*_test.py'))):
        try:
            tree = ast.parse(f.read_text(errors='replace'))
        except SyntaxError:
            continue
        rel = f.relative_to(ROOT).as_posix()

        def marks(decorators):
            out = []
            for d in decorators:
                node = d.func if isinstance(d, ast.Call) else d
                chain = []
                while isinstance(node, ast.Attribute):
                    chain.append(node.attr)
                    node = node.value
                if isinstance(node, ast.Name):
                    chain.append(node.id)
                chain.reverse()
                if chain[:2] == ['pytest', 'mark'] and len(chain) == 3 and chain[2] not in PYTEST_BUILTIN:
                    out.append(chain[2])
            return out
        module = []
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'pytestmark' for t in node.targets):
                vals = node.value.elts if isinstance(node.value, (ast.List, ast.Tuple)) else [node.value]
                module += marks(vals)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test'):
                cases[f'{rel}::{node.name}'] = module + marks(node.decorator_list)
            elif isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
                cls = marks(node.decorator_list)
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith('test'):
                        cases[f'{rel}::{node.name}::{item.name}'] = module + cls + marks(item.decorator_list)
    return cases


def framework():
    return os.environ.get('TEST_FRAMEWORK') or 'none'


def cases(voc):
    """{case: (canonical tags, unknown native tags)} from source plus the overlay."""
    fw = framework()
    found = {'behave': gherkin_cases, 'cucumber': gherkin_cases, 'pytest': pytest_cases}.get(fw, dict)()
    overlay = ROOT / 'test-tags.cases.tsv'
    extra = {}
    if overlay.exists():
        for line in overlay.read_text().splitlines():
            if line.strip() and not line.startswith('#'):
                case, _, tags = line.partition('\t')
                extra[case] = tags.split()
    out = {}
    for case in sorted(set(found) | set(extra)):
        tags, unknown = set(), []
        for n in found.get(case, []) + extra.get(case, []):
            c = canonical(n, voc)
            if c:
                tags.add(c)
            else:
                unknown.append(n)
        out[case] = (sorted(tags), unknown, extra.get(case, []))
    return out


def read_lock():
    lock, removed = {}, set()
    path = ROOT / 'test-tags.lock'
    for line in path.read_text().splitlines() if path.exists() else []:
        m = re.match(r'#\s*removed\s+(\S.*?)\s+(\S+):\s*\S', line)
        if m:
            removed.add((m.group(1), m.group(2)))
        elif line.strip() and not line.startswith('#'):
            case, _, tags = line.partition('\t')
            lock[case] = set(tags.split())
    return lock, removed, path


def check(voc, update):
    found, failures = cases(voc), []
    gherkin_source = framework() in ('behave', 'cucumber')
    natives = gherkin_cases() if gherkin_source else {}
    for case, (tags, unknown, overlay) in found.items():
        for n in unknown:
            bare = n.lstrip('@')
            why = 'has no group or prefix' if not re.search(r'[:._]', bare) else 'is not in test-tags.toml or test-tags.local.toml'
            failures.append(f'{case}: tag {n} {why}')
        if gherkin_source and case in natives:
            for n in natives[case]:
                if ':' in n:
                    failures.append(f'{case}: tag {n} uses ":"; write it @{n.lstrip("@").replace(":", ".", 1)} (behave reads ":" as a run limit)')
        for t in tags:
            if t.startswith('tier:'):
                failures.append(f'{case}: {t} is hand-set; tiers come from measured runs (make test-timings)')
        for n in overlay:
            if not TAG.match(n.lstrip('@')) and canonical(n, voc) is None:
                failures.append(f'{case}: overlay tag {n} is not <group>:<name>')
    lock, removed, path = read_lock()
    for case, before in lock.items():
        now = set(found.get(case, ([], [], []))[0])
        for t in sorted(before - now):
            if (case, t) not in removed:
                failures.append(f'{case}: lost {t}; record "# removed {case} {t}: <why>" in test-tags.lock')
    if update and not failures:
        notes = [l for l in (path.read_text().splitlines() if path.exists() else []) if l.startswith('#')]
        body = [f'{c}\t{" ".join(t)}' for c, (t, _, _) in found.items()]
        path.write_text('\n'.join(notes + body) + '\n')
    color = sys.stdout.isatty() and not os.environ.get('NO_COLOR')
    bad, ok, off = ('\033[1;31m', '\033[32m', '\033[0m') if color else ('', '', '')
    for f in failures:
        print(f'  {bad}FAIL{off}  {f}')
    untagged = sum(1 for t, _, _ in found.values() if not any(x.startswith('cloud:') for x in t))
    if failures:
        print(f'{bad}==> {len(failures)} tag problem(s) in {len(found)} case(s){off}', file=sys.stderr)
        return 1
    print(f'{ok}==> {len(found)} case(s) tagged correctly{off}; {untagged} without a cloud: tag (treated as writing)'
          + ('; test-tags.lock updated' if update else ''))
    return 0


def main(argv):
    voc = vocabulary()
    cmd = argv[0] if argv else ''
    if cmd == 'args' and len(argv) == 2:
        print('\n'.join(args(argv[1], voc)))
    elif cmd == 'cases':
        for case, (tags, unknown, _) in cases(voc).items():
            print(case + '\t' + ' '.join(tags) + ('\t?' + ' '.join(unknown) if unknown else ''))
    elif cmd == 'check':
        return check(voc, '--update' in argv)
    elif cmd == 'vocabulary':
        print(json.dumps({k: v for k, v in voc.items() if k != 'groups'} | {'groups': sorted(voc['groups'])}, indent=1))
    else:
        raise Problem('usage: nucloud-tags.py args <framework>|cases|check [--update]|vocabulary')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except Problem as exc:
        print('error: ' + str(exc), file=sys.stderr)
        sys.exit(2)
