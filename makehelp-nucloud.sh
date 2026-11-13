#!/usr/bin/env bash
# nucloud image repo helper. Stamped from IzumaNetworks/nucloud
# templates/makehelp.sh; identical in every repo. Reads nucloud.env:
#
#   REPO=<org>/<repo>
#   IMAGES=(                      # one entry per image this repo builds
#     "name|upstream_tag|dockerfile|context|target|release"
#   )   # target: Dockerfile stage or "-"; release: helm release on k3s, "-" for none,
#         # or "release=values.key" when the chart's tag key is not image.tag
#   SECRETS=(fa_token=FA_PRO_TOKEN)   # BuildKit secrets: id=ENVVAR
#   SSH=1                         # forward the ssh agent to the build
#   PLATFORM=linux/amd64
#   SMOKE_CMD=(...)               # command run by `make smoke`, default: none (image must start)
#   SMOKE_<name>=(...)            # per-image override; <name> with every non-alphanumeric as _ (SMOKE_iam_policies)
#   KIND=tests                    # a test repo: one image holds the suite, which runs against a stage's API
#   SETUP_CMD=(...)               # tests: in the image, creates or verifies the suite's own fixtures; safe to repeat;
#                                 # make test runs it first, and a failure is reported as setup, never as a test result
#   HOST_SETUP_CMD=(...)          # tests: the same preparation run on this host (it needs host access, e.g. kubectl)
#   TEST_CMD=(...)                # tests: runs the suite in the image
#   HOST_TEST_CMD=(...)           # tests: runs the suite from this host instead
#   TEST_STAGE=no                 # tests: TEST_CMD needs no stage (a library's own tests)
#   CREDENTIALS=(API_KEY)         # tests: the encrypted izmachine facts make prereqs requires on each cloud, default
#                                 # API_KEY; any of API_KEY USER PASSWORD ROOT_USER ROOT_PASSWORD CONFIG_JSON ACCOUNT_ID
#                                 # KUBECONFIG. The suite receives every one of them the cloud holds.
#   HOST_TOOLS=("kubectl|hsm setup" "py:yaml|kubeconfig parsing")  # tools and python modules this repo needs on the host
#   PREREQS_CMD=(...)             # a read-only repository check run last by make prereqs
#   HTTP_LOG=no                   # tests: no per-request log (.nucloud-logs/<stage>/http.log)
#   TIMINGS=no                    # tests: no per-case pytest durations (--durations=0 via PYTEST_ADDOPTS)
#   SUITE_START_TIMEOUT=120       # tests: seconds for the suite container to leave Created before the run aborts
#   EXTRA_ACCOUNTS=(staging=edge)  # tests: more accounts, as NUCLOUD_ACCOUNT_<NAME>_{API_KEY,USER,PASSWORD,CONFIG_JSON}
#   TEST_FRAMEWORK=behave         # tests: how TAGS= reaches the suite: behave|cucumber|pytest|none (default)
#   ACCOUNTS=(staging=edge)       # tests: the cloud.accounts.<name> a stage uses unless ACCOUNT= is given
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
ENV="${MACHINE:-${ENV:-}}"
# nucloud.conf is the one settings file for a workspace: BUILD_ROOT (the source
# checkouts) and DOCKER_CONTEXT (the build context). It is found in the nearest
# directory above this checkout (setup.sh writes <dir>/NUCLOUD/nucloud.conf), else at
# ${XDG_CONFIG_HOME:-~/.config}/nucloud/nucloud.conf. The environment overrides each key.
# The build context is DOCKER_CONTEXT from the environment, else from nucloud.conf, else
# Docker's current context.
conf_file() { # conf_file <dir>: the nucloud.conf that governs <dir>, or nothing
    local d=$1
    while d=$(dirname "$d"); [[ $d != / ]]; do [[ -f $d/nucloud.conf ]] && { echo "$d/nucloud.conf"; return 0; }; done
    d=${XDG_CONFIG_HOME:-$HOME/.config}/nucloud/nucloud.conf
    [[ -f $d ]] && echo "$d"
}
CONF=$(conf_file "$PWD") || CONF=
CONTEXT_FROM=
if [[ -n ${DOCKER_CONTEXT:-} ]]; then
    CONTEXT_FROM='DOCKER_CONTEXT'
elif [[ -n $CONF ]] && c=$(sed -n 's/^DOCKER_CONTEXT=//p' "$CONF" | tail -1) && [[ -n $c ]]; then
    export DOCKER_CONTEXT=$c; CONTEXT_FROM=$CONF
fi
# Color and hyperlinks: COLOR=always|never wins; otherwise only on a terminal,
# never under NO_COLOR (https://no-color.org) or TERM=dumb.
case "${COLOR:-auto}" in
    always) TTY=1 ;;
    never) TTY= ;;
    *) if [[ -t 1 && -z "${NO_COLOR:-}" && "${TERM:-}" != dumb ]]; then TTY=1; else TTY=; fi ;;
esac
if [[ -n $TTY ]]; then
    C_OK=$'\033[32m' C_FAIL=$'\033[1;31m' C_WARN=$'\033[33m' C_NAME=$'\033[36m' C_BOLD=$'\033[1m' C_DIM=$'\033[2m' C_OFF=$'\033[0m'
else
    C_OK= C_FAIL= C_WARN= C_NAME= C_BOLD= C_DIM= C_OFF=
fi

# Clouds come from .iz then .izlocal parsed as structured TOML by nucloud-cloud.py,
# stamped beside this file: top-level [machine.<stage>] entries only; their nested
# .labels/.facts/.functions tables are metadata, never stages.
CLOUD=(python3 ./nucloud-cloud.py)
stage_list() { "${CLOUD[@]}" stages; }            # "<stage>\t<file>\t<remote>\t<note>" per machine
production_stages() { "${CLOUD[@]}" production; } # the stages in [nucloud] production
endpoint_stages() { "${CLOUD[@]}" endpoints; }    # "<stage>\t<api url>" per [nucloud] endpoints entry
api_only_stages() { # "<stage>\t<api url>" per endpoint with no machine: nucloud reaches it through its API alone
    endpoint_stages | awk -F'\t' -v m=" $(stage_list | cut -f1 | tr '\n' ' ') " 'index(m, " " $1 " ") == 0'
}

