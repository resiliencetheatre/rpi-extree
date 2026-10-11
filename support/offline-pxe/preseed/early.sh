#!/bin/sh
set -eu
# apt-setup 0.198 supports per-local-source options before its first apt update.
# Full version and source checks also run during host verification.
. /usr/share/debconf/confmodule
if [ "${OFFLINE_UNATTENDED:-0}" != 1 ]; then
    db_fset netcfg/get_hostname seen false
    db_input critical netcfg/get_hostname || true
    db_go
fi
# Do not accept a public mirror selected accidentally through an earlier menu.
db_set mirror/http/hostname @ADDRESS@
db_set mirror/http/directory /debian
db_set mirror/http/proxy ''
# In apt-setup 0.198, use_mirror=false is honoured only for CD installs.
# Install a generator that runs after udebs are unpacked, before 50mirror.
# 60local supplies all three signed local sources with consistent options.
mkdir -p /usr/lib/apt-setup/generators
cat > /usr/lib/apt-setup/generators/00offline-policy <<'POLICY'
#!/bin/sh
set -eu
mirror="$(dirname "$0")/50mirror"
original="$(dirname "$0")/../offline-original-50mirror"
expected=75c441b672f42d91225dc81f729b20cf73d5c5916393e037fda40c85337d8d60
stub="$mirror.offline-new"
# Never leave temporary files inside the generator directory on failure.
trap 'status=$?; rm -f "$stub"; if [ "$status" -ne 0 ]; then exit 10; fi' EXIT
cat > "$stub" <<'STUB'
#!/bin/sh
# Offline PXE: repositories are supplied by 60local with per-source options.
exit 1
STUB
if cmp -s "$mirror" "$stub"; then
    exit 0
fi
actual=$(sha256sum "$mirror")
if [ "${actual%% *}" != "$expected" ]; then
    echo 'offline-pxe: unreviewed apt-setup 50mirror; refusing to configure APT' >&2
    exit 10
fi
cp -p "$mirror" "$original"
chmod 755 "$stub"
mv "$stub" "$mirror"
POLICY
chmod 755 /usr/lib/apt-setup/generators/00offline-policy
