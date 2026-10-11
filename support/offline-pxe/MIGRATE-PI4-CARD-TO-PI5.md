# Reuse the populated Pi 4 card on Pi 5

Workstation path setup (adjust once for your checkout):

```sh
WORKSPACE=/path/to/workspace
export BR2_EXTERNAL="$WORKSPACE/rpi-extree"
```


Both targets use the identical DOS/MBR genimage template and sizes:

| Partition | Image | Size | Migration |
| --- | --- | --- | --- |
| 1, FAT boot | boot.vfat | 128 MiB | Replace with Pi 5 image |
| 2, ext4 root | rootfs.ext4 | 512 MiB | Replace with Pi 5 image |
| 3, ext4 mirror | existing card data | Remaining card space | Preserve |

The Pi 5 post-image hook rejects a different layout template or configured rootfs
size. The migration tool additionally compares the **actual completed image and
card** partition offsets, sizes, types and boot flag. It refuses a mismatch.
It writes only the partition device nodes for partitions 1 and 2, never the whole
disk node, partition table, or partition 3. Replacing entire filesystem images
also removes stale Pi 4 boot files and kernel modules.

Do not use an image flasher or `dd sdcard.img` on the whole populated card.
Do not create or format partition 3 again.

## On desk after the Pi 5 build completes

Shut down the Pi cleanly, remove its card and insert it into desk. Confirm the
device again; `/dev/sdc` below is an example from the previous session, not a
permanent device name:

```sh
lsblk -o NAME,SIZE,MODEL,FSTYPE,LABEL,UUID,MOUNTPOINTS
```

The existing mirror UUID must be
`89d3c0d0-322b-4b40-b7af-fad9bf3b09d9`. Unmount any card partitions mounted by
the desktop (including rootfs if present). For the previously observed layout:

```sh
sudo umount /dev/sdc1
sudo umount /dev/sdc3
```

Close file-manager windows that might remount it. Run a read-only check first:

```sh
cd "$BR2_EXTERNAL/support/offline-pxe"
sudo python3 migrate-pi5-card.py \
  --device /dev/sdc \
  --images "$WORKSPACE/buildroot/output-rpi5-offline-pxe/images" \
  --mirror-uuid 89d3c0d0-322b-4b40-b7af-fad9bf3b09d9
```

This requires the completed `sdcard.img`, `boot.vfat`, `rootfs.ext4` and
`offline-pxe-build.json` together. It verifies Pi 5 manifest identity, matching
geometry, that partition images match sdcard.img, and that the card is unmounted
with no active swap/device holders. Any mismatch stops the operation.

After it reports PASS, explicitly replace the two partitions:

```sh
sudo python3 migrate-pi5-card.py \
  --device /dev/sdc \
  --images "$WORKSPACE/buildroot/output-rpi5-offline-pxe/images" \
  --mirror-uuid 89d3c0d0-322b-4b40-b7af-fad9bf3b09d9 \
  --backup-dir /mnt/data/offline-pxe/pi4-card-before-pi5 \
  --write
```

The backup directory must not already exist. The tool saves and verifies the
original 128 MiB boot and 512 MiB root images before replacing either, plus the
partition table and MBR. It reads back both new partitions and checks that the
MBR, partition geometry and mirror UUID are unchanged. Keep the backups and desk
mirror. Rootfs settings, root passwords, installed maintenance keys and any other
rootfs changes are replaced by the new image; the original copies are in the
backup images. The existing verified mirror and its `current` symlink stay on
partition 3, including the previous installer-policy correction.

If writing or read-back fails, do not boot the card yet; preserve the logs and
backup images. Rollback is possible by restoring only the two backup partition
images to their verified partition nodes. Do not restore the whole-disk image or
recreate the partition table as a routine rollback step.

## First Pi 5 boot

Move the card to Pi 5, with suitable power and cooling. Connect the serial adapter
to GPIO14 TX / GPIO15 RX (physical pins 8/10), common ground, at 115200 baud.
The updated Pi 5 configuration uses UART0 on this header. Attach the RTC backup battery.

The default image has a placeholder data UUID. Configure the **existing** third
partition, without creating or formatting it:

```sh
offline-mirror-card inspect /dev/mmcblk0
offline-mirror-card configure /dev/mmcblk0 --use-third-partition
offline-clock 'YYYY-MM-DD HH:MM:SS'
offline-rtc --enroll
systemctl start offline-recover.service
```

Replace the timestamp with actual current UTC. If the image was built with the
correct UUID already, configuring it again is unnecessary. Because the existing
`current` symlink is preserved, another activation is normally unnecessary.

```sh
findmnt /srv/offline
readlink /srv/offline/current
ip -br address
systemctl is-active offline-dnsmasq offline-nginx
curl -f http://192.168.50.1/status/
```

Expect the original mirror UUID mounted read-only, eth0 at 192.168.50.1, two
active services and the existing generation's status. Then test RTC retention
after removing main power, followed by laptop PXE. See RASPBERRY-PI-5.md for RTC
enrollment and hardware-test limits.

Migration checks have been tested with synthetic tables/files; no physical card
has been written by the agent. The actual Pi 5 artifacts must pass the read-only
preflight after your build finishes.
