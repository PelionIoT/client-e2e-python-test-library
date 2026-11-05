# Defects

PelionIoT/client-e2e-python-test-library is a public repo whose `nucloud`
image needs two sources it does not hold: ArmMbedCloud/device-simulator
(private) and `simulated_client/testapp.py` plus `provision.py` from
IzumaNetworks/pelion-system-tests (internal). The Dockerfile fetches both at
fixed commits over a forwarded SSH agent (`SSH=1` in `nucloud.env`). The
stamped CI workflow runs on the self-hosted `nucloud` runner group, which
admits private repos only, so CI cannot build this repo while it is public
and depends on private sources. Developers build and test from a checkout
with `make build` and `make test MACHINE=<stage>`. The suite passes on
k3s-golden (9 passed, 0 failed, 1 not run) and runs its GET cases on staging
behind an HTTP guard (2 passed, 7 not run). ArmMbedCloud/pelion-e2e-python-test-library-internal
is a private near copy of this repo with the same cases and the same results.

## Defects

### D1: CI cannot build the image

**Symptom.** A push or pull request on `nucloud` queues the `image` job of
`.github/workflows/nucloud.yml` and no runner takes it. If a runner did take
it, the `sources` stage of the Dockerfile would fail at the first `git fetch`
with `Permission denied (publickey)`, because the job has no SSH key.

**Cause.** Three facts combine.

1. The repo is public and the sources are not:

   ```
   $ gh repo view PelionIoT/client-e2e-python-test-library --json visibility
   PUBLIC
   $ gh repo view ArmMbedCloud/device-simulator --json visibility
   PRIVATE
   $ gh repo view IzumaNetworks/pelion-system-tests --json visibility
   INTERNAL
   ```

2. The Dockerfile reads both over the build's SSH agent. `Dockerfile:9-20`
   mounts the agent (`--mount=type=ssh`), fetches
   `git@github.com:ArmMbedCloud/device-simulator.git` at
   `a4a387ff8af4f92992c8e75461339454af677265` and
   `git@github.com:IzumaNetworks/pelion-system-tests.git` at
   `c9056ed471c2b59d3ab903fc9c57a985dd9ce5f9`, keeps the whole simulator tree
   and only `simulated_client/testapp.py` and `simulated_client/provision.py`
   from the system tests, and deletes the rest. `nucloud.env:8` sets `SSH=1`
   so `make build` forwards the developer's agent. `.gitignore` lists
   `simulated_client/testapp.py` and `simulated_client/provision.py`, so a
   local copy never enters a commit.

3. CI has neither a runner nor a key for a public repo. `nucloud.yml:58`
   sets `runs-on: [self-hosted, nucloud]`. The `nucloud` runner group in
   PelionIoT is created with `"allows_public_repositories":false`
   (IzumaNetworks/nucloud `scripts/runner-groups.sh:17`), and its repo list
   on line 27 of that script does not name this repo. The operator keeps the
   group that way: public repos get no self-hosted runner and no
   GitHub-hosted runner. `nucloud.yml:66-74` checks for `IZUMABOT_SSH_KEY` and
   skips the agent step when the secret is empty, which it is for a public
   repo (`IzumaNetworks/nucloud docs/standards.md:215`: the key reads private
   git dependencies and is scoped to private repos).

**Evidence.**

- `Dockerfile:2-4`: "This repo is public. ArmMbedCloud/device-simulator is
  private and IzumaNetworks/pelion-system-tests is internal, so the build
  fetches them at fixed commits over the forwarded ssh agent, and no file of
  theirs enters git."
- `README.md:126`: "The image needs `make build` to reach the private device
  simulator and the internal `simulated_client/testapp.py`, so `nucloud.env`
  sets `SSH=1`. This repo is public, so neither enters git."
- `nucloud.yml:66`: "IZUMABOT_SSH_KEY reaches private repos only; a public
  repo builds without it."
