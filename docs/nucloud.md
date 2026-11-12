# Building and deploying this repo

This repo builds the images listed in `nucloud.env` from its development
branch: `nucloud` where the repo keeps one beside the upstream `master`, else
`main`. The checkout lives in `<dir>/NUCLOUD/REPOS/<repo>` or
`<dir>/NUCLOUD/TESTING/<repo>`, the layout nucloud's `setup.sh` creates, and
has one worktree. `archive/<tag>` records the archived production image digest.
The rules are in [nucloud standards](https://github.com/IzumaNetworks/nucloud/blob/main/docs/standards.md),
the stages in [nucloud setup](https://github.com/IzumaNetworks/nucloud/blob/main/docs/setup.md).

## Check this machine

```sh
make help                # targets, the variables they read, this repo's own targets
make prereqs             # host tools, the Docker engine, izmachine, stages and each cloud's credentials
```

`make prereqs` prints each check with the tool's path and version: host
tools first, then the Docker engine, then izmachine and the stages. In a test
repo it ends with one line per cloud (`MACHINE=<stage>` checks one) for the
credentials the suite needs and a read-only API check. It lists every failure
at the end with the elapsed time, exiting 1. A stage whose incus remote this
machine lacks is noted, not failed. Output is colored only on a terminal;
`NO_COLOR=1` or `COLOR=never` turns color off and `COLOR=always` forces it.
The helper needs bash 4.3 or newer first on `PATH` (on macOS,
`brew install bash`).

In a repo that has its own Makefile, `make help` ends with that Makefile's
targets. Any target nucloud does not define runs the repo's own rule. For one
nucloud also defines, such as `build` or `clean`, `NATIVE=1 make <target>` runs
the repo's rule.

## Build

```sh
make images              # images and tags
make build               # build every image inside Docker
make build ONLY=<name>   # one image
```

Builds run entirely in Docker for `linux/amd64` on the workspace's build
context: `DOCKER_CONTEXT` in the nearest `nucloud.conf` above this checkout
(nucloud's `setup.sh` writes `<dir>/NUCLOUD/nucloud.conf`), else in
`~/.config/nucloud/nucloud.conf`.
`DOCKER_CONTEXT=<name>` in your shell overrides it; with neither, Docker's
current context builds. Any Linux engine works, local or remote: an amd64 host
builds natively, and Docker Desktop on an Apple silicon Mac (`desktop-linux`)
builds the same images under emulation, more slowly. `make prereqs` names the
context, where it came from and its engine, and fails when the engine is not
Linux. `make image` also builds the
images. Nucloud build and deploy targets run independently of
the repository's native host build prerequisites. Build
secrets named in `nucloud.env` (`SECRETS`) come from environment variables
and reach the build as BuildKit secrets, never as layers. A repo with
`SSH=1` reads private git dependencies through your ssh agent.

## Deploy to a k3s stage

```sh
make deploy MACHINE=k3s-trav
make deploy MACHINE=k3s-cypress
make deploy              # on a terminal: pick the stage from a list
```

Every stage target takes `MACHINE=<stage>`. Without it, a terminal shows a
numbered list of the stages in `.iz` and `.izlocal`; answer with a number or
a stage name. Without a terminal, the target exits naming the stages.

`make deploy` builds the images, imports them, upgrades their releases and
ends with the same table `make running` prints. Use
`make deploy-only` to import and apply images that already exist on the
selected Docker context:

```sh
make deploy-only MACHINE=k3s-ed IMAGE_SUFFIX=nucloud.dev.abcdef0
```

`IMAGE_SUFFIX` selects the exact suffix from a completed build, including
any dirty-tree hash. Omit it to select the current checkout's image tags.
Every selected image must exist and match the configured platform before
any import or Helm upgrade starts. Missing images cause an error; this
command never builds, pulls or pushes images. `make deploy` rejects
`IMAGE_SUFFIX` so a build cannot overwrite an earlier build's selected tag.

`deploy` finds the stage's incus remote and VM in `.iz`, which every repo
carries. `.iz` defines the shared clouds: the K3s clouds `k3s-ed`, `k3s-trav`
and `k3s-golden` and the Kubernetes (k8s) cloud `staging`, all on the `D71`
remote, and lists `k3s-golden` and `staging` under `[nucloud] production`:
`deploy`, `deploy-only` and `image-load` refuse a production stage and leave
it out of the list, while `running`, `stage-check` and `kubeconfig` read it.
`.izlocal` beside it holds private machines, such as `k3s-cypress` on the
`cypressLinux` remote, and local overrides; it is never committed, and is
created once from the template and left as you edit it. izmachine reads
`~/.config/izmachine/global.iz`, then `.iz`, then `.izlocal`; a later file
replaces an earlier one field by field. The helper reads the same files as
structured TOML (`nucloud-cloud.py`): a stage is a top-level
`[machine.<stage>]` entry, and its nested `labels`, `facts` and `functions`
tables are its metadata. A stage that no file defines, a checkout without
`.iz` and a machine without izmachine on `PATH` each stop the run before
anything is built or imported.

Each Kubernetes cloud carries `labels = { class = "kubernetes", distribution
= "k3s" }` (or `"k8s"`) and a `kubeconfig_path` fact. The class attaches the
shared `fetchKubeconfig` producer in `global.iz`, which caches the cloud's
kubeconfig as an encrypted izmachine fact; a kubeconfig stored with
`izmachine fact set <stage> kubeconfig - --secret` is enough without it.
`deploy` points the kubeconfig at the VM's LAN address. The kubeconfig lives in a private temporary file for the run and is
never written into the repo. The chart of each release comes from the
release's newest record in the cluster, and the upgrade keeps the release's
current values and namespace, sets this repo's image tags and waits for its
workloads across their namespaces. A release that renders vendored
subcharts, which Helm does not keep in its record, takes its chart from an
`izuma-dm-platform` checkout: `NUCLOUD_PLATFORM`, default
`../../INFRA/izuma-dm-platform`, where `setup.sh` places it. `paas` and `zookeeper-nucloud` have
such releases. The release each image goes to is the last field of its
`nucloud.env` entry.

```sh
make stage-check MACHINE=k3s-ed   # the stage VM answers and its kubeconfig can be fetched
make kubeconfig MACHINE=k3s-ed    # print the stage's kubeconfig; nothing is written
make running MACHINE=k3s-ed       # a table of this repo's releases and the build each workload runs
```

`make running` prints one table per release: each workload, its readiness,
its image and the commit it was built from, with how far that commit is
behind this checkout's branch. On a terminal the branch, the commits and the
images link to GitHub.

## Test repos

A repo whose `nucloud.env` sets `KIND=tests` holds a suite instead of a service:

```sh
make prereqs MACHINE=staging # host tools, Docker, izmachine and staging's credentials; changes nothing
make setup MACHINE=staging   # create or verify the suite's own fixtures; safe to repeat
make test MACHINE=staging    # run setup, then the suite against the stage's API
```

Without `MACHINE=`, a terminal offers the stages. Credentials are encrypted
izmachine facts on each cloud, never files: `cloud.api_key`, and for suites
that log in `cloud.admin_user`, `cloud.admin_password`, `cloud.root_user` and
`cloud.root_password`; `cloud.api_url` names an API other than
`https://api.<stage>.izuma.io`. Store one with
`izmachine fact set <stage> cloud.api_key - --secret`, which reads the value
from standard input. `CREDENTIALS=` in `nucloud.env` names the ones
`make prereqs` requires; the suite receives every one the cloud holds as
`NUCLOUD_API_KEY`, `NUCLOUD_USER` and so on. `ACCOUNT=<name>` runs as another
test account on the stage, from its `cloud.accounts.<name>.*` facts.
`ACCOUNTS=(staging=edge k3s-golden=onprem)` in `nucloud.env` names the
account a suite uses on each stage; `ACCOUNT=` on the command line wins.
`SUITES=<paths>` narrows the run to those folders or tests, for suites that
read it.

The shared checks cover what every repo needs. `nucloud.env` adds this
repo's own needs, and `make prereqs` runs them in the same colored format:

- `HOST_TOOLS=("kubectl|hsm setup" "py:yaml|kubeconfig parsing")` lists host
  tools and python3 modules, each with what needs it.
- `CREDENTIALS=(API_KEY USER PASSWORD)` names the `cloud.*` facts each cloud
  must hold.
- `PREREQS_CMD=(scripts/nucloud-prereqs.sh)` runs last, read-only, for
  anything else: repo-specific facts such as `bdd.hsm.signing_key`, or a
  tool needed only for one feature. A bash script calls `chk_ok`,
  `chk_fail`, `chk_note` and `chk_tool`; a script in another language prints
  with the `NUCLOUD_CHECK_OK`, `NUCLOUD_CHECK_FAIL`, `NUCLOUD_CHECK_WARN`,
  `NUCLOUD_CHECK_NAME` and `NUCLOUD_CHECK_OFF` colors. Either exits 1 on a
  failure.

`nucloud.env` is bash, so a check can depend on the run, for example
`[[ ${FEATURE:-} != hsm_* ]] || HOST_TOOLS+=("incus|hsm helper image")`.
Every file these checks use lives in this repo, so the repo runs on its own.

`make test` runs the suite's setup first. Setup is the suite's own code: it
creates or verifies the fixtures the suite owns, so a cloud with only its
credentials needs no other preparation. A setup failure prints
`setup: <repo> failed on <stage>` and the cases do not run, so it never reads
as a test result. A suite whose cases create and delete everything they use
has no separate setup; its `nucloud.env` says so in one line,
`# setup: none — <why>`. The deploy targets refuse a test repo. See [standards](https://github.com/IzumaNetworks/nucloud/blob/main/docs/standards.md#test-repos).

## Select and time test cases

Every test case carries tags from `test-tags.toml`: whether it writes to the
cloud (`cloud:read-only`, `cloud:writes`, `cloud:login`), what it needs
(`needs:hsm`), what it proves (`kind:rejection`) and whether it runs by
default (`lifecycle:deprecated`, `risk:insecure` and the other `exclude`
tags do not). This repo's own tags use its prefix and live in
`test-tags.local.toml`. The rules are in
[testing](https://github.com/IzumaNetworks/nucloud/blob/main/docs/testing.md#rules).

```sh
make tags                                  # every case and its tags
make tags MACHINE=staging                  # the cases a staging run takes (read-only only)
make tags TAGS=lifecycle:deprecated        # the cases that selection runs
make test MACHINE=k3s-golden TAGS=needs:hsm EXCLUDE_TAGS=cloud:writes
make tags-check                            # fail on an unknown, ungrouped or dropped tag
make test-timings                          # each test's measured average and tier
```

`TAGS=` selects cases carrying any of the named tags, and an `exclude` tag
runs only when it is named. `EXCLUDE_TAGS=` always wins. On a read-only
stage (staging) only `cloud:read-only` cases run. `TEST_FRAMEWORK=` in
`nucloud.env` (`behave`, `cucumber`, `pytest`) turns the selection into the
framework's own arguments, which the suite receives as `NUCLOUD_TAG_ARGS`.
Tags kept outside the original source sit in `test-tags.cases.tsv`; a tag a
case loses needs a `# removed <case> <tag>: <why>` line in
`test-tags.lock`, then `make tags-check UPDATE=1`.

`make test-timings` reads TESTMASTER's measured runs: fast at 10 seconds or
less, standard up to 120 seconds, slow above that, unmeasured with no
completed run. Tiers are never written by hand.

## Tags

A local build is tagged `<upstream>-nucloud.dev.<commit>`, plus a hash of
any uncommitted changes, so each changed tree deploys under a new tag and
its pods restart. CI tags `<upstream>-nucloud.<run number>`. `make push`
pushes only CI tags, so a rebuild can never replace an image a cluster
runs.

## CI

`.github/workflows/nucloud.yml` builds source changes on pull requests
into the development branch and pushes to it. Changes confined to `docs/`,
README files, Markdown, `Makefile`, `Makefile.nucloud`,
`makehelp-nucloud.sh`, `nucloud-cloud.py`, `.dockerignore`, `.iz`, `.izlocal`, `.gitignore` and the workflow file skip CI.
`Dockerfile`, `nucloud.env` and code changes trigger it.

Force a rebuild with `gh workflow run nucloud -R <org/repo> --ref <development branch>`.
CI builds, tests, smoke-checks and writes SBOMs on the five-runner pool.
It pushes images to GHCR from the development branch, then removes its images and
build cache. Every runner service also runs its completion cleanup hook.

## Changes from upstream

`docs/fixes.md` lists every change the development branch makes to build
files or source, and why.
