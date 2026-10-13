#!/bin/sh
# On the Pi only. Administrator asserts all installation sessions have ended.
set -eu
[ "$#" -eq 2 ] && [ "$2" = --no-active-installers ] || {
    echo 'Usage: offline-activate GENERATION --no-active-installers' >&2; exit 2;
}
case "$1" in ''|*[!A-Za-z0-9_-]*) echo 'Unsafe generation name' >&2; exit 2;; esac
. /etc/offline-pxe/runtime.conf
[ "$(findmnt -rn -M /srv/offline -o UUID)" = "$SSD_UUID" ]
mkdir -p /run/offline-pxe
exec 9>/run/offline-pxe/activation.lock
flock -n 9
[ ! -e /var/lib/offline-pxe/update-transaction.json ] || { echo 'Recover interrupted mirror update first' >&2; exit 1; }
# Reject an incomplete generation before stopping a healthy server.
for suite in debian/dists/trixie debian/dists/trixie-updates debian-security/dists/trixie-security; do
    for file in Release Release.gpg; do
        [ -s "/srv/offline/generations/$1/$suite/$file" ] || {
            echo "Missing installer metadata: $suite/$file; repair this generation first" >&2
            exit 1
        }
    done
done
: > /run/offline-pxe/maintenance
systemctl stop offline-dnsmasq.service offline-nginx.service
# On failure keep maintenance set and services stopped. No automatic rollback
# can establish that an installer has not already read a new generation.
generation="/srv/offline/generations/$1"
[ "$(readlink -f "$generation")" = "$generation" ]
(cd "$generation" && sha256sum -c ready.sha256)
grep -q '"outcome": "verified"' "$generation/manifest.json"
mount -o remount,rw /srv/offline
ln -s "generations/$1" /srv/offline/current.next
mv -Tf /srv/offline/current.next /srv/offline/current
sync
mount -o remount,ro /srv/offline
rm /run/offline-pxe/maintenance
/usr/sbin/offline-ready
systemctl start offline-dnsmasq.service offline-nginx.service