- Team log, 2026-11-04: "this repo is PUBLIC, device-simulator is PRIVATE and
  pelion-system-tests INTERNAL, so nothing of theirs is committed: the build
  fetches both at fixed commits with SSH=1. ... CI on this repo cannot build
  until it gets the key or a public way to fetch the simulator."

**Options.** Pick one; the suite needs no code change under either.

*Option A: make the repo private.*

- Set the repo visibility to private in GitHub.
- Add `client-e2e-python-test-library` to the PelionIoT line of
  IzumaNetworks/nucloud `scripts/runner-groups.sh` and run it, so the
  `nucloud` runner group admits the repo.
- Confirm the org secret `IZUMABOT_SSH_KEY` reaches the repo and that
  IzumaBOT, through the `nucloud-ci` team, can read ArmMbedCloud/device-simulator
  and IzumaNetworks/pelion-system-tests.
- Cost: the library stops being public. GitHub redirects the historical
  name ARMmbed/pelion-e2e-python-test-library to this repo
  (`gh repo view ARMmbed/pelion-e2e-python-test-library` answers
  `PelionIoT/client-e2e-python-test-library`); the redirect, the Apache-2.0
  `LICENSE` link in `README.md:120` and every external clone of the
  library stop working for anyone outside the org. The 122-commit public
  history since 2019-06-13 becomes private. No file in the repo changes.

*Option B: remove the private dependencies.*

The Dockerfile uses, from the private sources:

| Source | What the image keeps | Where it goes | Size at the pinned commit |
|---|---|---|---|
| ArmMbedCloud/device-simulator `a4a387f` | The whole tree: root modules (`config.py`, `device.py`, `lwm2m.py`, `bootstrap.py`, `base_resource.py`, `update_resources.py`, `nodevice.py`, ...), the vendored `aiocoap/` (MIT) and `lwm2mclient/` packages, `requirements.txt` | `/opt/device-simulator`, on `PYTHONPATH` of `simulated_client/client0:6` | 2.0 MB, 101 `.py` files |
| device-simulator `requirements.txt` | 25 pins for Python 3.6 and OpenSSL 1.1, among them `python3-dtls==1.0.3`, `mbed-cloud-sdk==2.0.4`, `manifest-tool==1.5.2`, `cryptography==2.4.2` | A separate interpreter at `/opt/simulator-python` (`Dockerfile:25-33,40`), with a `sed` patch to `python3-dtls` (`Dockerfile:28-31`) | - |
| IzumaNetworks/pelion-system-tests `c9056ed` | `simulated_client/testapp.py` (784 lines) and `simulated_client/provision.py` (57 lines) | `simulated_client/` beside `example.py` and `client0` (`Dockerfile:43`) | 33 KB |

`simulated_client/example.py:15-21` imports `aiocoap`, `testapp`,
`base_resource` and `bootstrap`; `testapp.py` imports `aiocoap`,
`lwm2mclient.encdec`, `config`, `device`, `lwm2m` and `update_resources`. The
suite needs all of it to register, observe, factory reset and update.

Two ways to remove the dependency:

- *Vendor.* Copy the device-simulator tree and the two system-tests files
  into this repo. Cost: 2 MB of Python written for 3.6 enters a public
  Apache-2.0 repo. Neither ArmMbedCloud/device-simulator nor
  IzumaNetworks/pelion-system-tests carries a `LICENSE` file, so the owners
  of both must agree to publish the code and choose its license before any
  file lands. The vendored `aiocoap/` is MIT and can be published as is.
  Updates to the simulator then need a manual copy.
