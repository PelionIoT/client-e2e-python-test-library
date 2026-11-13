# Installed as sitecustomize.py in the suite container (nucloud template): one line per HTTP request that
# urllib3 (requests, botocore, the SDKs) makes, appended to $NUCLOUD_HTTP_LOG as
# <case>\t<METHOD>\t<scheme://host/path>\t<status>. <case> is pytest's current test, else "-". Query strings
# are dropped, so no key or token in a URL reaches the log. Test code and its own logging are untouched.
import logging
import os
import re
import sys

_path = os.environ.get('NUCLOUD_HTTP_LOG')
if _path:
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
                case = os.environ.get('PYTEST_CURRENT_TEST', '-').rsplit(' (', 1)[0]
                with open(_path, 'a') as f:
                    f.write('%s\t%s\t%s%s\t%s\n' % (case, m.group('method'), origin, m.group('path'), m.group('status')))
            except Exception:
                pass

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
