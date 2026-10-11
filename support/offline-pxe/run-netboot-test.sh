#!/bin/sh
# Foreground, RAM-only DHCP/TFTP diagnostic. Ctrl-C stops it and restores timer state.
set -eu
[ "${1:-}" = --isolated-lan ] && [ "$#" -eq 1 ] || {
    echo 'Usage: sh run-netboot-test.sh --isolated-lan' >&2
    echo 'Only use a direct laptop cable or isolated switch; no other DHCP server.' >&2
    exit 2
}
[ "$(id -u)" -eq 0 ] || { echo 'Run on the Pi as root' >&2; exit 1; }
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case "$base" in /tmp/*|/run/*) ;; *) echo 'Extract the bundle under /tmp or /run (RAM)' >&2; exit 1;; esac
(cd "$base" && sha256sum -c files.sha256 >/dev/null)
. "$base/network.conf"
ip -4 -o address show dev "$INTERFACE" | grep -F " $ADDRESS " >/dev/null || {
    echo "Expected $ADDRESS on $INTERFACE; fix Ethernet first" >&2; exit 1;
}
for unit in offline-dnsmasq.service offline-nginx.service dnsmasq.service; do
    if systemctl is-active --quiet "$unit"; then
        echo "$unit is active; end production installation sessions before testing" >&2; exit 1
    fi
done
if pidof dnsmasq >/dev/null; then echo 'Another dnsmasq is running' >&2; exit 1; fi
mkdir -p /run/offline-pxe
# Reuse the production activation lock so promotion cannot race this test.
exec 9>/run/offline-pxe/activation.lock
flock -n 9 || { echo 'Another test or activation holds the lock' >&2; exit 1; }
[ ! -e /run/offline-pxe/maintenance ] || { echo 'Existing maintenance operation; investigate before testing' >&2; exit 1; }
timer_was_active=no
systemctl is-active --quiet offline-recover.timer && timer_was_active=yes
cleanup() {
    rm -f /run/offline-pxe/maintenance
    if [ "$timer_was_active" = yes ]; then systemctl start offline-recover.timer; fi
}
: > /run/offline-pxe/maintenance
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
systemctl stop offline-recover.timer offline-recover.service
# A previously running recovery may have started a service while being stopped.
for unit in offline-dnsmasq.service offline-nginx.service; do
    if systemctl is-active --quiet "$unit"; then
        echo "$unit started during setup; aborting test" >&2; exit 1
    fi
done
# Explicit paths: never load /etc/dnsmasq.conf or serve the production archive.
dnsmasq --test --conf-file="$base/dnsmasq.conf" --tftp-root="$base/tftp"
echo 'NETBOOT DIAGNOSTIC: select Install, stop at the first language screen. No package mirror.'
echo 'Press Ctrl-C here to stop DHCP/TFTP and restore the recovery timer.'
dnsmasq --keep-in-foreground --conf-file="$base/dnsmasq.conf" \
    --tftp-root="$base/tftp" --dhcp-leasefile="$base/leases" --pid-file="$base/dnsmasq.pid"
