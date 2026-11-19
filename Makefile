# REPORT defaults to [nucloud] report in the untracked .izlocal, this system's trackHammer.
# REPORT=<url or path> on the command line or in the environment wins; REPORT= turns reporting off.
ifeq ($(origin REPORT),undefined)
REPORT := $(shell python3 -c 'import pathlib,sys; toml=__import__("tomllib" if sys.version_info >= (3,11) else "tomli"); p=pathlib.Path(".izlocal"); print(toml.loads(p.read_text()).get("nucloud",{}).get("report","") if p.is_file() else "")' 2>/dev/null)
endif
# nucloud targets: see docs/nucloud.md
include Makefile.nucloud