show_help() { # make help: the nucloud targets, the variables they read, and a wrapper repo's own targets
    local stages prod native shadow kind endpoints
    kind=$(sed -n 's/^KIND=//p' nucloud.env 2>/dev/null | tail -1)
    printf '\nUsage:\n  make %s<target>%s [MACHINE=<stage>] [ONLY=<image>]\n' "$C_NAME" "$C_OFF"
    awk -v C="$C_NAME" -v B="$C_BOLD" -v O="$C_OFF" -v kind="$kind" 'BEGIN { FS = ":.*##" }
        /^##@/ { sec = substr($0, 5); hide = kind == "tests" && sec == "Deploy"
            if (hide) next
            printf "\n%s%s%s\n", B, (kind == "tests" && sec == "Test" ? "Testing" : sec), O; next }
        /^[a-zA-Z_-]+:.*##/ { if (hide || (kind != "tests" && $1 == "setup")) next
            d = $2; sub(/^ +/, "", d)
            if (kind == "tests" && $1 == "test") d = "Run the suite against a stage: MACHINE=<stage>"
            printf "  %s%-14s%s %s\n", C, $1, O, d }' Makefile.nucloud
    prod=$(production_stages | tr '\n' ' '); prod=${prod% }
    stages=$(stage_list | cut -f1 | grep -vxF "$(production_stages; echo __none__)" | tr '\n' ' '); stages=${stages% }
    endpoints=$(api_only_stages | cut -f1 | tr '\n' ' '); endpoints=${endpoints% }
    [[ $kind != tests || -z $endpoints ]] || stages+=" $endpoints"
    printf '\n%sVariables%s\n' "$C_BOLD" "$C_OFF"
    printf '  %s%-14s%s %s\n' "$C_NAME" "MACHINE=" "$C_OFF" "the stage for stage targets: ${stages:-none in .iz or .izlocal}"
    if [[ $kind == tests ]]; then
        [[ -z $prod ]] || printf '  %-14s %s\n' "" "$prod: production, a test target; nucloud never deploys there"
    else
        [[ -z $prod ]] || printf '  %-14s %s\n' "" "$prod: production, read-only (running, stage-check, kubeconfig)"
    fi
    printf '  %-14s %s\n' "" "${ENV:+now $ENV; }unset: a picklist on a terminal, an error elsewhere"
    printf '  %s%-14s%s %s\n' "$C_NAME" "ONLY=" "$C_OFF" "one image by name (make images lists them)"
    printf '  %s%-14s%s %s\n' "$C_NAME" "IMAGE_SUFFIX=" "$C_OFF" "an earlier build for deploy-only, image-load, smoke, sbom"
    printf '  %s%-14s%s %s\n' "$C_NAME" "ARGS=" "$C_OFF" "arguments for run"
    printf '  %s%-14s%s %s\n' "$C_NAME" "COLOR=" "$C_OFF" "always or never; default: color on a terminal unless NO_COLOR is set"
    grep -q '^# nucloud entrypoint' Makefile 2>/dev/null || return 0
    printf '  %s%-14s%s %s\n' "$C_NAME" "NATIVE=1" "$C_OFF" "run this repository's own rule for a target nucloud also defines"
    shadow=" $(sed -n 's/^NUCLOUD_TARGETS := //p' Makefile) "
    # the repo's own rules: the Makefile outside the nucloud block, and the files its native branch includes
    local own inc
    own=$(sed '/^# nucloud entrypoint/,/^else$/d' Makefile)
    for inc in $(printf '%s\n' "$own" | sed -nE 's/^-?include[[:space:]]+//p'); do
        [[ -f $inc && $inc != Makefile.nucloud ]] && own+=$'\n'$(cat "$inc")
    done
    native=$(printf '%s\n' "$own" | { grep -oE '^[a-zA-Z0-9_.-]+:([^=]|$)' || true; } | sed 's/:.*//' | { grep -v '^\.' || true; } | sort -u)
    [[ -n $native ]] || return 0
    printf '\n%sRepository targets%s %s(this repository'"'"'s own Makefile; * also a nucloud target: NATIVE=1 make <target>)%s\n' "$C_BOLD" "$C_OFF" "$C_DIM" "$C_OFF"
    printf '%s\n' "$native" | awk -v sh="$shadow" '{ n = $0; if (index(sh, " " n " ")) n = n "*"
        if (len + length(n) + 2 > 78) { print line; line = ""; len = 0 }
        line = line "  " n; len = length(line) } END { if (line) print line }'
}
[[ ${1:-} != help ]] || { show_help; exit 0; }

if (( BASH_VERSINFO[0] * 100 + BASH_VERSINFO[1] < 403 )); then
    echo "error: this helper needs bash 4.3 or newer; $BASH runs $BASH_VERSION (macOS: brew install bash)" >&2; exit 1
fi
[[ -f nucloud.env ]] || { echo "error: nucloud.env missing" >&2; exit 1; }
REGISTRY=ghcr.io/izumanetworks
SECRETS=() SSH=0 PLATFORM=linux/amd64 SMOKE_CMD=() KIND=image SETUP_CMD=() TEST_CMD=() TEST_STAGE=yes
CREDENTIALS=(API_KEY) EXTRA_ACCOUNTS=() HOST_TOOLS=() PREREQS_CMD=() HOST_SETUP_CMD=() HOST_TEST_CMD=() TEST_FRAMEWORK=none ACCOUNTS=()
# shellcheck disable=SC1091
source nucloud.env
ONLY="${ONLY:-}"
GIT_HEAD="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
# CI tags <upstream>-nucloud.<run number>. A local build tags
# <upstream>-nucloud.dev.<commit>, plus a hash of any uncommitted changes, so
# every changed tree deploys under a new tag and its pods restart.
if [[ -n "${BUILD_NUMBER:-}" ]]; then
    SUFFIX="nucloud.$BUILD_NUMBER"
else
    # BUILD_NUMBER stays empty: it is exported, and a nested make (HOST_TEST_CMD) computes its own dev tag
    SUFFIX="nucloud.dev.${GIT_HEAD:0:7}"
    if [[ -n "$(git status --porcelain -- . ':!sbom-*' 2>/dev/null)" ]]; then
        SUFFIX+=".$({ git diff HEAD; git ls-files -o --exclude-standard -z -- . ':!sbom-*' | xargs -0 cat; } | git hash-object --stdin | cut -c1-7)"
    fi
fi

