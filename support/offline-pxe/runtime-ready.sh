#!/bin/sh
set -eu
fail() { echo "offline-pxe: $*" >&2; exit 1; }
. /etc/offline-pxe/runtime.conf
[ ! -e /run/offline-pxe/maintenance ] || fail 'Maintenance in progress'
[ "$(findmnt -rn -M /srv/offline -o UUID)" = "$SSD_UUID" ] || fail 'SSD not mounted with configured UUID'
[ "$(findmnt -rn -M /srv/offline -o FSTYPE)" = ext4 ] || fail 'SSD is not ext4'
case ",$(findmnt -rn -M /srv/offline -o OPTIONS)," in *,ro,*) ;; *) fail 'Serving requires a read-only SSD mount';; esac
[ -f /run/offline-clock-ready ] || fail 'Set and acknowledge current UTC using offline-clock (see README)'
[ "$(date +%s)" -ge 1754006400 ] || fail 'Clock precedes Debian 13'
generation=$(readlink -f /srv/offline/current)
case "$generation" in /srv/offline/generations/*) ;; *) fail 'current escapes generations';; esac
[ -f "$generation/ready.sha256" ] || fail 'Missing host verification seal'
# This checksum list covers the manifest, signed Releases, and boot/preseed config;
# full index-to-pool hashing belongs on the workstation.
(cd "$generation" && sha256sum -c ready.sha256 >/dev/null) || fail 'Generation readiness checksums failed'
[ -f "$generation/manifest.json" ] || fail 'Missing manifest'
grep -q '"outcome": "verified"' "$generation/manifest.json" || fail 'Generation not verified'
[ -s "$generation/tftp/debian-installer/amd64/initrd.gz" ] || fail 'Missing installer initrd'
mkdir -p /run/offline-pxe/status
{
    echo '<!doctype html><title>Offline Debian snapshot</title><h1>Offline Debian snapshot</h1><pre>'
    cat "$generation/manifest.json"
    echo; df -h /srv/offline
    echo "Clock: acknowledged (manual or enrolled RTC), UTC $(date -u)"
    echo '</pre>'
} > /run/offline-pxe/status/index.html
