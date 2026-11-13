#!/usr/bin/env bash
# Build, sign and publish a public release; never install or flash it.
set -euo pipefail

usage() {
    cat <<'HELP'
Usage: release.sh [--public] [--local] [--publish-only] dev-N

Build/sign/verify once, publish to either or both channels. No flags builds a
bundle only. --publish-only reuses an existing verified bundle without a build.
Never installs, starts a server, changes firewall rules or initializes trust.

Common environment (paths must be absolute):
  RELEASE_WORKSPACE    Default: inferred workspace
  RELEASE_OUTPUT       Default: WORKSPACE/output-edgemap-ab (set your actual output)
  RELEASE_DIR          Default: WORKSPACE/edgemap-releases
  AB_SIGN_KEY          Default: WORKSPACE/ab-development-private.pem
  AB_VERIFY_KEY        Default: WORKSPACE/ab-development-public.pem
  RELEASE_JOBS         Default: 4
  RELEASE_NOTES        Default: Release dev-N
  RELEASE_EXPIRES_DAYS Default: 7
Public channel:
  RELEASE_REMOTE       Required: existing rclone remote and web directory
  RELEASE_PUBLIC_URL   Default: RELEASE_BASE_URL or https://resilience-theatre.eu/rpi4edgemap
Local channel:
  RELEASE_HOST         Required: absolute initialized Python HTTPS host directory
  RELEASE_LOCAL_URL    Required: https://LAN_IP:PORT (no trailing path)
  RELEASE_LOCAL_CA     Default: RELEASE_HOST/tls/ca.pem

N is the sequence and must exceed each selected channel's current sequence.
Each channel gets signed metadata binding its own URL to the same signed SWU.
Manual make commands do not share the wrapper lock. Inspect partial publications
before retrying. --publish-only can add an existing bundle to the other channel.
HELP
}
public_mode=no
local_mode=no
publish_only=no
version=''
while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h) usage; exit 0;;
        --public) public_mode=yes;;
        --local) local_mode=yes;;
        --publish-only) publish_only=yes;;
        dev-*) [[ -z $version ]] || { usage >&2; exit 2; }; version=$1;;
        *) usage >&2; exit 2;;
    esac
    shift