die() { echo "error: $*" >&2; exit 1; }
say() { printf '==> %s\n' "$*"; }
need_stage() { # need_stage [change|api]: MACHINE= names the stage; otherwise a picklist on a terminal, a refusal elsewhere.
    # With "change" (image-load, deploy, deploy-only) a production stage is refused and left out of the picklist.
    # With "api" (prereqs, setup, test in a test repo) the API-only stages join the list; every other mode refuses them.
    local -a stages=() files=() remotes=() notes=()
    local s f r n i choice prod endpoints
    prod=" $(production_stages | tr '\n' ' ') "
    endpoints=" $(api_only_stages | cut -f1 | tr '\n' ' ') "
    if [[ -n $ENV ]]; then
        [[ ${1:-} == api || $endpoints != *" $ENV "* ]] || die "$ENV is an API-only stage: nucloud reaches it through its API and has no VM to act on"
        [[ ${1:-} != change || $prod != *" $ENV "* ]] || die "$ENV is production; nucloud builds are never deployed there (.iz [nucloud] production)"
        return 0
    fi
    while IFS=$'\t' read -r s f r n; do
        if [[ $prod == *" $s "* ]]; then
            [[ ${1:-} == change ]] && continue
            if [[ ${1:-} == api ]]; then n="production, tests only"; else n="production, read-only"; fi
        fi
        stages+=("$s"); files+=("$f"); remotes+=("$r"); notes+=("$n")
    done < <(stage_list)
    if [[ ${1:-} == api ]]; then
        while IFS=$'\t' read -r s r; do
            [[ -n $s ]] && { stages+=("$s"); files+=(""); remotes+=(""); notes+=("API only: $r"); }
        done < <(api_only_stages)
    fi
    [[ ${#stages[@]} -gt 0 ]] || die "no [machine.<stage>] in .iz or .izlocal"
    [[ -t 0 && -t 2 ]] || die "MACHINE=<stage> is required; stages: ${stages[*]}"
    printf '%sChoose a stage%s %s(or pass MACHINE=<stage>)%s\n' "$C_BOLD" "$C_OFF" "$C_DIM" "$C_OFF" >&2
    for i in "${!stages[@]}"; do
        printf '  %s%2d%s  %s%-12s%s %-13s %s%s%s\n' "$C_NAME" "$((i + 1))" "$C_OFF" "$C_BOLD" "${stages[i]}" "$C_OFF" "${remotes[i]:+on ${remotes[i]}}" "$C_DIM" "${notes[i]:-${files[i]}}" "$C_OFF" >&2
    done
    while :; do
        read -r -p "stage [1-${#stages[@]}]: " choice || die "no stage chosen"
        if [[ $choice =~ ^[0-9]+$ && $choice -ge 1 && $choice -le ${#stages[@]} ]]; then ENV=${stages[choice - 1]}; break; fi
        for i in "${!stages[@]}"; do [[ $choice == "${stages[i]}" ]] && { ENV=$choice; break 2; }; done
        printf '%sno such stage: %s%s\n' "$C_FAIL" "$choice" "$C_OFF" >&2
    done
    printf '%s==> stage %s%s\n' "$C_BOLD" "$ENV" "$C_OFF" >&2
}

if [[ -n "${IMAGE_SUFFIX:-}" ]]; then
    [[ "$IMAGE_SUFFIX" =~ ^nucloud\.(dev\.[a-f0-9]{7,40}(\.[a-f0-9]{7})?|[0-9]+)$ ]] || die "invalid IMAGE_SUFFIX=$IMAGE_SUFFIX"
    case "${1:-}" in
        images|image-load|deploy-only|upgrade|sbom|smoke) SUFFIX=$IMAGE_SUFFIX ;;
        *) die "IMAGE_SUFFIX selects existing images; omit it for builds and pushes" ;;
    esac
fi

each() { # each <fn>: call fn name tag dockerfile context target release ref
    local e name tag df ctx tgt rel
    for e in "${IMAGES[@]}"; do
        IFS='|' read -r name tag df ctx tgt rel <<<"$e"
        [[ -z "$ONLY" || "$ONLY" == "$name" ]] || continue
        "$1" "$name" "$tag" "$df" "$ctx" "$tgt" "$rel" "$REGISTRY/$name:$tag-$SUFFIX"
    done
}

guard_tag() { [[ "$1" == *-nucloud.* ]] || die "refusing $1: not a -nucloud.<n> tag"; }

# A build context holding .nucloud-logs/ (unredacted service logs from earlier runs) must exclude it, or a
# `COPY . /work` bakes those logs into the image. BuildKit reads <dockerfile>.dockerignore before <context>/.dockerignore.
guard_logs() { # guard_logs <context> <dockerfile> <ref>
    local ign=$1/.dockerignore
    [[ -d $1/.nucloud-logs ]] || return 0
    [[ -f $2.dockerignore ]] && ign=$2.dockerignore
    grep -qsxE '/?\.nucloud-logs/?' "$ign" ||
        die "refusing $3: $ign does not exclude .nucloud-logs/, so the build would copy run logs into the image; add a .nucloud-logs/ line"
}

i_list() { printf '%-50s %s\n' "$1" "$7"; }

i_build() {
    local name=$1 df=$3 ctx=$4 tgt=$5 ref=$7 args=() s
    guard_tag "$ref"
    guard_logs "$ctx" "$df" "$ref"
    for s in "${SECRETS[@]}"; do
        args+=(--secret "id=${s%%=*},env=${s#*=}")
    done
    [[ "$SSH" == 1 ]] && args+=(--ssh default)
    [[ "$tgt" != "-" && -n "$tgt" ]] && args+=(--target "$tgt")
    say "build $ref on $(docker context show) ($PLATFORM)"
    DOCKER_BUILDKIT=1 docker buildx build --load --platform "$PLATFORM" "${args[@]}" \
        --build-arg GIT_HEAD="$GIT_HEAD" --build-arg BUILD_NUMBER="${BUILD_NUMBER:-0}" \
        --label org.opencontainers.image.revision="$GIT_HEAD" \
        --label org.opencontainers.image.source="https://github.com/$REPO" \
        --label org.opencontainers.image.version="$2-$SUFFIX" \
        -f "$df" -t "$ref" "$ctx"
}

i_sbom() { syft "$7" -o spdx-json > "sbom-${1//\//_}.spdx.json"; say "sbom-${1//\//_}.spdx.json"; }

i_smoke() {
    local ref=$7 cid var="SMOKE_${1//[^A-Za-z0-9]/_}"
    local -a cmd=("${SMOKE_CMD[@]}")
    if declare -p "$var" >/dev/null 2>&1; then local -n per=$var; cmd=("${per[@]}"); fi
    if [[ ${#cmd[@]} -gt 0 ]]; then
        docker run --rm --platform "$PLATFORM" --entrypoint "${cmd[0]}" "$ref" "${cmd[@]:1}"
    else
        cid=$(docker run -d --platform "$PLATFORM" "$ref")
        sleep 8
        if [[ "$(docker inspect -f '{{.State.Running}} {{.State.ExitCode}}' "$cid")" =~ ^(true|false\ 0) ]]; then
            say "$ref started"; docker rm -f "$cid" >/dev/null
        else
            docker logs --tail 20 "$cid" >&2; docker rm -f "$cid" >/dev/null; die "$ref exited"
        fi
    fi
}

stage_vm() { # the stage's incus remote and VM, "remote:guest": ./.iz and .izlocal through izmachine
    local hit
    command -v izmachine >/dev/null || die "izmachine is not on PATH; stage $ENV is resolved from .iz through it"
    [[ -f .iz ]] || die "no .iz in $PWD; stages are defined in .iz (make rollout in nucloud installs it)"
    hit=$(izmachine info "$ENV" --format json -f .iz 2>/dev/null | python3 -c '
import json, sys
want, raw = sys.argv[1], sys.stdin.read()
for g in (json.loads(raw).get("guests", []) if raw.strip() else []):
    if g.get("definition") == want and g.get("remote"):
        print(g["remote"] + ":" + g.get("guest", want)); break' "$ENV") || hit=
    [[ -n $hit ]] || die "stage $ENV is not defined in .iz or .izlocal"
    echo "$hit"
}

WORK=
work_dir() { [[ -n $WORK ]] || { WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT; }; }

STAGE_KC=
stage_kubeconfig() { # the stage's kubeconfig fact into $STAGE_KC (mode 600, removed on exit), API at its LAN address
    local hit
    [[ -z $STAGE_KC ]] || return 0
    hit=$(stage_vm)
    work_dir
    "${CLOUD[@]}" kubeconfig "$ENV" "$WORK/$ENV.kubeconfig" || die "cannot fetch $ENV's kubeconfig (machine ${hit#*:} on ${hit%%:*})"
    STAGE_KC=$WORK/$ENV.kubeconfig
}

release_chart() { # release_chart <kubeconfig> <release> <namespace> <dir>: write the installed chart from its newest release record
    local rec="$WORK/$2.release.json" rc=0
    kubectl --kubeconfig "$1" get secret -n "$3" -l "owner=helm,name=$2" -o json > "$rec" || die "cannot read release $2 on $ENV"
    python3 -I - "$rec" "$4" <<'PYCHART' || rc=$?
import base64, gzip, json, os, sys
rec, dest = sys.argv[1:3]
items = json.load(open(rec))["items"]
if not items:
    sys.exit("no release record")
best = max(items, key=lambda i: int(i["metadata"]["labels"]["version"]))
raw = base64.b64decode(base64.b64decode(best["data"]["release"]))
if raw[:2] == b"\x1f\x8b":
    raw = gzip.decompress(raw)
rel = json.loads(raw)
chart = rel["chart"]
if ("# Source: %s/charts/" % chart["metadata"]["name"]) in rel.get("manifest", "") and not chart.get("dependencies"):
    sys.exit(3)  # the release rendered vendored subcharts, which Helm does not keep in its record

def put(root, rel, data):
    path = os.path.normpath(os.path.join(root, rel))
    if os.path.isabs(rel) or not path.startswith(os.path.normpath(root) + os.sep):
        sys.exit("unsafe path in release: " + rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(data)

def write(c, root):
    os.makedirs(root, exist_ok=True)
    meta = dict(c["metadata"])
    present = {d["metadata"]["name"] for d in c.get("dependencies") or []}
    if meta.get("dependencies"):  # a disabled subchart is absent from the record but still listed in Chart.yaml
        meta["dependencies"] = [r for r in meta["dependencies"] if (r.get("alias") or r["name"]) in present]
    put(root, "Chart.yaml", json.dumps(meta).encode())
    put(root, "values.yaml", json.dumps(c.get("values") or {}).encode())
    for f in (c.get("templates") or []) + (c.get("files") or []):
        put(root, f["name"], base64.b64decode(f.get("data") or ""))
    if c.get("schema"):
        put(root, "values.schema.json", base64.b64decode(c["schema"]))
    for d in c.get("dependencies") or []:
        write(d, os.path.join(root, "charts", d["metadata"]["name"]))

write(chart, dest)
PYCHART
    case $rc in 0) ;; 3) return 3 ;; *) die "cannot recover the chart of release $2" ;; esac
}
platform_chart() { # platform_chart <release> <chart name>: the chart directory in an izuma-dm-platform checkout
    # NUCLOUD_PLATFORM, else NUCLOUD/INFRA/izuma-dm-platform beside this NUCLOUD/REPOS checkout (setup.sh)
    local root=${NUCLOUD_PLATFORM:-../../INFRA/izuma-dm-platform} dir
    dir=$(find "$root/charts" -name Chart.yaml -exec grep -l "^name: $2$" {} + 2>/dev/null | head -1 | xargs dirname 2>/dev/null) || dir=
    [[ -d "$dir" ]] || die "release $1 renders vendored subcharts that its cluster record does not keep; no chart $2 under $root/charts (set NUCLOUD_PLATFORM to an izuma-dm-platform checkout)"
    echo "$dir"
}

LOAD_REFS=()
i_load_ref() { LOAD_REFS+=("$7"); }
save_images() {
    local endpoint target port socket command wrapped
    endpoint=$(docker context inspect "$(docker context show)" --format '{{.Endpoints.docker.Host}}')
    if [[ -z "${DOCKER_HOST:-}" && "$endpoint" == ssh://* ]]; then
        read -r target port socket < <(python3 - "$endpoint" <<'PYURL'
import sys
from urllib.parse import unquote, urlparse
u = urlparse(sys.argv[1])
target = (unquote(u.username) + '@' if u.username else '') + u.hostname
print(target, u.port or 22, unquote(u.path))
PYURL
        )
        local -a args=(docker)
        [[ -z "$socket" || "$socket" == / ]] || args+=(--host "unix://$socket")
        args+=(image save "${LOAD_REFS[@]}")
        printf -v command '%q ' "${args[@]}"
        printf -v wrapped 'bash -o pipefail -c %q' "$command | gzip -1"
        # Compress beside the engine before the SSH transfer to this checkout.
        ssh -o BatchMode=yes -p "$port" "$target" "$wrapped"
    else
        docker save "${LOAD_REFS[@]}" | gzip -1
    fi
}
load_images() {
    local vm
    LOAD_REFS=()
    each i_load_ref
    [[ ${#LOAD_REFS[@]} -gt 0 ]] || die "no images selected for import"
    local ref actual
    for ref in "${LOAD_REFS[@]}"; do
        actual=$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$ref") || \
            die "missing existing image $ref; build first or set IMAGE_SUFFIX= to a completed build"
        [[ "$actual" == "$PLATFORM" ]] || die "$ref has platform $actual; expected $PLATFORM"
    done
    vm=$(stage_vm)
    say "import ${#LOAD_REFS[@]} image(s) into $vm"
    local try
    for try in 1 2; do
        if save_images | incus exec "$vm" -- k3s ctr images import -; then break; fi
        [[ $try == 1 ]] || die "image import into $vm failed twice"
        say "import into $vm failed; retrying once"
    done
}

DEPLOY_SETS=()  # "release|key=tag" collected per image, applied once per release
i_deploy() {
    # release field: "rel", "rel=values.key", or several joined by commas when
    # one image is set in more than one release ("mdscore=a.tag,mdsnotification=b.tag")
    local name=$1 ref=$7 m rel key
    [[ "$6" == "-" || -z "$6" ]] && { say "$name: no k3s release, skipped"; return; }
    for m in ${6//,/ }; do
        rel=${m%%=*} key=image.tag
        [[ "$m" == *=* ]] && key=${m#*=}
        DEPLOY_SETS+=("$rel|$key=${ref##*:}")
    done
}
deploy_wait() {
    local kc=$1 rel=$2 ns=${3:-default} workload_ns kind name recreate resources
    resources=$(kubectl --kubeconfig "$kc" get deploy,sts,ds --all-namespaces -o json | python3 -c '
import json,sys
rel,release_ns=sys.argv[1:3]
for obj in json.load(sys.stdin)["items"]:
    annotations=obj["metadata"].get("annotations",{})
    if annotations.get("meta.helm.sh/release-name") != rel or annotations.get("meta.helm.sh/release-namespace") != release_ns:
        continue
    spec=obj["spec"]; pod=spec["template"]["spec"]
    ports=pod.get("hostNetwork",False) or any(p.get("hostPort",0) for c in pod.get("containers",[]) for p in c.get("ports",[]))
    recreate=obj["kind"]=="Deployment" and spec.get("replicas",1)==1 and ports
    print(obj["metadata"]["namespace"],obj["kind"].lower(),obj["metadata"]["name"],"yes" if recreate else "no")
' "$rel" "$ns")
    while read -r workload_ns kind name recreate; do
        [[ -n "$kind" ]] || continue
        if [[ "$recreate" == yes ]]; then
            say "$rel: recreate single-replica host-port deployment $name"
            kubectl --kubeconfig "$kc" patch deployment "$name" -n "$workload_ns" --type merge \
                -p '{"spec":{"strategy":{"type":"Recreate","rollingUpdate":null}}}'
        fi
        kubectl --kubeconfig "$kc" rollout status "$kind/$name" -n "$workload_ns" --timeout=10m
    done <<< "$resources"
}
deploy_apply() {
    # helm upgrade with the release's current user-supplied values re-sent as
    # a file: changes only this repo's image tags and keeps every other value,
    # including tags another repo's images set in a shared release (helmfile
    # apply would reset those to chart defaults). Not --reuse-values: helm 4
    # copies the previous values into the chart record too, and a stage's
    # values (600 KB of certificates) then overflow the 1 MiB release secret.
    local kc rel e args chart prev ns releases
    [[ ${#DEPLOY_SETS[@]} -gt 0 ]] || return 0
    stage_kubeconfig; kc=$STAGE_KC
    prev="$WORK/values.yaml"
    releases=$(KUBECONFIG="$kc" helm list --all-namespaces -o json)
    for rel in $(printf '%s\n' "${DEPLOY_SETS[@]}" | cut -d'|' -f1 | sort -u); do
        args=()
        for e in "${DEPLOY_SETS[@]}"; do [[ "${e%%|*}" == "$rel" ]] && args+=(--set "${e#*|}"); done
        ns=$(printf '%s' "$releases" | python3 -c '
import json,sys
matches=[r["namespace"] for r in json.load(sys.stdin) if r["name"]==sys.argv[1]]
if len(matches)!=1:
    sys.exit("release must have one installed namespace: "+sys.argv[1])
print(matches[0])' "$rel")
        chart="$WORK/chart-$rel"
        if ! release_chart "$kc" "$rel" "$ns" "$chart"; then
            chart=$(KUBECONFIG="$kc" helm get metadata "$rel" -n "$ns" -o json | python3 -c 'import json,sys;print(json.load(sys.stdin)["chart"])')
            chart=$(platform_chart "$rel" "$chart")
        fi
        KUBECONFIG="$kc" helm get values "$rel" -n "$ns" -o yaml > "$prev"
        say "helm upgrade $rel on $ENV ${args[*]}"
        KUBECONFIG="$kc" helm upgrade "$rel" "$chart" -n "$ns" -f "$prev" "${args[@]}" --timeout 10m
        deploy_wait "$kc" "$rel" "$ns"
    done
    show_running
}

REL_LIST=()
i_rel() { # collect the helm releases this repo's images deploy to
    local m
    [[ "$6" == "-" || -z "$6" ]] && return
    for m in ${6//,/ }; do REL_LIST+=("${m%%=*}"); done
}
show_timings() { # each TESTMASTER test's measured average, last duration, runs, result and tier; never inferred
    local reg=.claude/testmaster/registry.json
    [[ -f $reg ]] || { say "no TESTMASTER registry at $reg; adopt the suite with /testmaster adopt"; return 0; }
    NUCLOUD_TTY=$TTY python3 - "$reg" <<'PY'
import json, os, sys
tty = bool(os.environ.get('NUCLOUD_TTY'))
C = dict(fast="\033[32m", standard="\033[36m", slow="\033[33m", unmeasured="\033[2m", off="\033[0m") if tty else dict.fromkeys(("fast", "standard", "slow", "unmeasured", "off"), "")
tests = json.load(open(sys.argv[1])).get('tests', {})
def tier(ms): return 'unmeasured' if ms is None else 'fast' if ms <= 10000 else 'standard' if ms <= 120000 else 'slow'
def dur(ms):
    if ms is None: return '-'
    m, r = divmod(ms, 60000)
    return (f'{int(m)}m ' if m else '') + f'{r / 1000:.3f}s'
rows, count = [], {}
for tid, t in sorted(tests.items()):
    avg = t.get('avg_ms') if t.get('runs', 0) else None
    tr = tier(avg); count[tr] = count.get(tr, 0) + 1
    rows.append((tid, dur(avg), dur(t.get('last_ms') if avg is not None else None), str(t.get('runs', 0)), t.get('last_result', '-') if avg is not None else '-', tr))
w = max([len(r[0]) for r in rows] + [4])
print(f"  {'TEST':<{w}}  {'AVERAGE':>11}  {'LAST':>11}  {'RUNS':>4}  {'RESULT':<7} TIER")
for tid, a, l, n, res, tr in rows:
    print(f"  {tid:<{w}}  {a:>11}  {l:>11}  {n:>4}  {res:<7} {C[tr]}{tr}{C['off']}")
print('==> ' + ', '.join(f'{count.get(k, 0)} {k}' for k in ('fast', 'standard', 'slow', 'unmeasured')) + '; tiers from measured averages: fast <=10s, standard <=120s, slow >120s')
PY
}
show_running() { # a table per release this repo deploys: each workload, its readiness, image and build
    local kc rel branch
    REL_LIST=()
    each i_rel
    [[ ${#REL_LIST[@]} -gt 0 ]] || { say "no k3s release in this repo"; return 0; }
    stage_kubeconfig; kc=$STAGE_KC
    branch=$(git branch --show-current 2>/dev/null || echo "")
    for rel in $(printf '%s\n' "${REL_LIST[@]}" | sort -u); do
        python3 -I - "$kc" "$rel" "$ENV" "$REPO" "$REGISTRY" "$branch" "$GIT_HEAD" "${TTY:-}" <<'PYTABLE'
import json, os, re, subprocess, sys
kc, rel, stage, repo, registry, branch, head, tty = sys.argv[1:9]
C = dict(ok="\033[32m", bad="\033[1;31m", name="\033[36m", bold="\033[1m", dim="\033[2m", off="\033[0m") if tty else dict.fromkeys(("ok", "bad", "name", "bold", "dim", "off"), "")
def link(text, url): return "\033]8;;%s\033\\%s\033]8;;\033\\" % (url, text) if tty else text
def run(*a): return json.loads(subprocess.check_output(a, text=True, env=dict(os.environ, KUBECONFIG=kc)))
def git(*a):
    try: return subprocess.check_output(("git",) + a, text=True, stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError: return None
hit = [r for r in run("helm", "list", "--all-namespaces", "-o", "json") if r["name"] == rel]
if not hit:
    print("%s==> %s%s not installed on %s" % (C["bold"], rel, C["off"], stage)); sys.exit(0)
r = hit[0]
status = r.get("status", "unknown")
ok = status == "deployed"
print("%s==> %s on %s%s  namespace %s  rev %s  %s%s%s" % (C["bold"], rel, stage, C["off"], r["namespace"], r.get("revision", "?"), C["ok"] if ok else C["bad"], status, C["off"]))
if branch:
    print("    branch %s at %s  images in %s" % (link(branch, "https://github.com/%s/tree/%s" % (repo, branch)), link(head[:7], "https://github.com/%s/commit/%s" % (repo, head)), registry))
org = registry.split("/", 1)[1] if "/" in registry else registry
rows = []  # (plain cells, styled cells)
for o in run("kubectl", "--kubeconfig", kc, "get", "deploy,sts,ds", "-A", "-o", "json")["items"]:
    a = o["metadata"].get("annotations", {})
    if a.get("meta.helm.sh/release-name") != rel or a.get("meta.helm.sh/release-namespace") != r["namespace"]:
        continue
    st = o.get("status", {})
    want = o["spec"].get("replicas", st.get("desiredNumberScheduled", 1))
    have = st.get("readyReplicas", st.get("numberReady", 0))
    ready = "%s/%s" % (have, want)
    ready_s = (C["ok"] if have == want else C["bad"]) + ready + C["off"]
    for c in o["spec"]["template"]["spec"]["containers"]:
        image = c["image"]
        path, _, tag = image.rpartition(":")
        name = path[len(registry) + 1:] if path.startswith(registry + "/") else path
        image_s = link(name, "https://github.com/orgs/%s/packages/container/package/%s" % (org, name.replace("/", "%2F"))) + ":" + tag if name != path else image
        m = re.search(r"-nucloud\.(?:dev\.([0-9a-f]{7,40})(\.[0-9a-f]{7})?|(\d+))$", tag)
        if m and m.group(1):
            sha = m.group(1)
            behind = git("rev-list", "--count", sha + "..HEAD")
            state = "uncommitted changes" if m.group(2) else ("at HEAD" if behind == "0" else ("%s behind %s" % (behind, branch or "HEAD") if behind else "commit not in this checkout"))
            build, build_s = "%s (%s)" % (sha[:7], state), "%s (%s%s%s)" % (link(sha[:7], "https://github.com/%s/commit/%s" % (repo, sha)), C["ok"] if state == "at HEAD" else C["dim"], state, C["off"])
        elif m:
            build = build_s = "CI run %s" % m.group(3)
        else:
            build = build_s = "not a nucloud build"
        workload = "%s/%s" % (o["kind"].lower(), o["metadata"]["name"])
        rows.append(((workload, ready, image if name == path else name + ":" + tag, build), (C["name"] + workload + C["off"], ready_s, image_s, build_s)))
if not rows:
    print("    no workloads"); sys.exit(0)
hdr = ("WORKLOAD", "READY", "IMAGE", "BUILD")
w = [max(len(x) for x in col) for col in zip(hdr, *(p for p, _ in rows))]
print("    " + C["bold"] + "  ".join(h.ljust(n) for h, n in zip(hdr, w)) + C["off"])
for plain, styled in rows:
    print("    " + "  ".join(s + " " * (n - len(p)) for p, s, n in zip(plain, styled, w)))
PYTABLE
    done
}

i_push() {
    guard_tag "$7"
    [[ "$7" != *-nucloud.dev.* ]] || die "refusing $7: a local build; only CI pushes to GHCR"
    docker push "$7"
}

PREREQ_FAIL=()
# A test repo's credentials are encrypted izmachine facts on each cloud, read
# through nucloud-cloud.py: CREDENTIALS= in nucloud.env names the fields the suite
# reads (API_KEY USER PASSWORD ROOT_USER ROOT_PASSWORD CONFIG_JSON ACCOUNT_ID
# KUBECONFIG), as cloud.<field> facts; ACCOUNT=<name> selects cloud.accounts.<name>.*.
stage_api() { "${CLOUD[@]}" api "$1"; } # API_URL fact, else [nucloud] endpoints, else https://api.<stage>.izuma.io
stage_value() { "${CLOUD[@]}" value "$1" "$2"; }
wants() { local c; for c in ${CREDENTIALS[@]+"${CREDENTIALS[@]}"}; do [[ $c == "$1" ]] && return 0; done; return 1; }
stage_account() { # ACCOUNT from ACCOUNTS=(<stage>=<account>) for this stage, unless ACCOUNT= was given
    local p
    [[ -z ${ACCOUNT:-} ]] || return 0
    for p in ${ACCOUNTS[@]+"${ACCOUNTS[@]}"}; do
        if [[ ${p%%=*} == "$ENV" ]]; then ACCOUNT=${p#*=}; export ACCOUNT; say "account: $ACCOUNT (ACCOUNTS in nucloud.env)"; fi
    done
}
EXTRA_ENV=()
extra_accounts() { # EXTRA_ACCOUNTS=(<stage>=<name>): export NUCLOUD_ACCOUNT_<NAME>_<FIELD> for each field that account holds
    local p name var f v
    for p in ${EXTRA_ACCOUNTS[@]+"${EXTRA_ACCOUNTS[@]}"}; do
        [[ ${p%%=*} == "$ENV" ]] || continue
        name=${p#*=} var=$(tr 'a-z-' 'A-Z_' <<<"${p#*=}")
        for f in $("${CLOUD[@]}" extra-fields); do
            v=$(ACCOUNT=$name stage_value "$ENV" "$f") || die "cannot read $ENV's cloud.accounts.$name ${f,,} fact (EXTRA_ACCOUNTS)"
            [[ -n $v ]] || continue
            export "NUCLOUD_ACCOUNT_${var}_$f=$v"; EXTRA_ENV+=(-e "NUCLOUD_ACCOUNT_${var}_$f")
        done
        say "extra account: $name"
    done
}
suite_env() { # export NUCLOUD_STAGE, NUCLOUD_API_URL and NUCLOUD_<field> for every credential fact the cloud holds
    local f v
    need_stage api
    stage_account
    NUCLOUD_STAGE=$ENV NUCLOUD_API_URL=$(stage_api "$ENV") || die "cannot resolve $ENV's API URL"
    export NUCLOUD_STAGE NUCLOUD_API_URL
    if "${CLOUD[@]}" read-only | grep -qxF "$ENV"; then NUCLOUD_READ_ONLY=1; else NUCLOUD_READ_ONLY=; fi
    export NUCLOUD_READ_ONLY
    tag_env
    # Per-case durations without touching selection or verdicts: pytest prints each case's setup/call/teardown
    # time (`--durations=0`); TIMINGS=no in nucloud.env turns it off for a suite that cannot take it.
    if [[ ${TIMINGS:-yes} != no ]]; then PYTEST_ADDOPTS="${PYTEST_ADDOPTS:+$PYTEST_ADDOPTS }--durations=0"; export PYTEST_ADDOPTS; fi
    for f in API_KEY USER PASSWORD ROOT_USER ROOT_PASSWORD CONFIG_JSON ACCOUNT_ID; do
        v=$(stage_value "$ENV" "$f") || die "cannot read $ENV's ${f,,} fact${ACCOUNT:+ (ACCOUNT=$ACCOUNT)}"
        export "NUCLOUD_$f=$v"
    done
    extra_accounts
    if wants API_KEY && [[ -z $NUCLOUD_API_KEY ]]; then
        die "$ENV has no encrypted cloud.${ACCOUNT:+accounts.$ACCOUNT.}api_key fact: izmachine fact set $ENV cloud.${ACCOUNT:+accounts.$ACCOUNT.}api_key - --secret"
    fi
}
tag_env() { # NUCLOUD_TAGS, NUCLOUD_EXCLUDE_TAGS and NUCLOUD_TAG_ARGS: this run's selection in the suite's framework syntax
    local a=() line out
    [[ -f test-tags.toml ]] || return 0
    out=$(TEST_FRAMEWORK=$TEST_FRAMEWORK python3 ./nucloud-tags.py args "$TEST_FRAMEWORK") || die "TAGS/EXCLUDE_TAGS: see the error above"
    while IFS= read -r line; do [[ -n $line ]] && a+=("$line"); done <<<"$out"
    NUCLOUD_TAGS=${TAGS:-} NUCLOUD_EXCLUDE_TAGS=${EXCLUDE_TAGS:-} NUCLOUD_TAG_ARGS=${a[*]+$(printf '%q ' "${a[@]}")}
    NUCLOUD_TAG_ARGS=${NUCLOUD_TAG_ARGS% }
    export NUCLOUD_TAGS NUCLOUD_EXCLUDE_TAGS NUCLOUD_TAG_ARGS
    [[ -z $NUCLOUD_TAG_ARGS ]] || say "tags: $NUCLOUD_TAG_ARGS"
}
redact_secrets() { # stdin to stdout with this run's secret values, Izuma API keys and PEM private keys masked
    python3 -u -c '
import os, re, sys
keys = ["NUCLOUD_API_KEY", "NUCLOUD_PASSWORD", "NUCLOUD_ROOT_PASSWORD"] + [k for k in os.environ if re.fullmatch(r"NUCLOUD_ACCOUNT_\w+_(API_KEY|PASSWORD)", k)]
vals = sorted({os.environ.get(k, "") for k in keys} - {""}, key=len, reverse=True)
vals = [v for v in vals if len(v) >= 6]
key, pem = re.compile(r"\bak_[0-9A-Za-z]{20,}"), False
whole = re.compile(r"-----BEGIN ([A-Z ]*)PRIVATE KEY-----.*?-----END \1PRIVATE KEY-----")
opened = re.compile(r"-----BEGIN ([A-Z ]*)PRIVATE KEY-----.*")
for line in sys.stdin:
    for v in vals:
        line = line.replace(v, "<redacted>")
    line = key.sub("ak_<redacted>", line)
    if pem:  # inside a multi-line key: drop lines up to and including its END line
        if re.search(r"-----END [A-Z ]*PRIVATE KEY-----", line):
            pem = False
        continue
    line = whole.sub(r"<redacted \1private key>", line)  # a key on one line (JSON with escaped newlines)
    if opened.search(line):
        pem = True
        line = opened.sub(r"<redacted \1private key>", line).rstrip("\n") + "\n"
    sys.stdout.write(line)
'
}
suite_logs() { # copy the stopped suite container's /nucloud-logs to $1, masked like the suite's output, then remove the container
    local f t
    [[ $(docker inspect -f '{{.State.Running}}' "$SUITE_CONTAINER" 2>/dev/null) != true ]] || stop_suite
    docker cp "$SUITE_CONTAINER":/nucloud-logs/. "$1"/ >/dev/null 2>&1 || true
    # Service logs a suite copies out (mbed-client-service's server.log) can print keys: each text file passes through
    # redact_secrets in place, so no copy on this host keeps one.
    while IFS= read -r -d '' f; do
        grep -Iq . "$f" 2>/dev/null || continue
        t=$f.redact.$$
        if redact_secrets <"$f" >"$t"; then mv -f "$t" "$f"; else rm -f "$t"; fi
    done < <(find "$1" -type f ! -name '*.redact.*' -print0 2>/dev/null)
    docker rm -fv "$SUITE_CONTAINER" >/dev/null 2>&1 || true
}
# SIGTERM, then 60 s for the suite's EXIT trap to delete the cloud records it made, then SIGKILL. `docker rm -f` alone
# kills at once, so the trap never runs and the records stay on the stage.
stop_suite() { deadline 90 docker stop -t 60 "$SUITE_CONTAINER" >/dev/null 2>&1 || true; }
# deadline <seconds> <command...>: run a Docker client call, KILL it after <seconds>. A call over a dead SSH link to the
# engine otherwise blocks forever. KILL, because a signal trap ignores TERM and its children inherit that.
deadline() {
    local s=$1 p w rc; shift
    "$@" & p=$!
    { sleep "$s"; kill -KILL "$p"; } >/dev/null 2>&1 & w=$!
    wait "$p"; rc=$?
    kill -KILL "$w" 2>/dev/null; wait "$w" 2>/dev/null
    return "$rc"
}
# start_suite: start the created container detached and wait, up to SUITE_START_TIMEOUT seconds, for the engine to
# report it running or exited. A start lost on the way (the container stays Created) aborts the run.
start_suite() {
    local t=${SUITE_START_TIMEOUT:-120} end st=
    end=$((SECONDS + t))
    deadline "$t" docker start "$SUITE_CONTAINER" >/dev/null 2>&1 || true
    while :; do
        st=$(deadline 20 docker inspect -f '{{.State.Status}}' "$SUITE_CONTAINER" 2>/dev/null) || st=
        [[ $st == running || $st == exited ]] && return 0
        ((SECONDS < end)) || { echo "error: $SUITE_CONTAINER still ${st:-unreachable} after ${t}s; the Docker engine ($(docker context show 2>/dev/null)) did not start it" >&2; return 1; }
        sleep 2
    done
}
suite() { # suite <verb> <command...>: run a command of the suite image against the stage's API
    local verb=$1 ref; shift
    suite_env
    IFS='|' read -r n t _ <<<"${IMAGES[0]}"; ref=$REGISTRY/$n:$t-$SUFFIX
    # A remote BuildKit session can time out; one retry, then refuse rather than run a missing image.
    docker image inspect "$ref" >/dev/null 2>&1 || each i_build || true
    docker image inspect "$ref" >/dev/null 2>&1 || { say "build left no $ref; retrying once"; each i_build || true; }
    docker image inspect "$ref" >/dev/null 2>&1 || die "cannot build $ref; $verb did not run on $ENV"
    say "$verb on $ENV ($NUCLOUD_API_URL)"
    # The client is backgrounded so the trap runs on a signal; a killed client alone leaves the container calling the stage.
    SUITE_CONTAINER=nucloud-suite-$$
    # /nucloud-logs ($NUCLOUD_LOGS in the container) is an anonymous volume; a suite copies its service logs there,
    # typically from an EXIT trap. Afterwards docker cp brings them to .nucloud-logs/<stage>/ here, which works on a
    # remote Docker context where a bind mount would resolve on the engine's host.
    local logs=$PWD/.nucloud-logs/$ENV
    mkdir -p "$logs"
    if docker inspect "$SUITE_CONTAINER" >/dev/null 2>&1; then stop_suite; docker rm -fv "$SUITE_CONTAINER" >/dev/null 2>&1 || true; fi
    # nucloud-http.py goes in as the container's sitecustomize: Python's urllib3 then appends one line per request to
    # $NUCLOUD_LOGS/http.log (HTTP_LOG=no in nucloud.env turns it off). The image's PYTHONPATH is kept after it.
    local http=() pp
    if [[ ${HTTP_LOG:-yes} != no && -f nucloud-http.py ]]; then
        pp=$(docker image inspect "$ref" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | sed -n 's/^PYTHONPATH=//p' | head -1)
        http=(-e "PYTHONPATH=/nucloud-hooks${pp:+:$pp}" -e NUCLOUD_HTTP_LOG=/nucloud-logs/http.log)
    fi
    docker create --init --name "$SUITE_CONTAINER" --platform "$PLATFORM" -e NUCLOUD_STAGE -e NUCLOUD_API_URL -e NUCLOUD_API_KEY \
        -e NUCLOUD_USER -e NUCLOUD_PASSWORD -e NUCLOUD_ROOT_USER -e NUCLOUD_ROOT_PASSWORD -e NUCLOUD_CONFIG_JSON -e NUCLOUD_ACCOUNT_ID \
        -e NUCLOUD_READ_ONLY -e NUCLOUD_TAGS -e NUCLOUD_EXCLUDE_TAGS -e NUCLOUD_TAG_ARGS -e SUITES -e PYTEST_ADDOPTS ${EXTRA_ENV[@]+"${EXTRA_ENV[@]}"} \
        ${http[@]+"${http[@]}"} -v /nucloud-logs -e NUCLOUD_LOGS=/nucloud-logs "$ref" "$@" >/dev/null || die "cannot create the suite container from $ref"
    if [[ ${#http[@]} -gt 0 ]]; then
        local hooks; hooks=$(mktemp -d); cp nucloud-http.py "$hooks/sitecustomize.py"
        docker cp "$hooks/." "$SUITE_CONTAINER":/nucloud-hooks >/dev/null || die "cannot copy the request logger into $SUITE_CONTAINER"
        rm -rf "$hooks"
    fi
    # Output passes through redact_secrets: a suite that prints its key or password never leaves it in a log.
    start_suite || { stop_suite; suite_logs "$logs"; die "$verb did not start on $ENV"; }
    # The output streams from `docker logs -f`; `docker wait` gives the exit code. Both run in the background, so a
    # signal reaches the trap at once.
    (set -o pipefail; docker logs -f "$SUITE_CONTAINER" 2>&1 | redact_secrets) &
    local client=$! rc=0 code
    code=$(mktemp)
    trap 'trap "" HUP INT TERM; kill "$client" 2>/dev/null; stop_suite; suite_logs "$logs"; rm -f "$code"; exit 143' HUP INT TERM
    docker wait "$SUITE_CONTAINER" >"$code" 2>/dev/null &
    wait "$!" || rc=125
    [[ $rc != 0 ]] || rc=$(tr -dc 0-9 <"$code"); rc=${rc:-125}
    # the log stream ends with the container; it gets 30 s to drain
    local i
    for ((i = 0; i < 60; i++)); do kill -0 "$client" 2>/dev/null || break; sleep 0.5; done
    kill "$client" 2>/dev/null || true
    wait "$client" 2>/dev/null || true
    rm -f "$code"
    trap - HUP INT TERM
    suite_logs "$logs"
    return "$rc"
}
run_setup() { # the suite's own preparation, host step then container step; a failure is reported as setup
    local rc=0
    [[ ${#HOST_SETUP_CMD[@]} -gt 0 || ${#SETUP_CMD[@]} -gt 0 ]] || return 0
    if [[ ${#HOST_SETUP_CMD[@]} -gt 0 ]]; then
        suite_env; export MACHINE=$ENV; say "setup on $ENV (host)"; "${HOST_SETUP_CMD[@]}" || rc=$?
    fi
    if [[ $rc -eq 0 && ${#SETUP_CMD[@]} -gt 0 ]]; then
        suite setup "${SETUP_CMD[@]}" || rc=$?
    fi
    [[ $rc -eq 0 ]] || { printf '%ssetup: %s failed on %s (exit %d); the suite did not run%s\n' "$C_FAIL" "$REPO" "$ENV" "$rc" "$C_OFF" >&2; exit 3; }
}

chk_ok()   { printf '  %sok%s    %s%-11s%s %s\n' "$C_OK" "$C_OFF" "$C_NAME" "$1" "$C_OFF" "$2"; }
chk_fail() { printf '  %sFAIL%s  %s%-11s%s %s%s%s\n' "$C_FAIL" "$C_OFF" "$C_NAME" "$1" "$C_OFF" "$C_FAIL" "$2" "$C_OFF"; PREREQ_FAIL+=("$1"); }
chk_note() { printf '  %snote%s  %s%-11s%s %s\n' "$C_WARN" "$C_OFF" "$C_NAME" "$1" "$C_OFF" "$2"; }
chk_tool() { # chk_tool <name> <what needs it> <version command...>: on PATH, with the version it prints
    local path ver
    path=$(command -v "$1") || { chk_fail "$1" "not installed; needed by $2"; return 0; }
    ver=$("${@:3}" 2>&1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1) || ver=
    chk_ok "$1" "$path${ver:+ $ver}"
}
check_prereqs() { # host tools, then the Docker runtime, then izmachine and each cloud's credentials; exit 1 on a failure
    local s v ctx endpoint engine stages prod src remotes r st t name why ref usable=() unusable=() clouds=() started=$SECONDS
    say "prereqs for $REPO: ${#IMAGES[@]} image(s), $PLATFORM${ENV:+, $ENV}"
    chk_ok bash "$BASH $BASH_VERSION"
    chk_tool git "image tags" git --version
    chk_tool python3 "every target" python3 --version
    if python3 -c 'import tomllib' 2>/dev/null || python3 -c 'import tomli' 2>/dev/null; then
        chk_ok toml "python3 tomllib reads .iz and .izlocal"
    else
        chk_fail toml "python3 3.11+ (tomllib) or the tomli module; reads .iz and .izlocal"
    fi
    chk_tool docker "build, smoke, run, test" docker --version
    if command -v docker >/dev/null && docker buildx version >/dev/null 2>&1; then
        chk_ok buildx "$(docker buildx version | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
    else
        chk_fail buildx "docker buildx missing; needed by build"
    fi
    [[ $KIND == tests ]] || chk_tool syft "sbom" syft --version
    if [[ $KIND != tests ]]; then
        chk_tool incus "image-load, deploy" incus --version
        chk_tool kubectl "running, deploy" kubectl version --client
        chk_tool helm "running, deploy" helm version --short
    fi
    for t in ${HOST_TOOLS[@]+"${HOST_TOOLS[@]}"}; do # "<tool>|<what needs it>"; python modules as "py:<module>|<why>"
        name=${t%%|*} why=${t#*|}
        if [[ $name == py:* ]]; then
            if python3 -c "import ${name#py:}" 2>/dev/null; then chk_ok "${name#py:}" "python3 module; $why"; else chk_fail "${name#py:}" "python3 module missing; needed by $why"; fi
        else
            chk_tool "$name" "$why" "$name" --version
        fi
    done
    for s in ${SECRETS[@]+"${SECRETS[@]}"}; do
        v="${s#*=}"
        if [[ -n "${!v:-}" ]]; then chk_ok secret "${s%%=*} from \$$v"; else chk_fail secret "${s%%=*} needs \$$v set; needed by build"; fi
    done
    if ctx=$(docker context show 2>/dev/null); then
        endpoint=$(docker context inspect "$ctx" --format '{{.Endpoints.docker.Host}}' 2>/dev/null || echo '?')
        src=${CONTEXT_FROM:-the current docker context}
        if ! engine=$(docker version --format '{{.Server.Os}}/{{.Server.Arch}}' 2>/dev/null); then
            chk_fail context "$ctx ($endpoint, from $src): engine not reachable; choose a build context with setup.sh, or DOCKER_CONTEXT=<name>"
        elif [[ $engine != linux/* ]]; then
            chk_fail context "$ctx ($endpoint, from $src): engine $engine; builds need a Linux engine"
        else
            chk_ok context "$ctx ($endpoint, from $src) engine $engine, builds $PLATFORM$([[ $engine == "$PLATFORM" ]] || echo ", emulated (slower)")"
            # The suite's own libraries live in its image; a built image is checked there, an unbuilt one builds on first use.
            IFS='|' read -r n t _ <<<"${IMAGES[0]}"; ref=$REGISTRY/$n:$t-$SUFFIX
            if [[ $KIND == tests && ${#SMOKE_CMD[@]} -gt 0 ]] && docker image inspect "$ref" >/dev/null 2>&1; then
                if docker run --rm --platform "$PLATFORM" "$ref" "${SMOKE_CMD[@]}" >/dev/null 2>&1; then chk_ok runtime "$ref: suite libraries import"
                else chk_fail runtime "$ref: SMOKE_CMD failed inside the image; make image rebuilds it"; fi
            fi
        fi
    else
        chk_fail context "no docker context; needed by build"
    fi
    chk_tool izmachine "clouds, kubeconfig, credentials" izmachine --version
    [[ $KIND != tests ]] || chk_tool curl "cloud API access check" curl --version
    if command -v izmachine >/dev/null && stages=$(stage_list 2>&1); then
        stages=$( { printf '%s\n' "$stages" | cut -f1; api_only_stages | cut -f1; } | awk 'NF' | tr '\n' ' '); prod=$(production_stages | tr '\n' ' ')
        if [[ -n $stages ]]; then
            chk_ok stages "${stages% }${prod:+ (production: ${prod% })}"
        else
            chk_fail stages "no [machine.<stage>] in .iz or .izlocal; needed by every stage target"
        fi
        if [[ $KIND == tests && $TEST_STAGE != no ]]; then
            if [[ -n $ENV ]]; then clouds=("$ENV"); else read -r -a clouds <<<"$stages"; fi
            while IFS= read -r st; do
                [[ $st == *FAIL* ]] && PREREQ_FAIL+=("${st#*FAIL*  }")
                printf '%s\n' "$st"
            done < <(NUCLOUD_CREDENTIALS="${CREDENTIALS[*]-}" NUCLOUD_ACCOUNTS="${ACCOUNTS[*]-}" NUCLOUD_CHECK_OK="$C_OK" NUCLOUD_CHECK_FAIL="$C_FAIL" NUCLOUD_CHECK_NAME="$C_NAME" NUCLOUD_CHECK_OFF="$C_OFF" \
                "${CLOUD[@]}" check "${clouds[@]}" 2>&1)
        fi
    elif command -v izmachine >/dev/null; then
        chk_fail stages "$stages"
    fi
    # each stage's incus remote must be registered here; a stage on a remote this machine lacks is noted, not failed
    if [[ -n $stages && $KIND != tests ]] && command -v incus >/dev/null; then
        remotes=" $(incus remote list --format csv 2>/dev/null | cut -d, -f1 | sed 's/ (current)//' | tr '\n' ' ') "
        while IFS=$'\t' read -r st _ r _; do
            [[ -n $r ]] || continue
            if [[ $remotes == *" $r "* ]]; then usable+=("$st on $r"); else unusable+=("$st (incus remote $r missing)"); fi
        done < <(stage_list)
        if [[ ${#usable[@]} -gt 0 ]]; then chk_ok remotes "$(printf '%s, ' "${usable[@]}" | sed 's/, $//')"
        else chk_fail remotes "no stage's incus remote is registered; incus remote add <name> <url>"; fi
        [[ ${#unusable[@]} -eq 0 ]] || chk_note remotes "$(printf '%s, ' "${unusable[@]}" | sed 's/, $//'); those stages are unusable here"
    fi
    if [[ ${#PREREQS_CMD[@]} -gt 0 ]]; then
        # A bash PREREQS_CMD calls chk_ok/chk_fail/chk_note/chk_tool and exits 1 on a failure; any other
        # language colors its lines from NUCLOUD_CHECK_* and exits 1 on a failure.
        export NUCLOUD_CHECK_OK="$C_OK" NUCLOUD_CHECK_FAIL="$C_FAIL" NUCLOUD_CHECK_NAME="$C_NAME" NUCLOUD_CHECK_OFF="$C_OFF" NUCLOUD_CHECK_WARN="$C_WARN"
        export C_OK C_FAIL C_WARN C_NAME C_OFF
        export -f chk_ok chk_fail chk_note chk_tool
        if ! "${PREREQS_CMD[@]}"; then chk_fail suite "repository prerequisites failed; see above"; fi
    fi
    if [[ ${#PREREQ_FAIL[@]} -gt 0 ]]; then
        printf '%s==> %d check(s) failed in %ds:%s %s\n' "$C_FAIL" "${#PREREQ_FAIL[@]}" "$((SECONDS - started))" "$C_OFF" "${PREREQ_FAIL[*]}" >&2
        exit 1
    fi
    printf '%s==> all checks passed in %ds:%s context %s, %d image(s)\n' "$C_OK" "$((SECONDS - started))" "$C_OFF" "$ctx" "${#IMAGES[@]}"
}

if [[ $KIND == tests ]]; then
    case "${1:-}" in
        image-load|deploy|deploy-only|upgrade|running|push) echo "error: $REPO is not an image repo: it runs a suite against a stage (make setup, make test)" >&2; exit 2 ;;
    esac
elif [[ ${1:-} == setup ]]; then
    echo "error: $REPO is an image repo: setup belongs to test repos (KIND=tests)" >&2; exit 2
fi
if [[ ${1:-} == running ]]; then  # nothing to show needs no stage
    REL_LIST=(); each i_rel
    [[ ${#REL_LIST[@]} -gt 0 ]] || { say "no k3s release in this repo"; exit 0; }
fi
case "${1:-}" in
    image-load|deploy-only|deploy|upgrade) need_stage change ;;
    stage-check|kubeconfig|running) need_stage ;;
esac
case "${1:-}" in
    images) each i_list ;;
    prereqs) check_prereqs ;;
    tags)
        if [[ -n ${TAGS:-}${EXCLUDE_TAGS:-}${MACHINE:-} ]]; then  # the cases a run with this selection takes
            if [[ -n ${MACHINE:-} ]] && "${CLOUD[@]}" read-only | grep -qxF "$MACHINE"; then export NUCLOUD_READ_ONLY=1; fi
            TEST_FRAMEWORK=$TEST_FRAMEWORK python3 ./nucloud-tags.py select
        else
            TEST_FRAMEWORK=$TEST_FRAMEWORK python3 ./nucloud-tags.py cases
        fi ;;
    tags-check) TEST_FRAMEWORK=$TEST_FRAMEWORK python3 ./nucloud-tags.py check ${UPDATE:+--update} ;;
    image) each i_build ;;
    sbom) each i_sbom ;;
    setup)
        if [[ ${#SETUP_CMD[@]} -gt 0 || ${#HOST_SETUP_CMD[@]} -gt 0 ]]; then run_setup; else say "no setup in nucloud.env"; fi ;;
    test)
        if [[ $KIND == tests ]]; then
            [[ ${#TEST_CMD[@]} -gt 0 || ${#HOST_TEST_CMD[@]} -gt 0 ]] || die "TEST_CMD missing from nucloud.env"
            [[ $TEST_STAGE == no ]] || run_setup  # the suite prepares its own fixtures before the cases
            if [[ ${#HOST_TEST_CMD[@]} -gt 0 ]]; then
                suite_env; export MACHINE=$ENV; "${HOST_TEST_CMD[@]}"
            elif [[ $TEST_STAGE == no ]]; then
                IFS='|' read -r n t _ <<<"${IMAGES[0]}"
                docker image inspect "$REGISTRY/$n:$t-$SUFFIX" >/dev/null 2>&1 || each i_build
                docker run --rm --platform "$PLATFORM" "$REGISTRY/$n:$t-$SUFFIX" "${TEST_CMD[@]}"
            else
                suite test "${TEST_CMD[@]}"
            fi
            exit 0
        fi
        IFS='|' read -r _ _ df _ <<<"${IMAGES[0]}"
        if grep -qiE '^FROM .* AS test( |$)' "$df"; then
            DOCKER_BUILDKIT=1 docker buildx build --platform "$PLATFORM" --target test \
                $([[ "$SSH" == 1 ]] && echo --ssh default) -f "$df" .
        else
            say "no test stage in $df"
        fi ;;
    smoke) each i_smoke ;;
    image-load) load_images ;;
    stage-check) stage_kubeconfig; say "$ENV answers at $(stage_vm)" ;;
    kubeconfig) stage_kubeconfig; cat "$STAGE_KC" ;;
    running) show_running ;;
    test-timings) show_timings ;;
    deploy-only) stage_kubeconfig; load_images; each i_deploy; deploy_apply ;;
    deploy) stage_kubeconfig; say "$ENV answers at $(stage_vm)"; each i_build; load_images; each i_deploy; deploy_apply ;;
    upgrade) stage_kubeconfig; each i_deploy; deploy_apply ;;  # internal: upgrade releases to images already in the VM
    push) each i_push ;;
    run) shift; IFS='|' read -r n t _ <<<"${IMAGES[0]}"; docker run --rm -it "$REGISTRY/$n:$t-$SUFFIX" "$@" ;;
    *) echo "error: unknown command ${1:-}; run make help" >&2; exit 2 ;;
esac
