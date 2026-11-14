# Installed as sitecustomize.py in the suite container (nucloud template): one line per HTTP request that
# urllib3 (requests, botocore, the SDKs) makes, appended to $NUCLOUD_HTTP_LOG as
# <case>\t<METHOD>\t<scheme://host/path>\t<status>. <case> is pytest's current test, else "-". Query strings
# are dropped, so no key or token in a URL reaches the log. A 2xx answer to a POST made through requests that
# carries a top-level JSON "id" also appends <case>\t<scheme://host/path>\t<id> to <the same folder>/http-ids.log, so
# a run that leaves records behind can delete them by id; nothing else of the answer is kept. Test code and its own
# logging are untouched.
import logging
import os
import re
import sys

_path = os.environ.get('NUCLOUD_HTTP_LOG')
# Python 2 sets a freed module's globals to None while its handler can still run (icetea suites), so on Python 2
# the hook installs nothing: no handler, no import hook, urllib3's logging exactly as the image left it.
if _path and sys.version_info[0] >= 3:
    _line = re.compile(r'^(?P<origin>\S+) "(?P<method>[A-Z]+) (?P<path>[^ ?"]*)\S* HTTP/[\d.]+" (?P<status>\d+)')

    class _Requests(logging.Handler):
        def emit(self, record):
            try:
                m = _line.match(record.getMessage())
            except Exception:
                m = None
            if m:
                self.write(m)
            # The suite's own logging sees exactly what it saw before: forward at the level it asked for
            parent = logging.getLogger('urllib3')
            if record.levelno >= parent.getEffectiveLevel():
                parent.handle(record)

        def write(self, m):
            try:
                origin = re.sub(r':(443|80)$', '', m.group('origin'))
                case = _case()
                with open(_path, 'a') as f:
                    f.write('%s\t%s\t%s%s\t%s\n' % (case, m.group('method'), origin, m.group('path'), m.group('status')))
            except Exception:
                pass

    def _case():
        return os.environ.get('PYTEST_CURRENT_TEST', '').rsplit(' (', 1)[0] or _behave[0] or '-'

    _ids = os.path.join(os.path.dirname(_path), 'http-ids.log')

    def _patch_requests(sessions):
        send = sessions.Session.send

        def logged_send(self, request, **kwargs):
            r = send(self, request, **kwargs)
            try:
                if (request.method == 'POST' and 200 <= r.status_code < 300 and not kwargs.get('stream')
                        and 'json' in r.headers.get('Content-Type', '')):
                    rid = r.json().get('id')
                    if isinstance(rid, str) and re.match(r'^[\w.:-]{1,128}$', rid):
                        with open(_ids, 'a') as f:
                            f.write('%s\t%s\t%s\n' % (_case(), request.url.split('?', 1)[0], rid))
            except Exception:
                pass
            return r
        sessions.Session.send = logged_send

    # behave sets no pytest id: wrap behave.model.Scenario.run, once behave imports it, to name the running
    # scenario as <feature file>::<scenario name>, the id the case inventory uses.
    _behave = ['']

    def _patch_behave(model):
        run = model.Scenario.run

        def scenario_run(self, *args, **kwargs):
            prev, _behave[0] = _behave[0], '%s::%s' % (getattr(self, 'filename', ''), self.name)
            try:
                return run(self, *args, **kwargs)
            finally:
                _behave[0] = prev
        model.Scenario.run = scenario_run

    _patches = {'behave.model': _patch_behave, 'requests.sessions': _patch_requests}

    class _ImportHook(object):
        """Patches each module in _patches once it is imported, then leaves sys.meta_path when all are done."""
        def find_module(self, name, path=None):  # Python 2 and pre-3.4 finders: never claims a module
            return None

        def find_spec(self, name, path, target=None):
            if name not in _patches:
                return None
            import importlib.util
            sys.meta_path.remove(self)
            try:
                spec = importlib.util.find_spec(name)
            finally:
                sys.meta_path.insert(0, self)
            if spec is None or spec.loader is None or not hasattr(spec.loader, 'exec_module'):
                return spec
            exec_module = spec.loader.exec_module

            def patched(module):
                exec_module(module)
                try:
                    _patches.pop(name)(module)
                except Exception:
                    pass
                if not _patches and self in sys.meta_path:
                    sys.meta_path.remove(self)
            spec.loader.exec_module = patched
            return spec

    if sys.version_info >= (3, 4):  # find_spec exists from 3.4; 3.0-3.3 log requests without scenario names or ids
        sys.meta_path.insert(0, _ImportHook())

    _log = logging.getLogger('urllib3.connectionpool')
    _log.addHandler(_Requests(logging.DEBUG))
    _log.setLevel(logging.DEBUG)
    _log.propagate = False

# Chain to the image's own sitecustomize, if it has one
_here = os.path.dirname(os.path.abspath(__file__))
for _d in sys.path:
    if _d and os.path.abspath(_d) != _here and os.path.isfile(os.path.join(_d, 'sitecustomize.py')):
        with open(os.path.join(_d, 'sitecustomize.py')) as _f:
            exec(compile(_f.read(), os.path.join(_d, 'sitecustomize.py'), 'exec'))
        break