- *Depend on a published artifact.* Build the simulator in its own repo and
  consume it from a registry. ArmMbedCloud/device-simulator already builds
  an image (`device-simulator:2020.07`, `KIND=tests` in its `nucloud.env`),
  but the stamped workflow's push step exits before pushing a `KIND=tests`
  image (`nucloud.yml:93`), and a GHCR package of a private repo is private,
  so a public repo cannot pull it without a token. Cost: a push rule and a
  public package (or a PyPI release) for device-simulator, the same
  publication decision as vendoring for `testapp.py` and `provision.py`,
  which belong to no package, and a Dockerfile rewrite of the `sources` and
  `simulator` stages to pull instead of fetch.

Either way the `sources` stage (`Dockerfile:5-20`), `SSH=1` in `nucloud.env`
and the two `.gitignore` lines go away.

**Status.** Open. Blocks CI only; `make build` and `make test` from a
developer checkout with a loaded SSH agent work. Decide before `nucloud`
becomes the default branch.

### D2: one case does not run on k3s-golden

**Symptom.** `make test MACHINE=k3s-golden ACCOUNT=clitest` reports
9 passed, 1 skipped: `tests/read-only-tests.py::test_guard_refuses_a_write`
with reason "only a read-only stage has a guard".

**Cause.** `tests/read-only-tests.py:48-51` marks the case `skipif` unless
`NUCLOUD_READ_ONLY=1`. `scripts/nucloud-test.sh:32-37` sets that variable
only for a stage whose name does not start with `k3s-`, so on a k3s stage
there is no guard to prove and the case skips.

**Evidence.** Team log ledger row: `k3s-golden 9 0 1 ... Not run: 1, the
guard case, staging only`.

**Options.** None needed. The case exists to prove the guard that protects
staging; a k3s stage takes writes and has no guard.

**Status.** By design.

### D3: seven cases do not run on staging

**Symptom.** `make test MACHINE=staging` reports 2 passed, 1 passed offline
(the guard case), 7 skipped.

**Cause.** Two reasons.

- Six device cases (`tests/dev-client-tests.py`, `test_01` to `test_06`):
  `scripts/nucloud_plugin.py:33-37` marks every case in that file skipped
  with "blocked: bootstrapping a device is a write: staging is read-only".
  Registering a simulated device creates a developer certificate and a
  device, both writes.
- `tests/read-only-tests.py::test_get_update_campaigns`: staging answers
  `404` to `GET /v3/update-campaigns`, and `read-only-tests.py:43-44` skips
  with "blocked: the stage has no /v3/update-campaigns route". This is a
  stage finding, not a suite defect.

The guard itself counts as offline: `scripts/nucloud_plugin.py:16-26`
replaces `requests.sessions.Session.request` and raises before any method
other than GET or OPTIONS leaves the process, so `test_guard_refuses_a_write`
passes without a network call.

**Evidence.** Team log ledger rows: `staging 2 0 7 ... GET only, HTTP guard.
Not run: 6 device cases, bootstrapping writes; 1 update-campaign case,
/v3/update-campaigns answers 404 on staging` and `offline 1 0 0 ... The guard
refuses a write before it leaves the process`. Team log finding: "GET
/v3/update-campaigns answers 404 on staging."

**Options.** None in this repo. The device cases need a stage that takes
writes. The campaign case runs once staging serves `/v3/update-campaigns`.

**Status.** By design (device cases); external (campaign route).

### D4: `docs/nucloud.md` names a file that does not exist

**Symptom.** `docs/nucloud.md:158` reads "`docs/fixes.md` lists every change
the `nucloud` branch makes to build files or source, and why." `docs/`
holds only `nucloud.md` and this file.

**Cause.** The stamped `docs/nucloud.md` expects every repo to carry
`docs/fixes.md`; this repo has none.

**Evidence.** `ls docs` prints `defects.md nucloud.md`.

**Options.** Write `docs/fixes.md` from the `nucloud` branch's changes to
build files and source (commit `b6c2f1f` lists them), or drop the paragraph.

**Status.** Open.

### D5: `manifest_tool.init` passes flags `manifest-dev-tool` 2.6.2 lacks

