#!/usr/bin/env bash
# Build, sign and publish a public release; never install or flash it.
set -euo pipefail

usage() {
    cat <<'HELP'
Usage: release-public.sh dev-N

Builds the existing EdgeMap Lite A/B output, refreshes EdgeMap sources, signs and
verifies the release, uploads it with rclone, verifies its public HTTPS bytes,
then publishes signed latest.json last. Never installs on a device.

Environment:
  RELEASE_WORKSPACE    Absolute workspace (default: inferred from script)
  RELEASE_OUTPUT       Absolute output (default: WORKSPACE/output-edgemap-ab)
  AB_SIGN_KEY          Absolute private PEM (default: WORKSPACE/ab-development-private.pem)
  AB_VERIFY_KEY        Absolute public PEM (default: WORKSPACE/ab-development-public.pem)
  RELEASE_BASE_URL     Default: https://resilience-theatre.eu/rpi4edgemap
  RELEASE_REMOTE       Required: your existing rclone remote and web directory
  RELEASE_DIR          Absolute artifact root (default: WORKSPACE/edgemap-releases)
  RELEASE_JOBS         Default: 4
  RELEASE_NOTES        Default: Release dev-N
  RELEASE_EXPIRES_DAYS Default: 7

Credentials are read by rclone from its existing configuration, never copied.
Only the SWU, versioned checksum and signed latest.json are uploaded.
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
output=${RELEASE_OUTPUT:-$workspace/output-edgemap-ab}
remote=${RELEASE_REMOTE:?set RELEASE_REMOTE to your configured rclone remote and web directory}
private=${AB_SIGN_KEY:-$workspace/ab-development-private.pem}
public=${AB_VERIFY_KEY:-$workspace/ab-development-public.pem}
base=${RELEASE_BASE_URL:-https://resilience-theatre.eu/rpi4edgemap}
base=${base%/}
remote=${remote%/}
release_root=${RELEASE_DIR:-$workspace/edgemap-releases}
jobs=${RELEASE_JOBS:-4}
days=${RELEASE_EXPIRES_DAYS:-7}
notes=${RELEASE_NOTES:-Release $version}
fail() { echo "release: $*" >&2; exit 1; }
[[ $base == https://* ]] || fail "RELEASE_BASE_URL must use HTTPS"
for path in "$workspace" "$output" "$private" "$public" "$release_root"; do
    [[ $path == /* ]] || fail "Use absolute paths: $path"
done
[[ $jobs =~ ^[1-9][0-9]*$ && $days =~ ^[1-9][0-9]*$ ]] || fail 'Jobs and expiry must be positive integers'
for command in make python3 openssl sha256sum flock rclone; do command -v "$command" >/dev/null || fail "Missing command: $command"; done
[[ -d $workspace/buildroot && -f $output/.config ]] || fail 'Existing configured A/B output required'
[[ $(realpath "$workspace/rpi-extree/board/edgemap-ab") == "$board" ]] || fail 'Workspace and updater source disagree'
[[ -f $output/images/boot-a.vfat && -f $output/images/boot-b.vfat && -f $output/images/rootfs.ext4 ]] || fail 'Build and inspect the factory artifacts first'
[[ -r $private && -r $public ]] || fail 'Signing and verification keys required'
grep -qx 'BR2_PACKAGE_SITUATION_MAP=y' "$output/.config" || fail 'Situation map package is not enabled'
grep -q 'edgemap-ab/post-build.sh' "$output/.config" || fail 'Output is not configured for EdgeMap Lite A/B'
exec 9>"$workspace/.edgemap-release.lock"
flock -n 9 || fail 'Another release script is running'
release=$release_root/$version
[[ ! -e $release ]] || fail 'Release already exists; use a new version (inspect partial artifacts after failures)'
scratch=$(mktemp -d "$workspace/.edgemap-public-XXXXXXXX")
trap 'rm -rf -- "$scratch"' EXIT
python3 "$board/api/public_release.py" preflight --remote "$remote" --base "$base" \
    --version "$version" --sequence "$sequence" --public-key "$public" \
    --snapshot "$scratch/previous.json"
openssl pkey -in "$private" -pubout -outform DER -out "$scratch/sign.der"
openssl pkey -pubin -in "$public" -outform DER -out "$scratch/verify.der"
cmp -s "$scratch/sign.der" "$scratch/verify.der" || fail 'Signing key does not match AB_VERIFY_KEY'
# Prevent accidentally changing the trust domain of an existing factory output.
installed_public="$output/target/etc/edgemap-ab/public.pem"
[[ -r $installed_public ]] || fail 'Existing factory verification key is missing'
openssl pkey -pubin -in "$installed_public" -outform DER -out "$scratch/factory.der"
cmp -s "$scratch/factory.der" "$scratch/verify.der" || fail 'Verification key differs from existing factory output'


# A local package is not automatically recopied when its source changes.
make -C "$workspace/buildroot" O="$output" situation-map-dirclean
AB_RELEASE_VERSION="$version" AB_VERIFY_KEY="$public" \
    make -C "$workspace/buildroot" O="$output" -j"$jobs"
mkdir -p -- "$release"
python3 "$board/package.py" --images "$output/images" --version "$version" \
    --key "$private" --output "$release/$version.swu"
(cd -- "$release" && sha256sum "$version.swu" > SHA256SUMS)
python3 "$board/api/publish.py" --bundle "$release/$version.swu" --key "$private" \
    --url "${base%/}/$version.swu" --sequence "$sequence" --expires-in-days "$days" \
    --notes "$notes" --output "$release/latest.json"
python3 "$board/api/public_release.py" upload --remote "$remote" --base "$base" \
    --version "$version" --sequence "$sequence" --public-key "$public" \
    --snapshot "$scratch/previous.json" --release "$release"
printf 'Published %s at %s/%s.swu\nBundle: %s/%s.swu\n' \
    "$version" "$base" "$version" "$release" "$version"
