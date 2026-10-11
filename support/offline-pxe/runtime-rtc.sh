#!/bin/sh
# Pi 5 only. Enrol after setting UTC and attaching/testing the backup battery.
set -eu
fail() { echo "offline-rtc: $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || fail 'Root required'
# A manual acknowledgement wins for this boot. Recovery can request this unit
# again after an RTC failure; never clear a valid marker or overwrite that time.
if [ "${1:-}" = --restore ] && [ "$#" -eq 1 ] && [ -f /run/offline-clock-ready ]; then
    echo 'Clock already acknowledged for this boot; keeping current time.'
    exit 0
fi
case "$(cat /sys/class/rtc/rtc0/name)" in
    'rpi-rtc '*) ;;
    *) fail 'Expected Pi 5 rtc0 (rpi-rtc)';;
esac
state=/var/lib/offline-pxe/rtc-enrolled
case "${1:-}" in
    --enroll)
        [ "$#" -eq 1 ] || exit 2
        [ -f /run/offline-clock-ready ] || fail 'Set current UTC with offline-clock first'
        now=$(date +%s)
        [ "$now" -ge 1754006400 ] || fail 'Clock precedes Debian 13'
        hwclock --systohc --utc --rtc=/dev/rtc0
        mkdir -p /var/lib/offline-pxe
        echo "$now" > "$state.new"
        mv "$state.new" "$state"
        echo 'RTC enrolled. Power off, disconnect main power, then verify retained UTC on boot.'
        ;;
    --restore)
        [ "$#" -eq 1 ] || exit 2
        [ -f "$state" ] || fail 'RTC has not been enrolled'
        minimum=$(cat "$state")
        case "$minimum" in ''|*[!0-9]*) fail 'Invalid RTC enrollment';; esac
        hwclock --hctosys --utc --rtc=/dev/rtc0
        now=$(date +%s)
        [ "$now" -ge 1754006400 ] && [ "$now" -ge "$minimum" ] || fail 'RTC moved backwards; set UTC and re-enroll'
        : > /run/offline-clock-ready
        echo 'Clock restored from enrolled RTC; battery retention must be hardware tested.'
        ;;
    *) echo 'Usage: offline-rtc --enroll | --restore' >&2; exit 2;;
esac