**Symptom.** A call to `client_test_lib.tools.manifest_tool.init` fails,
because `manifest-dev-tool init` rejects `-d`, `-m`, `-q` and `-f`.

**Cause.** `client_test_lib/tools/manifest_tool.py:47-56` builds the command
with those flags; `requirements.txt:1` pins `manifest-tool==2.6.2`, whose
`init` takes neither. No fixture calls `init`: `client_test_lib/fixtures/cloud_fixtures.py:174,285`
call only `create_manifest`, and `scripts/nucloud-test.sh:44` runs
`manifest-dev-tool init -u "$CLOUD_API_GW"` directly.

**Evidence.** Team log finding of 2026-11-04 on `manifest_tool.init`: the
`-d -m -q -f` flags are absent from `manifest-dev-tool` 2.6.2, and no fixture
calls `init`.

**Options.** Rewrite `init` for the 2.x command line
(`manifest-dev-tool init -u <api url> [-a <api key>]`), or delete it.

**Status.** Open, dormant. Nothing in the suite reaches the code.

## Related repository

ArmMbedCloud/pelion-e2e-python-test-library-internal is private
(`gh repo view ... --json visibility` answers `PRIVATE`) and is a near copy of
this repo:

- Its `README.md:11` names itself the "internal work repository for public
  pelion python test library: https://github.com/ARMmbed/pelion-e2e-python-test-library",
  and GitHub redirects that name to PelionIoT/client-e2e-python-test-library.
  `changelog.md` of this repo records the rename to
  client-e2e-python-test-library at 0.4.0 (2023-12-11), with
  `PELION_CLOUD_API_KEY` and `PELION_CLOUD_API_GW` becoming `CLOUD_API_KEY`
  and `CLOUD_API_GW`.
- The two histories share no commit. Root commits: this repo 2019-06-13
  (`6cb01a5`), the internal repo 2019-06-18 (`0db23d3`). The internal
  `master` ends at `18a937e` (2020-09-15, manifest tool v2); this repo's
  `master` ends at `717b5dc` (2025-09-25).
- Same cases, same counts: `tests/dev-client-tests.py` holds `test_01` to
  `test_06` and `tests/read-only-tests.py` the same four GET and guard cases
  in both. The package is `pelion_test_lib` there and `client_test_lib`
  here; the environment variables carry the `PELION_` prefix there.
- Same `nucloud` build: the internal `Dockerfile` has the same `sources`
  stage with the same two pinned refs, and its `nucloud.env` sets `SSH=1`.
  Because the internal repo is private and `scripts/runner-groups.sh`
  lists it in the ArmMbedCloud group, its CI gets a runner and the key, so
  D1 does not apply to it.
- Same results: the team log ledger rows for the internal repo read
  k3s-golden 9/0/1, staging 2/0/7, offline 1/0/0, with the same reasons.

## Run results

Runs on 2026-11-04 from a developer checkout with `make test`, account
`clitest` on k3s-golden. Counts are passed / failed / not run.

| Stage | Passed | Failed | Not run | Notes |
|---|---|---|---|---|
| k3s-golden | 9 | 0 | 1 | 6 device cases on a simulated device (register, GET, PUT, subscribe with a websocket notification, factory reset with a new device id, update to deployed) and 3 read-only cases. Not run: the guard case (D2). The update case applies no firmware and checks no signature. |
| staging | 2 | 0 | 7 | GET only, behind the HTTP guard. Not run: 6 device cases, bootstrapping writes; `test_get_update_campaigns`, `/v3/update-campaigns` answers 404 (D3). |
| offline | 1 | 0 | 0 | `test_guard_refuses_a_write`: the guard refuses a write before it leaves the process. |

After each k3s-golden run the account holds 0 trusted certificates,
0 firmware images, 0 manifests, 0 campaigns and 1 API key. Devices stay;
the cloud cannot delete them.

Source: IzumaNetworks/nucloud team log `libs.log.md` (queensnake, 2026-11-04).
