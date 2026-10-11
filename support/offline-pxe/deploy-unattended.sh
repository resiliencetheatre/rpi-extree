#!/bin/sh
# Deploy only control files; mirror packages and signed metadata are unchanged.
set -eu
case "${1:-}" in
    --enable-destructive-profile|--disable) action=$1;;
    *) echo 'Usage: deploy-unattended.sh --enable-destructive-profile | --disable' >&2; exit 2;;
esac
[ "$#" -eq 1 ] && [ "$(id -u)" = 0 ]
bundle=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. /etc/offline-pxe/runtime.conf
[ "$(findmnt -rn -M /srv/offline -o UUID)" = "$SSD_UUID" ]
generation=$(readlink -f /srv/offline/current)
case "$generation" in /srv/offline/generations/*) ;; *) exit 1;; esac
mkdir -p /run/offline-pxe
exec 9>/run/offline-pxe/activation.lock
flock -n 9
cd "$generation"
sha256sum -c ready.sha256 >/dev/null
# Do not stop healthy services or modify content with an unacknowledged clock.
/usr/sbin/offline-ready
backup=unattended-profile-backup
work=$(mktemp -d /run/offline-profile.XXXXXX)
cleanup() { rm -rf "$work"; }
trap cleanup EXIT
if [ "$action" = --enable-destructive-profile ]; then
    [ ! -e "$backup" ] || { echo 'Disable the current unattended profile before replacing it' >&2; exit 1; }
    archive="$bundle/unattended-profile.tar.gz"
    # Target BusyBox tar may lack integrated gzip (-z) support. Decompress
    # separately so gzip errors are checked without relying on pipefail.
    gzip -dc "$archive" > "$work/payload.tar"
    tar -tf "$work/payload.tar" > "$work/archive-list"
    while IFS= read -r file; do
        case "$file" in
            www/preseed/offline.cfg|www/preseed/interactive.cfg|www/preseed/offline.sources|www/preseed/early.sh|www/preseed/late.sh|www/preseed/nvme.cfg|www/preseed/nvme-early.sh|www/preseed/nvme-late.sh|www/preseed/sata.cfg|www/preseed/sata-early.sh|www/preseed/sata-late.sh|tftp/debian-installer/amd64/grub/grub.cfg|tftp/debian-installer/amd64/boot-screens/syslinux.cfg|payload.sha256|profile-generation|profile-server) ;;
            *) echo 'Unexpected file in profile archive' >&2; exit 1;;
        esac
    done < "$work/archive-list"
    tar -xf "$work/payload.tar" -C "$work"
    [ "$(cat "$work/profile-generation")" = "$(basename "$generation")" ]
    [ "$(cat "$work/profile-server")" = "$SERVER" ]
    (cd "$work" && sha256sum -c payload.sha256 >/dev/null)
else
    [ -f "$backup/ready.sha256" ] && [ -f "$backup/new-files" ]
fi
# Any failure from here leaves services stopped and maintenance set.
failed_cleanup() {
    mount -o remount,ro /srv/offline || :
    cleanup
    echo 'Deployment incomplete: services stopped, maintenance retained. Check the preceding error before retrying.' >&2
}
trap failed_cleanup EXIT
: > /run/offline-pxe/maintenance
systemctl stop offline-recover.timer offline-recover.service
systemctl stop offline-dnsmasq.service offline-nginx.service
mount -o remount,rw /srv/offline
if [ "$action" = --enable-destructive-profile ]; then
    mkdir "$backup"
    cp -p ready.sha256 "$backup/ready.sha256"
    : > "$backup/new-files"
    while read -r hash file; do
        [ ! -L "$work/$file" ]
        if [ -e "$file" ]; then
            mkdir -p "$backup/original/$(dirname "$file")"
            cp -p "$file" "$backup/original/$file"
        else
            echo "$file" >> "$backup/new-files"
        fi
        mkdir -p "$(dirname "$file")"
        cp "$work/$file" "$file"
        chmod 644 "$file"
    done < "$work/payload.sha256"
    {
        echo 'Explicitly enabled NVMe/SATA unattended profiles; package verification unchanged.'
        date -u
        sha256sum "$archive" "$backup/ready.sha256"
    } > unattended-profile-change.txt
    awk 'NR==FNR {changed[$2]=1; next} !($2 in changed)' "$work/payload.sha256" ready.sha256 > ready.sha256.new
    cat "$work/payload.sha256" >> ready.sha256.new
    sha256sum unattended-profile-change.txt >> ready.sha256.new
    mv ready.sha256.new ready.sha256
else
    cp -a "$backup/original/." ./
    while IFS= read -r file; do rm -f "$file"; done < "$backup/new-files"
    cp "$backup/ready.sha256" ready.sha256
    rm -f unattended-profile-change.txt
    mv "$backup" "$backup.disabled-$(date +%s)"
fi
sha256sum -c ready.sha256 >/dev/null
sync
mount -o remount,ro /srv/offline
rm /run/offline-pxe/maintenance
/usr/sbin/offline-ready
systemctl start offline-dnsmasq.service offline-nginx.service
systemctl start offline-recover.timer
trap cleanup EXIT
echo "Completed $action. Do not switch profiles during an installation."
