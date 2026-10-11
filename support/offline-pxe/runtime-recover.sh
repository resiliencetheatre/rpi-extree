#!/bin/sh
set -eu
mkdir -p /run/offline-pxe
[ ! -e /run/offline-pxe/maintenance ] || exit 0
# Retry failed mount dependencies as well as failed service starts.
# Inactive units may have been garbage-collected; reset-failed then returns
# nonzero even though starting them is valid. The actual start remains checked.
systemctl reset-failed srv-offline.mount offline-dnsmasq.service offline-nginx.service || :
systemctl start srv-offline.mount
if /usr/sbin/offline-ready; then
    systemctl start offline-dnsmasq.service offline-nginx.service
else
    systemctl stop offline-dnsmasq.service offline-nginx.service
    exit 1
fi
