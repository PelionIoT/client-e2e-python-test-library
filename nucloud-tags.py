#!/usr/bin/env python3
"""Test-case tags: vocabulary, selection and checks (docs/nucloud.md#tags).

Stamped from IzumaNetworks/nucloud templates/nucloud-tags.py; identical in every repo.

  nucloud-tags.py args <framework>   selection arguments for TAGS=, EXCLUDE_TAGS= and a read-only stage
  nucloud-tags.py cases [--json]     every case with its canonical tags, one per line: <case>\\t<tags>
  nucloud-tags.py select             the cases this run selects (TAGS=, EXCLUDE_TAGS=, NUCLOUD_READ_ONLY=1), overlay included
  nucloud-tags.py check [--update]   fail on unknown, ungrouped, hand-set tier or silently dropped tags
  nucloud-tags.py vocabulary         the merged vocabulary as JSON

Selection frameworks: behave and cucumber (Gherkin @tags; cucumber is Cucumber-JVM run by JUnit),
pytest (markers), none. Cases are found statically in Gherkin, pytest, Go, JUnit and JS sources;
a repo with none of them is one case, `suite`. Their tags come from the overlay.
The vocabulary is test-tags.toml (shared) plus test-tags.local.toml (this repo's own tags,
under its [repo] prefix). Cases come from the framework's source, read statically, plus the
overlay test-tags.cases.tsv (<case>\\t<tag> <tag>…) for originals that must stay byte-identical.
test-tags.lock records each case's tags; a tag a case loses needs a line
`# removed <case> <tag>: <why>` in the lock, or check fails.
"""
import ast
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

ROOT = Path(os.environ.get('NUCLOUD_TAGS_ROOT') or Path(__file__).resolve().parent)
SKIP_DIRS = {'.git', 'node_modules', '.venv', 'venv', '.claude', '__pycache__', 'target', 'build', 'dist'}
PYTEST_BUILTIN = {'parametrize', 'skipif', 'usefixtures', 'xfail', 'filterwarnings', 'timeout', 'flaky', 'asyncio', 'order', 'dependency', 'run',
                  'trylast', 'tryfirst', 'hookwrapper', 'optionalhook'}
TAG = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*(:[a-z0-9]+(-[a-z0-9]+)*)+$')  # group:name, or group:name:part


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
    if local.exists() and not os.environ.get('NUCLOUD_TAGS_NO_OVERLAY'):  # the classifier rebuilds it
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
        alias[name.replace(':', '.')] = name  # the Gherkin spelling, @cloud.read-only (behave reads ':' as a limit)
        alias[re.sub(r'[^A-Za-z0-9_]', '_', name)] = name  # the pytest marker spelling, cloud_read_only
        for a in row.get('aliases', []):
            alias[a.removeprefix('pytest.mark.').lstrip('@')] = name
    return {'tags': tags, 'groups': groups, 'prefix': prefix, 'alias': alias, 'retired': dict(v.get('retired', {})),
            'open': set(v.get('open', {}).get('groups', []))}


def canonical(native, voc):
    """A native spelling's canonical tag: itself when canonical, its alias target, else None."""
    t = native.lstrip('@').removeprefix('pytest.mark.')
    if t in voc['tags']:
        return t
    if t.split(':', 1)[0] in voc['open'] and TAG.match(t):  # open groups take any measured name (api:devices)
        return t
    return voc['alias'].get(t)


def native_spellings(tag, voc, framework):
    """Every native spelling that selects a canonical tag: the tag itself plus its aliases."""
    names = [tag] + [a.removeprefix('pytest.mark.').lstrip('@') for a in voc['tags'].get(tag, {}).get('aliases', [])]
    if framework == 'pytest':
        return sorted({re.sub(r'[^A-Za-z0-9_]', '_', n) for n in names})
    return sorted({n.replace(':', '.') for n in names})


def split(value):
    return [t for t in re.split(r'[\s,]+', value or '') if t]


def selection(voc):
    """(include, exclude) canonical tag sets for this run."""
    include, exclude = [[voc['alias'].get(t, t) for t in split(os.environ.get(v))] for v in ('TAGS', 'EXCLUDE_TAGS')]
    for t in include + exclude:
        if t not in voc['tags']:
            raise Problem(f'unknown tag {t}; see test-tags.toml (or test-tags.local.toml)')
    stage = os.environ.get('NUCLOUD_STAGE') or os.environ.get('MACHINE') or ''
    held = [t for t, row in voc['tags'].items()
            if (row.get('default') == 'exclude' or stage in row.get('absent_on', [])) and t not in include]
    return include, sorted(set(exclude) | set(held))


