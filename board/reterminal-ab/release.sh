#!/usr/bin/env bash
# Build, sign and publish a development release; never install or flash it.
set -euo pipefail

usage() {
    cat <<'HELP'
Usage: release.sh dev-N

Builds the existing A/B configuration, refreshes local LVGL sources, signs the
bundle, and publishes it to the existing HTTPS document root. Does not start the
server, change firewall rules, install on a device, or regenerate configuration.

Optional environment variables (paths must be absolute):
  RELEASE_WORKSPACE   Workspace containing buildroot, rpi-extree and lvgl-console
  RELEASE_OUTPUT      Buildroot output (default: WORKSPACE/output-reterminal-ab)
  RELEASE_HOST        HTTPS host directory (default: WORKSPACE/update-host)
  AB_SIGN_KEY         Signing key (default: WORKSPACE/ab-development-private.pem)
  AB_VERIFY_KEY       Verification key (default: WORKSPACE/ab-development-public.pem)
  RELEASE_BASE_URL    Default: https://192.168.178.41:9443
  RELEASE_JOBS        Default: 4
  RELEASE_NOTES       Default: Release dev-N
  RELEASE_EXPIRES_DAYS Default: 7

N is also the metadata sequence and must exceed the currently published sequence.
Existing release directories and published bundle names are never overwritten.
HELP
}
if [[ ${1:-} == --help || ${1:-} == -h ]]; then usage; exit 0; fi
[[ $# == 1 && $1 =~ ^dev-([1-9][0-9]{0,8})$ ]] || { usage >&2; exit 2; }
version=$1
sequence=${BASH_REMATCH[1]}
board=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
workspace=${RELEASE_WORKSPACE:-$(cd -- "$board/../../.." && pwd)}
output=${RELEASE_OUTPUT:-$workspace/output-reterminal-ab}
host=${RELEASE_HOST:-$workspace/update-host}
private=${AB_SIGN_KEY:-$workspace/ab-development-private.pem}
public=${AB_VERIFY_KEY:-$workspace/ab-development-public.pem}
base=${RELEASE_BASE_URL:-https://192.168.178.41:9443}
jobs=${RELEASE_JOBS:-4}
days=${RELEASE_EXPIRES_DAYS:-7}
notes=${RELEASE_NOTES:-Release $version}
fail() { echo "release: $*" >&2; exit 1; }
for path in "$workspace" "$output" "$host" "$private" "$public"; do
    [[ $path == /* ]] || fail "Use absolute paths: $path"
done
[[ $jobs =~ ^[1-9][0-9]*$ && $days =~ ^[1-9][0-9]*$ ]] || fail 'Jobs and expiry must be positive integers'
for command in make python3 openssl sha256sum flock; do command -v "$command" >/dev/null || fail "Missing command: $command"; done
[[ -d $workspace/buildroot && -f $output/.config && -d $host/www ]] || fail 'Existing configured A/B output and initialized HTTPS host required'
[[ -r $private && -r $public ]] || fail 'Signing and verification keys required'
grep -qx 'BR2_PACKAGE_LVGL_CONSOLE_LOCAL=y' "$output/.config" || fail 'Local LVGL package is not enabled'
grep -q 'reterminal-ab/post-build.sh' "$output/.config" || fail 'Output is not configured for reTerminal A/B'
exec 9>"$workspace/.reterminal-release.lock"
flock -n 9 || fail 'Another release script is running'
release=$workspace/releases/$version
published=$host/www/$version.swu
[[ ! -e $release && ! -e $published ]] || fail 'Release already exists; use a new version (inspect partial artifacts after failures)'
python3 - "$host/www/latest.json" "$sequence" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
if path.exists():
    previous = json.loads(path.read_text())['signed']['sequence']
    if int(sys.argv[2]) <= previous:
        sys.exit(f'Release sequence must exceed published sequence {previous}')
PY
scratch=$(mktemp -d "$host/www/.release-XXXXXXXX")
trap 'rm -rf -- "$scratch"' EXIT
openssl pkey -in "$private" -pubout -outform DER -out "$scratch/sign.der"
openssl pkey -pubin -in "$public" -outform DER -out "$scratch/verify.der"
cmp -s "$scratch/sign.der" "$scratch/verify.der" || fail 'Signing key does not match AB_VERIFY_KEY'

# A local package is not automatically recopied when its source changes.
make -C "$workspace/buildroot" O="$output" lvgl-console-local-dirclean
AB_RELEASE_VERSION="$version" AB_VERIFY_KEY="$public" \
    make -C "$workspace/buildroot" O="$output" -j"$jobs"
mkdir -p -- "$release"
python3 "$board/package.py" --images "$output/images" --version "$version" \
    --key "$private" --output "$release/$version.swu"
(cd -- "$release" && sha256sum "$version.swu" > SHA256SUMS)
cp --reflink=auto -- "$release/$version.swu" "$scratch/$version.swu"
python3 "$board/api/publish.py" --bundle "$scratch/$version.swu" --key "$private" \
    --url "${base%/}/$version.swu" --sequence "$sequence" --expires-in-days "$days" \
    --notes "$notes" --output "$scratch/latest.json"
# Publish complete immutable payload first, then atomically replace the offer.
mv -- "$scratch/$version.swu" "$published"
mv -- "$scratch/latest.json" "$host/www/latest.json"
printf 'Published %s at %s/%s.swu\nBundle: %s/%s.swu\nUse Check for updates on reTerminal. Keep the HTTPS host running.\n' \
    "$version" "${base%/}" "$version" "$release" "$version"
