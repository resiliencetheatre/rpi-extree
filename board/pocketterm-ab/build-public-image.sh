#!/usr/bin/env bash
# Build a downloadable factory image. Never upload, sign releases or flash media.
set -euo pipefail
usage() {
cat <<'HELP'
Usage: build-public-image.sh dev-N

Builds raspberrypi4_pocketterm_public_defconfig in a separate output directory,
refreshes local LVGL, and archives a compressed factory disk image with SHA256SUMS.
No SWU publication, remote upload, EEPROM update or flashing is performed.

Absolute paths:
  RELEASE_WORKSPACE Workspace containing buildroot/rpi-extree/lvgl-console
  PUBLIC_OUTPUT     Default: WORKSPACE/output-pocketterm-public
  PUBLIC_IMAGES     Default: WORKSPACE/pocketterm-factory-images
  AB_VERIFY_KEY     Default: WORKSPACE/ab-development-public.pem
  RELEASE_JOBS      Default: 4

Use the verification key trusted for your public SWU channel. Only the public key
is embedded. Existing output configuration is preserved and checked, not reset.
Never run a manual build concurrently in the selected output directory.
HELP
}
if [[ ${1:-} == --help || ${1:-} == -h ]]; then usage; exit 0; fi
[[ $# == 1 && $1 =~ ^dev-[1-9][0-9]{0,8}$ ]] || { usage >&2; exit 2; }
version=$1
board=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
workspace=${RELEASE_WORKSPACE:-$(cd -- "$board/../../.." && pwd)}
output=${PUBLIC_OUTPUT:-$workspace/output-pocketterm-public}
archive=${PUBLIC_IMAGES:-$workspace/pocketterm-factory-images}
public=${AB_VERIFY_KEY:-$workspace/ab-development-public.pem}
jobs=${RELEASE_JOBS:-4}
fail() { echo "public-image: $*" >&2; exit 1; }
for path in "$workspace" "$output" "$archive" "$public"; do
    [[ $path == /* ]] || fail "Use absolute paths: $path"
done
[[ $jobs =~ ^[1-9][0-9]*$ ]] || fail 'Jobs must be a positive integer'
for command in make python3 openssl sha256sum flock xz git; do
    command -v "$command" >/dev/null || fail "Missing command: $command"
done
[[ -d $workspace/buildroot && -f $workspace/rpi-extree/external.desc && -d $workspace/lvgl-console ]] || fail 'Workspace is incomplete'
python3 - "$workspace" "$output" "$archive" "$public" <<'PY'
from pathlib import Path
import sys
workspace, output, archive, key = map(lambda s: Path(s).resolve(), sys.argv[1:])
for path in (output, archive, key):
    if path.is_relative_to(workspace/'rpi-extree'):
        sys.exit('Outputs, archives and external keys must be outside rpi-extree')
if output == workspace/'output-pocketterm-ab':
    sys.exit('Use a separate public factory output, not the development output')
if archive == output or archive.is_relative_to(output) or output.is_relative_to(archive):
    sys.exit('Archive and build output must be separate directories')
PY
openssl rsa -pubin -in "$public" -noout >/dev/null
exec 9>"$workspace/.pocketterm-release.lock"
flock -n 9 || fail 'Another PocketTerm release/image wrapper is running'
release=$archive/$version
[[ ! -e $release ]] || fail 'Factory release directory already exists; inspect partial artifacts and use a new version'
if [[ ! -e $output ]]; then
    make -C "$workspace/buildroot" O="$output" BR2_EXTERNAL="$workspace/rpi-extree" raspberrypi4_pocketterm_public_defconfig
elif [[ ! -f $output/.config ]]; then
    fail 'Existing output lacks .config; use a fresh directory'
fi
grep -q 'board/pocketterm-ab/public-overlay' "$output/.config" || fail 'Output is not the public factory profile'
grep -q 'board/pocketterm-ab/post-build.sh' "$output/.config" || fail 'Output lacks PocketTerm A/B integration'
grep -qx 'BR2_PACKAGE_LVGL_CONSOLE_LOCAL=y' "$output/.config" || fail 'Local LVGL package is not enabled'
make -C "$workspace/buildroot" O="$output" lvgl-console-local-dirclean
AB_RELEASE_VERSION="$version" AB_VERIFY_KEY="$public" \
    make -C "$workspace/buildroot" O="$output" -j"$jobs"
# Check generated defaults and trust before archiving the factory artifact.
python3 - "$output" "$version" <<'PY'
import json
from pathlib import Path
import sys
output=Path(sys.argv[1]); images=output/'images'; target=output/'target'
assert (images/'release-version').read_text().strip() == sys.argv[2]
assert (images/'release-profile').read_text().strip() == 'pocketterm-rpi4-lvgl-v1'
config=json.loads((target/'etc/default/pocketterm-updates.json').read_text())
assert config['manifest_url'] == 'https://resilience-theatre.eu/pocketterm/latest.json'
assert config['public_key'] == '/etc/pocketterm-ab/public.pem'
assert 'ca_file' not in config and config['allow_http_loopback'] is False
assert 'UDPPTT_SERVER=91.98.237.100' in (target/'etc/default/udpptt').read_text().splitlines()
assert (images/'sdcard-ab.img').stat().st_size > 0
PY
mkdir -p -- "$release"
name=pocketterm-public-$version.img.xz
xz -T"$jobs" -c -- "$output/images/sdcard-ab.img" > "$release/$name.partial"
mv -- "$release/$name.partial" "$release/$name"
(cd -- "$release" && sha256sum "$name" > SHA256SUMS)
cp -- "$output/.config" "$release/buildroot.config"
for repo in buildroot rpi-extree lvgl-console; do
    git -C "$workspace/$repo" rev-parse HEAD > "$release/$repo.revision"
    git -C "$workspace/$repo" status --short > "$release/$repo.status"
done
printf 'Factory image: %s/%s\nChecksums: %s/SHA256SUMS\n' "$release" "$name" "$release"
