#!/usr/bin/env bash
# Source into Bash. This file only exports settings and prints commands.
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
    printf 'Source this script so exports remain in your shell:\n  source %q LOCAL_IPV4 BUILD_DIRECTORY\n' "$0"
    [[ ${1:-} == --help || ${1:-} == -h ]] && exit 0
    exit 2
fi

_pocketterm_set_build_variables() {
    if [[ ${1:-} == --help || ${1:-} == -h ]]; then
        cat <<'HELP'
Usage: source ./set-build-variables.sh LOCAL_IPV4 BUILD_DIRECTORY
Example: source ./set-build-variables.sh 192.0.2.10 output-pocketterm-ab-fresh-02
Relative build directories resolve against the workspace, not the current directory.
Existing outputs are selected unchanged; nonexistent outputs are not created.
Optional overrides before sourcing: AB_SIGN_KEY, AB_VERIFY_KEY, RELEASE_HOST,
RELEASE_LOCAL_CA, RELEASE_LOCAL_PORT, RELEASE_PUBLIC_URL, RELEASE_REMOTE,
RELEASE_DIR, RELEASE_JOBS (default 32), RELEASE_NOTES, RELEASE_EXPIRES_DAYS.
Key/host/artifact paths must be absolute. Version is specified per build/release.
Nothing is built, cleaned, initialized, started, signed or published by this script.
HELP
        return 0
    fi
    if [[ $# != 2 ]]; then
        printf 'Usage: source ./set-build-variables.sh LOCAL_IPV4 BUILD_DIRECTORY\n' >&2
        return 1
    fi
    local ip=$1 output=$2 workspace script part path name jobs port days
    if [[ ! $ip =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        printf 'Invalid local IPv4 address: %s\n' "$ip" >&2; return 1
    fi
    local -a octets
    IFS=. read -r -a octets <<< "$ip"
    for part in "${octets[@]}"; do
        if [[ ( ${#part} -gt 1 && $part == 0* ) ]] || (( 10#$part > 255 )); then
            printf 'Invalid local IPv4 address: %s\n' "$ip" >&2; return 1
        fi
    done
    script=$(realpath -- "${BASH_SOURCE[0]}") || return 1
    workspace=$(cd -- "$(dirname -- "$script")/../../.." && pwd -P) || return 1
    if [[ ! -f $workspace/buildroot/Makefile || ! -f $workspace/rpi-extree/external.desc ||
          ! -f $workspace/rpi-extree/configs/raspberrypi4_pocketterm_ab_defconfig ]]; then
        printf 'Cannot identify the workspace from this script: %s\n' "$script" >&2; return 1
    fi
    [[ -n $output ]] || { printf 'Build directory cannot be empty\n' >&2; return 1; }
    [[ $output == /* ]] || output=$workspace/$output
    output=$(realpath -m -- "$output") || return 1
    if [[ $output == / || $output == "$workspace" || $workspace == "$output/"* ||
          $output == "$workspace/buildroot" || $output == "$workspace/buildroot/"* ||
          $output == "$workspace/lvgl-console" || $output == "$workspace/lvgl-console/"* || $output == "$workspace/rpi-extree" ||
          $output == "$workspace/rpi-extree/"* || ( -e $output && ! -d $output ) ]]; then
        printf 'Choose a separate build output directory: %s\n' "$output" >&2; return 1
    fi
    jobs=${RELEASE_JOBS:-32}
    port=${RELEASE_LOCAL_PORT:-9443}
    days=${RELEASE_EXPIRES_DAYS:-7}
    if [[ ! $jobs =~ ^[1-9][0-9]{0,4}$ || ! $days =~ ^[1-9][0-9]{0,4}$ ||
          ! $port =~ ^[1-9][0-9]{0,4}$ ]] || (( port < 1024 || port > 65535 )); then
        printf 'Use positive job/expiry counts and a local port between 1024 and 65535\n' >&2; return 1
    fi
    local sign=${AB_SIGN_KEY:-$workspace/ab-development-private.pem}
    local verify=${AB_VERIFY_KEY:-$workspace/ab-development-public.pem}
    local host=${RELEASE_HOST:-$workspace/pocketterm-update-host}
    local ca=${RELEASE_LOCAL_CA:-$host/tls/ca.pem}
    local releases=${RELEASE_DIR:-$workspace/pocketterm-releases}
    local public_url=${RELEASE_PUBLIC_URL:-https://resilience-theatre.eu/pocketterm}
    local remote=${RELEASE_REMOTE:-}
    for path in "$sign" "$verify" "$host" "$ca" "$releases"; do
        [[ $path == /* ]] || { printf 'Use absolute key/host/artifact paths: %s\n' "$path" >&2; return 1; }
    done
    [[ $public_url == https://* ]] || { printf 'RELEASE_PUBLIC_URL must use HTTPS\n' >&2; return 1; }
    export WORKSPACE="$workspace" BR2_EXTERNAL="$workspace/rpi-extree"
    export AB_OUTPUT="$output" RELEASE_OUTPUT="$output" RELEASE_WORKSPACE="$workspace"
    export AB_PROFILE="$workspace/rpi-extree/configs/raspberrypi4_pocketterm_ab_defconfig"
    export AB_SIGN_KEY="$sign" AB_VERIFY_KEY="$verify"
    export LOCAL_ADDRESS="$ip" RELEASE_LOCAL_PORT="$port"
    export RELEASE_HOST="$host" RELEASE_LOCAL_URL="https://$ip:$port" RELEASE_LOCAL_CA="$ca"
    export RELEASE_PUBLIC_URL="${public_url%/}" RELEASE_REMOTE="${remote%/}" RELEASE_DIR="$releases"
    export RELEASE_JOBS="$jobs" RELEASE_EXPIRES_DAYS="$days"
    export RELEASE_NOTES="${RELEASE_NOTES:-Describe changes in the next release}"
    printf 'Build/release environment (key paths only; no key contents):\n'
    for name in WORKSPACE BR2_EXTERNAL AB_OUTPUT AB_PROFILE AB_VERIFY_KEY AB_SIGN_KEY \
                RELEASE_WORKSPACE RELEASE_OUTPUT RELEASE_DIR LOCAL_ADDRESS RELEASE_LOCAL_PORT \
                RELEASE_HOST RELEASE_LOCAL_URL RELEASE_LOCAL_CA RELEASE_PUBLIC_URL RELEASE_REMOTE \
                RELEASE_JOBS RELEASE_EXPIRES_DAYS RELEASE_NOTES; do
        printf '  %s=%q\n' "$name" "${!name}"
    done
    if [[ -f $output/.config ]]; then
        printf '\nSelected existing configuration; no settings changed.\n'
    else
        printf '\nNo .config in this output: configure it, then build initial artifacts before release.\n'
    fi
    [[ -r $sign && -r $verify ]] || printf 'Note: selected signing/verification key files are not both readable yet.\n'
    [[ -r $ca ]] || printf 'Note: local CA is not present yet; initialize the HTTPS host once before publishing.\n'
    cat <<'HELP'

Command reference — run from: cd "$WORKSPACE"
Replace dev-N with the next unused version, e.g. dev-11. Commands below are NOT run.

Configure NEW output only (do not reload over intentional menuconfig edits):
  make -C buildroot O="$AB_OUTPUT" BR2_EXTERNAL="$BR2_EXTERNAL" raspberrypi4_pocketterm_ab_defconfig

Menuconfig / save reviewed profile:
  make -C buildroot O="$AB_OUTPUT" menuconfig
  make -C buildroot O="$AB_OUTPUT" savedefconfig BR2_DEFCONFIG="$AB_PROFILE"

Refresh another changed package / kernel source before a full build:
  make -C buildroot O="$AB_OUTPUT" PACKAGE-dirclean
  make -C buildroot O="$AB_OUTPUT" linux-dirclean

Initial image build (required once for a fresh output):
  AB_RELEASE_VERSION=dev-N make -C buildroot O="$AB_OUTPUT" -j"$RELEASE_JOBS"

Incremental release — rebuilds, signs and publishes; no separate make needed:
  export RELEASE_NOTES="Describe this release"
  rpi-extree/board/pocketterm-ab/release.sh --local dev-N
  rpi-extree/board/pocketterm-ab/release.sh --public dev-N
  rpi-extree/board/pocketterm-ab/release.sh --public --local dev-N
Choose one destination command; --public is the remote rclone path.

Start/restart an ALREADY initialized local server in another terminal:
  python3 rpi-extree/board/pocketterm-ab/api/https_host.py serve --directory "$RELEASE_HOST"

Initialize local TLS ONCE, only for a fresh host directory:
  python3 rpi-extree/board/pocketterm-ab/api/https_host.py init --directory "$RELEASE_HOST" --address "$LOCAL_ADDRESS" --port "$RELEASE_LOCAL_PORT"
  curl --cacert "$RELEASE_LOCAL_CA" "$RELEASE_LOCAL_URL/health.json"

Clean ALL build artifacts/toolchain in the selected output, if deliberately needed:
  cp "$AB_OUTPUT/.config" "$AB_OUTPUT/.config.backup-$(date +%Y%m%d-%H%M%S)"
  make -C buildroot O="$AB_OUTPUT" clean

Prefer a fresh unused output after disabling packages, deleting/switching overlays,
or toolchain/ABI changes. Save the profile before configuring that new output.

Stop other builds first. Manual make commands do not share the release lock.
Changing the IP/port here does not change existing host.json or its TLS certificate.

On the Pi: update.sh --local (or --remote), then update.sh --status after both reboots.

More detail: rpi-extree/board/pocketterm-ab/CHEATSHEET.md
HELP
}

if _pocketterm_set_build_variables "$@"; then
    unset -f _pocketterm_set_build_variables
    return 0
else
    unset -f _pocketterm_set_build_variables
    return 1
fi
