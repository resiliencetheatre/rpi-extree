#!/bin/sh
set -eu
if [ "$#" -ne 1 ]; then
    echo 'Usage: offline-clock "YYYY-MM-DD HH:MM:SS" (current UTC), or offline-clock --rtc' >&2
    exit 2
fi
# Serialize manual setting with a possibly running automatic RTC restore.
if [ -f /etc/systemd/system/offline-rtc.service ]; then
    systemctl stop offline-rtc.service
fi
if [ "$1" = --rtc ]; then hwclock --hctosys --utc; else date -u -s "$1"; fi
[ "$(date +%s)" -ge 1754006400 ]
: > /run/offline-clock-ready
systemctl start offline-recover.service
