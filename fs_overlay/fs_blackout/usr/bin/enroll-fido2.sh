#!/bin/sh
set -eu

luks_part="/dev/mmcblk0p3"
rule="/etc/udev/rules.d/99-nitrokey-luks.rules"
rule_disabled="/etc/udev/rules.d/99-nitrokey-luks.rules.disabled"

log() {
    echo "[enroll-fido2] $*"
}

fail() {
    echo "[enroll-fido2] ERROR: $*" >&2
    exit 1
}

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

reload_udev_rules() {
    if command -v udevadm >/dev/null 2>&1; then
        udevadm control --reload-rules 2>/dev/null || true
        udevadm trigger 2>/dev/null || true
    fi
}

restore_rule() {
    if [ -f "$rule_disabled" ] && [ ! -f "$rule" ]; then
        log "Restoring udev rule $rule"
        mv "$rule_disabled" "$rule"
        reload_udev_rules
    fi
}

trap restore_rule EXIT INT TERM

need_cmd systemd-cryptenroll
need_cmd readlink
need_cmd mv
need_cmd sync

[ -b "$luks_part" ] || fail "LUKS partition not found: $luks_part"

log "Starting FIDO2 enrollment for $luks_part"

if [ -f "$rule" ]; then
    log "Temporarily disabling udev rule $rule"
    mv "$rule" "$rule_disabled"
    sync
    reload_udev_rules
elif [ -f "$rule_disabled" ]; then
    log "Udev rule already disabled: $rule_disabled"
else
    log "Udev rule not found, continuing anyway"
fi

echo
echo "Insert your FIDO2 token now."
echo "When it is inserted and ready, press Enter to continue."
read dummy

log "Enrolling FIDO2 token to $luks_part"
systemd-cryptenroll \
    --fido2-device=auto \
    --fido2-with-client-pin=no \
    "$luks_part" || fail "systemd-cryptenroll failed"

log "FIDO2 enrollment completed successfully"

restore_rule
trap - EXIT INT TERM

log "Done"
