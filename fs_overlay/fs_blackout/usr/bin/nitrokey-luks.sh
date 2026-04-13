#!/bin/sh

set -eu

USB_VID="20a0"
USB_PID="42b2"

LUKS_DEV="/dev/mmcblk0p3"
MAPPER_NAME="internaldrive"
MAPPER_DEV="/dev/mapper/${MAPPER_NAME}"
MOUNT_POINT="/mnt/internaldrive"

LOCKDIR="/run/nitrokey-luks.lock"
STATUS_FILE="/tmp/nitrokey-ui-status"
MODE_STATE="/run/audio-mode-selected"

log() {
    logger -t nitrokey-luks "$*"
    echo "nitrokey-luks: $*"
}

ui_status() {
    printf '%s\n' "$1" > "$STATUS_FILE"
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

cleanup_lock() {
    rmdir "$LOCKDIR" 2>/dev/null || true
}

acquire_lock() {
    i=0
    while ! mkdir "$LOCKDIR" 2>/dev/null; do
        i=$((i + 1))
        if [ "$i" -ge 50 ]; then
            log "could not acquire lock"
            exit 1
        fi
        sleep 0.1
    done
    trap cleanup_lock EXIT INT TERM
}

open_luks_with_retries() {
    try=1
    max=5

    while [ "$try" -le "$max" ]; do
        if ! is_nitro_present; then
            log "Nitrokey disappeared before unlock"
            ui_status "unlock_failed"
            return 1
        fi

        log "opening LUKS device $LUKS_DEV as $MAPPER_NAME (try $try/$max)"
        ui_status "waiting_for_touch"

        if cryptsetup luksOpen "$LUKS_DEV" "$MAPPER_NAME"; then
            ui_status "unlock_ok"
            return 0
        fi

        log "unlock attempt $try failed"
        ui_status "unlock_failed"
        try=$((try + 1))

        if [ "$try" -le "$max" ]; then
            sleep 1
        fi
    done

    log "failed to open LUKS device after retries"
    ui_status "unlock_failed"
    return 1
}

wait_for_wg0() {
    i=0
    max=30

    while [ "$i" -lt "$max" ]; do
        if ip link show wg0 >/dev/null 2>&1; then
            log "wg0 is up"
            return 0
        fi
        i=$((i + 1))
        sleep 1
    done

    log "wg0 did not appear within timeout"
    return 1
}

reapply_selected_audio_mode() {
    [ -f "$MODE_STATE" ] || return 0

    mode="$(cat "$MODE_STATE" 2>/dev/null || true)"

    case "$mode" in
        codec2|opus|udpptt|spacecom)
            log "reapplying selected audio mode: $mode"
            /usr/bin/set-audio-mode "$mode" || true
            ;;
        *)
            log "no valid saved audio mode found"
            ;;
    esac
}

do_start() {
    if ! is_nitro_present; then
        log "Nitrokey not present, nothing to do"
        ui_status "idle"
        return 0
    fi

    ui_status "token_detected"

    if ! is_mapper_open; then
        log "waiting 5s for token to settle"
        sleep 5

        if ! open_luks_with_retries; then
            return 1
        fi
    else
        log "mapper already open"
        ui_status "unlock_ok"
    fi

    mkdir -p "$MOUNT_POINT"

    if ! is_mounted; then
        log "mounting $MAPPER_DEV on $MOUNT_POINT"
        mount "$MAPPER_DEV" "$MOUNT_POINT"
    else
        log "mountpoint already mounted"
    fi

    ui_status "mounted"

    log "starting internaldrive connection services"
    systemctl start internaldrive-connection.service

    if wait_for_wg0; then
        reapply_selected_audio_mode
    fi
}

do_stop() {
    log "stopping spacecom stack"
    systemctl stop spacecom-stack.target || true

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

    ui_status "unmounted"
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