done
[[ $version =~ ^dev-([1-9][0-9]{0,8})$ ]] || { usage >&2; exit 2; }
sequence=${BASH_REMATCH[1]}
board=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
workspace=${RELEASE_WORKSPACE:-$(cd -- "$board/../../.." && pwd)}
output=${RELEASE_OUTPUT:-$workspace/output-edgemap-ab}
remote=${RELEASE_REMOTE:-}
private=${AB_SIGN_KEY:-$workspace/ab-development-private.pem}
public=${AB_VERIFY_KEY:-$workspace/ab-development-public.pem}
base=${RELEASE_PUBLIC_URL:-${RELEASE_BASE_URL:-https://resilience-theatre.eu/rpi4edgemap}}
host=${RELEASE_HOST:-}
local_base=${RELEASE_LOCAL_URL:-}
local_base=${local_base%/}
local_ca=${RELEASE_LOCAL_CA:-$host/tls/ca.pem}
base=${base%/}
remote=${remote%/}
release_root=${RELEASE_DIR:-$workspace/edgemap-releases}
jobs=${RELEASE_JOBS:-4}
days=${RELEASE_EXPIRES_DAYS:-7}
notes=${RELEASE_NOTES:-Release $version}
fail() { echo "release: $*" >&2; exit 1; }
if [[ $public_mode == yes ]]; then
    [[ $base == https://* ]] || fail "RELEASE_PUBLIC_URL must use HTTPS"
fi
for path in "$workspace" "$output" "$private" "$public" "$release_root"; do
    [[ $path == /* ]] || fail "Use absolute paths: $path"
done
[[ $jobs =~ ^[1-9][0-9]*$ && $days =~ ^[1-9][0-9]*$ ]] || fail 'Jobs and expiry must be positive integers'
for command in make python3 openssl sha256sum flock; do command -v "$command" >/dev/null || fail "Missing command: $command"; done
[[ -d $workspace/buildroot && -f $output/.config ]] || fail 'Existing configured A/B output required'
[[ $(realpath "$workspace/rpi-extree/board/edgemap-ab") == "$board" ]] || fail 'Workspace and updater source disagree'
[[ -f $output/images/boot-a.vfat && -f $output/images/boot-b.vfat && -f $output/images/rootfs.ext4 ]] || fail 'Build and inspect the factory artifacts first'
[[ -r $private && -r $public ]] || fail 'Signing and verification keys required'
grep -qx 'BR2_PACKAGE_SITUATION_MAP=y' "$output/.config" || fail 'Situation map package is not enabled'
grep -q 'edgemap-ab/post-build.sh' "$output/.config" || fail 'Output is not configured for EdgeMap Lite A/B'
exec 9>"$workspace/.edgemap-release.lock"
flock -n 9 || fail 'Another release script is running'
release=$release_root/$version
if [[ $publish_only == yes ]]; then
    [[ $public_mode == yes || $local_mode == yes ]] || fail '--publish-only requires a destination'
    [[ -f $release/$version.swu && -f $release/SHA256SUMS ]] || fail 'Existing signed bundle and checksum required'
else
    [[ ! -e $release ]] || fail 'Release already exists; inspect it or use --publish-only to add a channel'
fi
scratch=$(mktemp -d "$workspace/.edgemap-release-XXXXXXXX")
trap 'rm -rf -- "$scratch"' EXIT
channels=()
if [[ $public_mode == yes ]]; then
    [[ -n $remote ]] || fail 'Set RELEASE_REMOTE'
    command -v rclone >/dev/null || fail 'Missing rclone'
    channels+=(public)
fi
if [[ $local_mode == yes ]]; then
    [[ $host == /* && $local_ca == /* && $local_base == https://* ]] || fail 'Set absolute RELEASE_HOST/RELEASE_LOCAL_CA and HTTPS RELEASE_LOCAL_URL'
    [[ -r $local_ca && -d $host/www ]] || fail 'Initialize the local host separately and keep it running'
    channels+=(local)
fi
# Preflight every selected destination before building or publishing any payload.
for channel in "${channels[@]}"; do
    if [[ $channel == public ]]; then
        destination=(--remote "$remote" --base "$base")
    else
        destination=(--local-host "$host" --base "$local_base" --ca-file "$local_ca")
    fi
    printf '[release] Preflight %s publication\n' "$channel"
    python3 "$board/api/public_release.py" preflight "${destination[@]}" \
        --version "$version" --sequence "$sequence" --public-key "$public" \
        --snapshot "$scratch/$channel.previous.json"
done
openssl pkey -in "$private" -pubout -outform DER -out "$scratch/sign.der"
openssl pkey -pubin -in "$public" -outform DER -out "$scratch/verify.der"
cmp -s "$scratch/sign.der" "$scratch/verify.der" || fail 'Signing key does not match AB_VERIFY_KEY'
# Prevent accidentally changing the trust domain of an existing factory output.
installed_public="$output/target/etc/edgemap-ab/public.pem"
[[ -r $installed_public ]] || fail 'Existing factory verification key is missing'
openssl pkey -pubin -in "$installed_public" -outform DER -out "$scratch/factory.der"
cmp -s "$scratch/factory.der" "$scratch/verify.der" || fail 'Verification key differs from existing factory output'


if [[ $publish_only != yes ]]; then
    # A local package is not automatically recopied when its source changes.
    make -C "$workspace/buildroot" O="$output" situation-map-dirclean
    AB_RELEASE_VERSION="$version" AB_VERIFY_KEY="$public" \
        make -C "$workspace/buildroot" O="$output" -j"$jobs"
    mkdir -p -- "$release"
    python3 "$board/package.py" --images "$output/images" --version "$version" \
        --key "$private" --output "$release/$version.swu"
    (cd -- "$release" && sha256sum "$version.swu" > SHA256SUMS)
fi
PYTHONPATH="$board" python3 -c 'import sys; from pathlib import Path; from remote_release import verify_bundle; verify_bundle(Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]))' "$release/$version.swu" "$version" "$public"
printf '[release] Verified bundle: %s/%s.swu\n' "$release" "$version"
for channel in "${channels[@]}"; do
    if [[ $channel == public ]]; then
        destination=(--remote "$remote" --base "$base")
        channel_base=$base
    else
        destination=(--local-host "$host" --base "$local_base" --ca-file "$local_ca")
        channel_base=$local_base
    fi
    metadata="$release/$channel"
    mkdir -- "$metadata"
    ln -s "../$version.swu" "$metadata/$version.swu"
    ln -s ../SHA256SUMS "$metadata/SHA256SUMS"
    python3 "$board/api/publish.py" --bundle "$release/$version.swu" --key "$private" \
        --url "$channel_base/$version.swu" --sequence "$sequence" --expires-in-days "$days" \
        --notes "$notes" --output "$metadata/latest.json"
    printf '[release] Starting %s publication to %s\n' "$channel" "$channel_base"
    python3 "$board/api/public_release.py" upload "${destination[@]}" \
        --version "$version" --sequence "$sequence" --public-key "$public" \
        --snapshot "$scratch/$channel.previous.json" --release "$metadata"
    printf '[release] Published %s: %s/%s.swu\n' "$channel" "$channel_base" "$version"
done