SAFE = ('cloud:read-only', 'needs:offline')  # what a read-only stage runs: reads only, or no cloud at all


def args(framework, voc):
    include, exclude = selection(voc)
    read_only = os.environ.get('NUCLOUD_READ_ONLY') == '1'
    sp = lambda t: native_spellings(t, voc, framework)
    if framework in ('behave',):
        out = []
        if include:
            out.append('--tags=' + ','.join('@' + n for t in include for n in sp(t)))
        if read_only:
            out.append('--tags=' + ','.join('@' + n for t in SAFE for n in sp(t)))
        out += ['--tags=~@' + n for t in exclude for n in sp(t)]
        return out
    if framework in ('cucumber', 'pytest'):
        at = '@' if framework == 'cucumber' else ''
        terms = []
        if include:
            terms.append('(' + ' or '.join(at + n for t in include for n in sp(t)) + ')')
        if read_only:
            terms.append('(' + ' or '.join(at + n for t in SAFE for n in sp(t)) + ')')
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
    """{case: [native tags]} from every .feature file, named as behave names them: a Scenario by its name,
    each Scenario Outline row as "<name> -- @<table>.<row> <examples name>" with its <params> filled in.
    Feature, Rule, Scenario and Examples tags all apply."""
    cases = {}
    for f in sorted(source_files('*.feature')):
        rel = f.relative_to(ROOT).as_posix()
        feature_tags, pending, outline, outline_tags = [], [], None, []
        table, header, row, examples_name, examples_tags = 0, None, 0, '', []

        def add(name, tags):
            n, base = 2, name
            while f'{rel}::{name}' in cases:  # a repeated scenario name keeps its own identity
                name, n = f'{base}#{n}', n + 1
            cases[f'{rel}::{name}'] = tags
        for line in f.read_text(errors='replace').splitlines():
            s = line.strip()
            if s.startswith('@'):
                pending += [t for t in s.split() if t.startswith('@')]
            elif re.match(r'(Feature|Funcionalidad|Fonctionnalité):', s):
                feature_tags, pending = pending, []
            elif re.match(r'Rule:', s):
                pending = []
            elif re.match(r'(Scenario Outline|Scenario Template):', s):
                outline, outline_tags, pending, table = s.split(':', 1)[1].strip(), pending, [], 0
            elif re.match(r'(Scenario|Example):', s):
                outline = None
                add(s.split(':', 1)[1].strip(), feature_tags + pending)
                pending = []
            elif re.match(r'(Examples|Scenarios):', s) and outline is not None:
                table, header, row = table + 1, None, 0
                examples_name, examples_tags, pending = s.split(':', 1)[1].strip(), pending, []
            elif s.startswith('|') and outline is not None and table:
                cells = [c.strip() for c in s.strip('|').split('|')]
                if header is None:
                    header = cells
                else:
                    row += 1
                    name, label = outline, examples_name  # behave fills <params> into both
                    for k, v in zip(header, cells):
                        name, label = name.replace(f'<{k}>', v), label.replace(f'<{k}>', v)
                    add(f'{name} -- @{table}.{row} {label}', feature_tags + outline_tags + examples_tags)
            elif s and not s.startswith('#') and not s.startswith('"""'):
                pending = []
    return cases


def pytest_config():
    """[(directory, python_files, python_classes, python_functions)] from every pytest.ini, tox.ini, setup.cfg and
    pyproject.toml in the repo; pytest's defaults for the repo root when none sets python_files."""
    import configparser
    out = []
    for name, section in (('pytest.ini', 'pytest'), ('tox.ini', 'pytest'), ('setup.cfg', 'tool:pytest'), ('pyproject.toml', None)):
        for path in source_files(name):
            opts = {}
            try:
                if section is None:
                    opts = tomllib.loads(path.read_text()).get('tool', {}).get('pytest', {}).get('ini_options', {})
                    opts = {k: ' '.join(v) if isinstance(v, list) else str(v) for k, v in opts.items()}
                else:
                    cp = configparser.ConfigParser(interpolation=None)
                    cp.read_string(path.read_text(errors='replace'))
                    opts = dict(cp[section]) if cp.has_section(section) else {}
            except Exception:
                continue
            if 'python_files' in opts:
                out.append((path.parent, opts['python_files'].split(), opts.get('python_classes', 'Test').split(),
                            opts.get('python_functions', 'test').split()))
    covered = {d for d, *_ in out}
    if ROOT not in covered:
        out.append((ROOT, ['test_*.py', '*_test.py'], ['Test'], ['test']))
    return out


