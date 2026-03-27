#!/bin/sh
set -eu

dev=/dev/mmcblk0
part="${dev}p3"
mapname="internaldrive"
mapper="/dev/mapper/$mapname"
fslabel="internaldrive"

log() {
    echo "[create-partition] $*"
}

fail() {
    echo "[create-partition] ERROR: $*" >&2
    exit 1
}

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

need_cmd parted
need_cmd awk
need_cmd cryptsetup
need_cmd mkfs.ext4
need_cmd dd
need_cmd sync
need_cmd sleep

[ -b "$dev" ] || fail "Block device not found: $dev"

log "Starting on $dev"

log "Closing old mappings and unmounting old filesystems if present"
umount "$mapper" 2>/dev/null || true
umount "$part" 2>/dev/null || true
cryptsetup close "$mapname" 2>/dev/null || true
sleep 1

end2=$(parted -m "$dev" unit s print | awk -F: '$1==2 { gsub("s","",$3); print $3 }')
[ -n "$end2" ] || fail "Could not find partition 2 on $dev"

if parted -m "$dev" unit s print | awk -F: '$1==3 { found=1 } END { exit !found }'
then
    log "Existing partition 3 found, removing it"
    parted --script "$dev" rm 3 || fail "Failed to remove partition 3"
    sync
    partprobe "$dev" 2>/dev/null || true
    sleep 2
fi

start3=$(( ((end2 + 1) + 2047) / 2048 * 2048 ))

log "Partition 2 ends at sector ${end2}"
log "Creating partition 3 from ${start3}s to 100%"
parted --script "$dev" mkpart primary "${start3}s" 100% || fail "Failed to create partition 3"

sync
partprobe "$dev" 2>/dev/null || true
sleep 2

i=0
while [ ! -b "$part" ]; do
    i=$((i + 1))
    [ "$i" -lt 15 ] || fail "Partition device did not appear: $part"
    sleep 1
done

log "Partition device is present: $part"

log "Zeroing first 8 MiB of $part"
dd if=/dev/zero of="$part" bs=1M count=8 conv=fsync 2>/dev/null || fail "dd failed on $part"

log "About to DESTROY all data on $part and create a new LUKS2 container"
cryptsetup luksFormat --type luks2 "$part" || fail "luksFormat failed"

log "Opening LUKS container as $mapname"
cryptsetup luksOpen "$part" "$mapname" || fail "luksOpen failed"

i=0
while [ ! -b "$mapper" ]; do
    i=$((i + 1))
    [ "$i" -lt 10 ] || fail "Mapper device did not appear: $mapper"
    sleep 1
done

log "Zeroing first 8 MiB of $mapper"
dd if=/dev/zero of="$mapper" bs=1M count=8 conv=fsync 2>/dev/null || fail "dd failed on $mapper"

log "Creating ext4 filesystem with label $fslabel on $mapper"
mkfs.ext4 -F -L "$fslabel" "$mapper" || fail "mkfs.ext4 failed"

log "Final LUKS status"
cryptsetup status "$mapname" || true

log "Final partition table"
parted "$dev" unit s print || true

log "Done"
log "Encrypted device: $part"
log "Mapped device:    $mapper"
