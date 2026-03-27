#!/bin/sh

set -eu

USB_VID="20a0"
USB_PID="42b2"

LUKS_DEV="/dev/mmcblk0p3"
MAPPER_NAME="internaldrive"
MAPPER_DEV="/dev/mapper/${MAPPER_NAME}"
MOUNT_POINT="/mnt/internaldrive"

LOCKDIR="/run/nitrokey-luks.lock"

log() {
    logger -t nitrokey-luks "$*"
    echo "nitrokey-luks: $*"
}

is_nitro_present() {
    for d in /sys/bus/usb/devices/*; do
        [ -f "$d/idVendor" ] || continue
        [ -f "$d/idProduct" ] || continue
        vid="$(cat "$d/idVendor" 2>/dev/null || true)"
        pid="$(cat "$d/idProduct" 2>/dev/null || true)"
        if [ "$vid" = "$USB_VID" ] && [ "$pid" = "$USB_PID" ]; then
            return 0
        fi
    done
    return 1
}

is_mapper_open() {
    [ -e "$MAPPER_DEV" ]
}

is_mounted() {
    grep -qs "[[:space:]]$MOUNT_POINT[[:space:]]" /proc/mounts
}

acquire_lock() {
    i=0
    while ! mkdir "$LOCKDIR" 2>/dev/null; do
        i=$((i + 1))
        [ "$i" -ge 50 ] && {
            log "could not acquire lock"
            exit 1
        }
        sleep 0.1
    done
    trap 'rmdir "$LOCKDIR" 2>/dev/null || true' EXIT INT TERM
}

do_start() {
    if ! is_nitro_present; then
        log "Nitrokey not present, nothing to do"
        return 0
    fi

    if ! is_mapper_open; then
        log "opening LUKS device $LUKS_DEV as $MAPPER_NAME"
        cryptsetup luksOpen "$LUKS_DEV" "$MAPPER_NAME"
    else
        log "mapper already open"
    fi

    mkdir -p "$MOUNT_POINT"

    if ! is_mounted; then
        log "mounting $MAPPER_DEV on $MOUNT_POINT"
        mount "$MAPPER_DEV" "$MOUNT_POINT"
    else
        log "mountpoint already mounted"
    fi

    log "starting internaldrive connection services"
    systemctl start internaldrive-connection.service
}

do_stop() {

    log "stopping internaldrive connection services"
    systemctl stop internaldrive-connection.service || true

    if is_mounted; then
	log "unmounting $MOUNT_POINT"
        if ! umount "$MOUNT_POINT"; then
            log "unmount failed, device busy; leaving mapping open"
            return 1
        fi
    else
        log "mountpoint already unmounted"
    fi

    if is_mapper_open; then
        log "closing LUKS mapping $MAPPER_NAME"
        cryptsetup luksClose "$MAPPER_NAME"
    else
        log "mapper already closed"
    fi
}

do_sync() {
    if is_nitro_present; then
        do_start
    else
        do_stop || true
    fi
}

acquire_lock

case "${1:-sync}" in
    start) do_start ;;
    stop)  do_stop ;;
    sync)  do_sync ;;
    *)
        echo "Usage: $0 {start|stop|sync}" >&2
        exit 2
        ;;
esac