def _named(name, patterns):  # pytest: a pattern without a glob character is a prefix
    return any(fnmatch.fnmatch(name, p) if any(ch in p for ch in '*?[') else name.startswith(p) for p in patterns)


def pytest_cases():
    cases = {}
    files = {}
    for base, file_globs, class_globs, func_globs in sorted(pytest_config(), key=lambda c: len(c[0].parts)):
        for g in file_globs:
            for f in base.rglob(g):
                if f.is_file() and f.suffix == '.py' and f.name != 'conftest.py' and not SKIP_DIRS.intersection(f.relative_to(ROOT).parts):
                    files[f] = (class_globs, func_globs)  # the deepest config wins
    for f in sorted(files):
        class_globs, func_globs = files[f]
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
        def fixture(fn):  # @pytest.fixture, @pytest.fixture(...), @fixture
            for d in fn.decorator_list:
                node = d.func if isinstance(d, ast.Call) else d
                if (isinstance(node, ast.Attribute) and node.attr == 'fixture') or (isinstance(node, ast.Name) and node.id == 'fixture'):
                    return True
            return False
        classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}

        def methods(cls, seen=()):  # own test methods plus those inherited from classes in this file
            out = {}
            for base in cls.bases:
                if isinstance(base, ast.Name) and base.id in classes and base.id not in seen:
                    out.update(methods(classes[base.id], seen + (cls.name,)))
            for item in cls.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and _named(item.name, func_globs) and not fixture(item):
                    out[item.name] = item
            return out
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _named(node.name, func_globs) and not fixture(node):
                cases[f'{rel}::{node.name}'] = module + marks(node.decorator_list)
            elif isinstance(node, ast.ClassDef) and (_named(node.name, class_globs) or any(
                    (isinstance(base, ast.Attribute) and base.attr.endswith('TestCase')) or (isinstance(base, ast.Name) and base.id.endswith('TestCase'))
                    for base in node.bases)):
                cls = marks(node.decorator_list)
                for name, item in methods(node).items():
                    cases[f'{rel}::{node.name}::{name}'] = module + cls + marks(item.decorator_list)
    return cases


def go_cases():
    cases = {}
    for f in sorted(source_files('*_test.go')):
        rel = f.relative_to(ROOT).as_posix()
        code = re.sub(r'`[^`]*`', '``', f.read_text(errors='replace'))  # fixture source inside raw strings is not a test
        for name in re.findall(r'^func (Test\w+)\(\w+ \*testing\.T\)', code, re.M):
            cases[f'{rel}::{name}'] = []
    return cases


def junit_cases():
    """JUnit 4/5 @Test methods; JUnit 5 @Tag values are their native tags."""
    cases = {}
    for f in sorted(source_files('*.java')):
        text = f.read_text(errors='replace')
        if '@Test' not in text:
            continue
        rel = f.relative_to(ROOT).as_posix()
        for m in re.finditer(r'((?:@\w+(?:\([^)]*\))?\s*)+)(?:public\s+|protected\s+|private\s+)?(?:static\s+)?void\s+(\w+)\s*\(', text):
            if re.search(r'@Test\b', m.group(1)):
                cases[f'{rel}::{m.group(2)}'] = re.findall(r'@Tag\("([^"]+)"\)', m.group(1))
    return cases


def js_cases():
    cases = {}
    for pattern in ('*.test.js', '*.spec.js', '*.test.ts', '*.spec.ts'):
        for f in sorted(source_files(pattern)):
            rel = f.relative_to(ROOT).as_posix()
            for name in re.findall(r'''\b(?:x?it|x?test)(?:\.(?:skip|only|todo))?\s*\(\s*(['"`])(.+?)\1''', f.read_text(errors='replace')):
                cases[f'{rel}::{name[1]}'] = []
    return cases


