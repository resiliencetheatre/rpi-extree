#!/bin/bash
#
# Create and mount the maps partition on /dev/mmcblk0.
#
# WARNING: Creating and formatting partitions destroys data in the target area.
#

set -euo pipefail

DISK="/dev/mmcblk0"
PART="${DISK}p3"
START_SECTOR="6211584s"
MOUNTPOINT="/opt/maps"
LABEL="maps"
FSTAB="/etc/fstab"

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: run this script as root." >&2
    exit 1
fi

for command in parted partprobe mkfs.ext4 blkid mount; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Error: required command not found: $command" >&2
        exit 1
    fi
done

if [ ! -b "$DISK" ]; then
    echo "Error: disk does not exist: $DISK" >&2
    exit 1
fi

if [ -b "$PART" ]; then
    echo "Error: $PART already exists."
    echo "Refusing to format an existing partition."
    exit 1
fi

echo "Current partition table:"
parted "$DISK" unit s print

echo
echo "This will create and format $PART using all remaining space."
printf "Type YES to continue: "
read -r answer

if [ "$answer" != "YES" ]; then
    echo "Cancelled."
    exit 1
fi

echo "Creating partition 3..."
parted -s "$DISK" \
    unit s \
    mkpart primary ext4 "$START_SECTOR" 100%

echo "Reloading partition table..."
partprobe "$DISK" || true

# Give udev/devtmpfs a moment to create the partition device.
for attempt in 1 2 3 4 5 6 7 8 9 10; do
    [ -b "$PART" ] && break
    sleep 1
done

if [ ! -b "$PART" ]; then
    echo "Partition was created, but $PART is not available yet."
    echo "Reboot the system and then run:"
    echo "  mkfs.ext4 -L $LABEL $PART"
    echo
    echo "After formatting, rerun the fstab configuration manually."
    exit 1
fi

echo "Formatting $PART as ext4..."
mkfs.ext4 -L "$LABEL" "$PART"

UUID="$(blkid -s UUID -o value "$PART")"

if [ -z "$UUID" ]; then
    echo "Error: could not obtain UUID for $PART" >&2
    exit 1
fi

echo "Partition UUID: $UUID"

mkdir -p "$MOUNTPOINT"

# Keep a backup before modifying fstab.
cp -p "$FSTAB" "${FSTAB}.before-maps"

FSTAB_LINE="UUID=$UUID $MOUNTPOINT ext4 rw,defaults,noatime 0 2"

# Remove existing active or commented /opt/maps entries, then add the new one.
sed -i '\|[[:space:]]/opt/maps[[:space:]]|d' "$FSTAB"
printf '%s\n' "$FSTAB_LINE" >> "$FSTAB"

echo "Added to $FSTAB:"
echo "$FSTAB_LINE"

echo "Checking fstab and mounting $MOUNTPOINT..."
mount -a

echo
echo "Maps partition is ready:"
df -h "$MOUNTPOINT"
findmnt "$MOUNTPOINT" 2>/dev/null || true

echo
echo "Copy planet.pmtiles to:"
echo "  $MOUNTPOINT/planet.pmtiles"
