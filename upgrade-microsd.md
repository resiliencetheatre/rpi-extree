# Upgrade the Buildroot MicroSD while preserving partition 3

This procedure updates the Buildroot boot and root filesystems on an existing
MicroSD card while preserving the third `maps` partition.

Expected layout:

```text
/dev/mmcblk0p1  boot
/dev/mmcblk0p2  root filesystem
/dev/mmcblk0p3  maps — preserved
```

> **Warning:** Verify the target device carefully. Writing to the wrong device
> can destroy data. Never write `sdcard.img` to the whole MicroSD, because that
> would replace its partition table and remove the partition 3 entry.

Run these commands from the Buildroot project directory:

```bash
DEV=/dev/mmcblk0
BOOT_IMG=output/images/boot.vfat
ROOT_IMG=output/images/rootfs.ext4
```

## 1. Verify the device and images

```bash
lsblk -o NAME,SIZE,FSTYPE,LABEL,UUID,MOUNTPOINTS "$DEV"
ls -lh "$BOOT_IMG" "$ROOT_IMG"
```

Confirm that `$DEV` is the intended MicroSD and that partition 3 contains the
`maps` filesystem.

## 2. Check that the images fit

```bash
BOOT_IMG_SIZE=$(stat -c %s "$BOOT_IMG")
ROOT_IMG_SIZE=$(stat -c %s "$ROOT_IMG")

BOOT_PART_SIZE=$(sudo blockdev --getsize64 "${DEV}p1")
ROOT_PART_SIZE=$(sudo blockdev --getsize64 "${DEV}p2")

printf 'Boot image:      %s bytes\n' "$BOOT_IMG_SIZE"
printf 'Boot partition:  %s bytes\n' "$BOOT_PART_SIZE"
printf 'Root image:      %s bytes\n' "$ROOT_IMG_SIZE"
printf 'Root partition:  %s bytes\n' "$ROOT_PART_SIZE"

if [ "$BOOT_IMG_SIZE" -gt "$BOOT_PART_SIZE" ]; then
    echo "ERROR: $BOOT_IMG is larger than ${DEV}p1"
    exit 1
fi

if [ "$ROOT_IMG_SIZE" -gt "$ROOT_PART_SIZE" ]; then
    echo "ERROR: $ROOT_IMG is larger than ${DEV}p2"
    exit 1
fi

echo 'Images fit in the existing partitions.'
```

Do not continue if either check fails.

## 3. Write only partitions 1 and 2

```bash
sudo umount "${DEV}p1" 2>/dev/null || true
sudo umount "${DEV}p2" 2>/dev/null || true

sudo dd if="$BOOT_IMG" \
    of="${DEV}p1" \
    bs=4M \
    conv=fsync \
    status=progress

sudo dd if="$ROOT_IMG" \
    of="${DEV}p2" \
    bs=4M \
    conv=fsync \
    status=progress

sync
```

Do not write anything to `/dev/mmcblk0` or `/dev/mmcblk0p3`.

## 4. Verify the result

```bash
lsblk -o NAME,SIZE,FSTYPE,LABEL,UUID,MOUNTPOINTS "$DEV"
sudo fsck.vfat -n "${DEV}p1"
sudo e2fsck -fn "${DEV}p2"
sudo e2fsck -fn "${DEV}p3"
```

The final layout must still contain all three partitions, with partition 3
retaining its `maps` filesystem and data.