DETECTORS = {'gherkin': gherkin_cases, 'pytest': pytest_cases, 'go': go_cases, 'junit': junit_cases, 'js': js_cases}


def framework():
    return os.environ.get('TEST_FRAMEWORK') or 'none'


def cases(voc):
    """{case: (canonical tags, unknown native tags)} from source plus the overlay."""
    found, kind = {}, {}
    for name, detect in DETECTORS.items():
        for case, tags in detect().items():
            found[case], kind[case] = tags, name
    if not found:  # a suite with no case-level source is one case: the suite
        found['suite'], kind['suite'] = [], 'suite'
    overlay = ROOT / 'test-tags.cases.tsv'
    extra = {}
    if overlay.exists() and not os.environ.get('NUCLOUD_TAGS_NO_OVERLAY'):  # the classifier reads source tags only
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
        KIND[case] = kind.get(case, 'overlay')
    return out


KIND = {}


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
    gherkin_source = True
    natives = gherkin_cases()
    for case, (tags, unknown, overlay) in found.items():
        for n in unknown:
            bare = n.lstrip('@')
            why = 'has no group or prefix' if not re.search(r'[:._]', bare) else 'is not in test-tags.toml or test-tags.local.toml'
            failures.append(f'{case}: tag {n} {why}')
        if gherkin_source and case in natives:
            for n in natives[case]:
                if ':' in n:
                    failures.append(f'{case}: tag {n} uses ":"; write it @{n.lstrip("@").replace(":", ".", 1)} (behave reads ":" as a run limit)')
        measured = {canonical(n, voc) for n in overlay}  # the overlay carries tiers from measured runs
        for t in tags:
            if t.startswith('tier:') and t not in measured:
                failures.append(f'{case}: {t} is hand-set; tiers come from measured runs (make test-timings)')
        for n in overlay:
            if not TAG.match(n.lstrip('@')) and canonical(n, voc) is None:
                failures.append(f'{case}: overlay tag {n} is not <group>:<name>')
    lock, removed, path = read_lock()
    for case, before in lock.items():
        now = set(found.get(case, ([], [], []))[0])
        for t in sorted(before - now):
            if (case, t) not in removed and t not in voc['retired']:
                failures.append(f'{case}: lost {t}; record "# removed {case} {t}: <why>" in test-tags.lock')
    if update and not failures:
        notes = [l for l in (path.read_text().splitlines() if path.exists() else []) if l.startswith('#')]
        body = [f'{c}\t{" ".join(t)}' for c, (t, _, _) in found.items()]
        path.write_text('\n'.join(notes + body) + '\n')
    color = sys.stdout.isatty() and not os.environ.get('NO_COLOR')
    bad, ok, off = ('\033[1;31m', '\033[32m', '\033[0m') if color else ('', '', '')
    for f in failures:
        print(f'  {bad}FAIL{off}  {f}')
    untagged = sum(1 for t, _, _ in found.values() if not any(x.startswith('cloud:') for x in t) and 'needs:offline' not in t)
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
    elif cmd == 'select':  # the cases this run selects, overlay tags included: TAGS=, EXCLUDE_TAGS=, a read-only stage
        include, exclude = selection(voc)
        read_only = os.environ.get('NUCLOUD_READ_ONLY') == '1'
        for case, (tags, _, _) in cases(voc).items():
            t = set(tags)
            if (not include or t & set(include)) and not t & set(exclude) and (not read_only or t & set(SAFE)):
                print(case)
    elif cmd == 'cases':
        for case, (tags, unknown, _) in cases(voc).items():
            if '--json' in argv:
                print(json.dumps({'case': case, 'kind': KIND[case], 'tags': tags, 'unknown': unknown}))
            else:
                print(case + '\t' + ' '.join(tags) + ('\t?' + ' '.join(unknown) if unknown else ''))
    elif cmd == 'check':
        return check(voc, '--update' in argv)
    elif cmd == 'vocabulary':
        print(json.dumps({k: v for k, v in voc.items() if k != 'groups'} | {'groups': sorted(voc['groups'])}, indent=1))
    else:
        raise Problem('usage: nucloud-tags.py args <framework>|cases [--json]|select|check [--update]|vocabulary')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except Problem as exc:
        print('error: ' + str(exc), file=sys.stderr)
        sys.exit(2)
