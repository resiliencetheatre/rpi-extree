#!/bin/sh
# Apply the manual-clock/RTC retry fix to an already flashed Pi.
set -eu
[ "$(id -u)" = 0 ]
bundle=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sh -n "$bundle/offline-clock"
sh -n "$bundle/offline-rtc"
systemctl stop offline-recover.timer offline-recover.service
systemctl stop offline-rtc.service
install -m 755 "$bundle/offline-clock" /usr/sbin/offline-clock
install -m 755 "$bundle/offline-rtc" /usr/sbin/offline-rtc
mkdir -p /etc/systemd/system/offline-rtc.service.d
cat > /etc/systemd/system/offline-rtc.service.d/manual-clock.conf <<'UNIT'
[Unit]
ConditionPathExists=!/run/offline-clock-ready
UNIT
systemctl daemon-reload
systemctl reset-failed offline-rtc.service offline-recover.service || :
echo 'Clock tools updated. Set actual UTC with offline-clock, then start offline-recover.timer.'
