# Third mirror-data partition on the appliance microSD

Workstation path setup (adjust once for your checkout):

```sh
WORKSPACE=/path/to/workspace
export BR2_EXTERNAL="$WORKSPACE/rpi-extree"
```


The image includes `/usr/bin/offline-mirror-card`. Nothing invokes it at boot.
The firmware image remains small, with its existing boot and rootfs partitions.
The script explicitly creates partition 3 in the unused tail of the actual card,
then formats/configures it in separate operations. It does not extend rootfs or
embed the package mirror in the firmware image.

This is a deliberate exception to the normal prohibition on modifying a system
disk: only appending partition 3 to this appliance's running microSD is supported.
The explicit device and action flags are required. The script verifies that the
specified card's partition 2 is the running rootfs, the table is DOS/MBR, the first
partition is FAT32 LBA and the second Linux, and kernel/table geometry agrees.
It refuses an existing partition 3 during creation, active holders/swap, active
installer services, and mounted partition 3 during format/configuration. Formatting
refuses any existing filesystem/signature, even if a destructive flag was passed.
It never formats partitions 1 or 2. It shows card identity including CID first.

Before use, back up anything important on the card and keep the console connected.
Partition-table backups are saved in `/var/lib/offline-pxe/card-backups/` on rootfs.
These protect the table only, not all card contents. Reflashing sdcard.img after
populating the mirror replaces the partition table; do not do that as a routine
mirror refresh. Prepare the final firmware image before populating the data area.

## Rebuild

The defconfig now explicitly selects util-linux wipefs. If reusing the current
appliance output directory, reload the defconfig and reconfigure that package:

```sh
export BR2_EXTERNAL="$WORKSPACE/rpi-extree"
cd "$WORKSPACE/buildroot"
make rpi4_offline_pxe_defconfig
make util-linux-reconfigure
make -j8
```

If you build with `O=...`, pass the same O value to every command instead. For a
fresh output directory the explicit util-linux-reconfigure step is unnecessary.
A post-build check refuses an image missing the required partition tools.
The user performs the image build; no build or physical-device write was run by
the agent for this change.

## On the Pi after flashing and booting

Identify the card with `lsblk`. The following example uses `/dev/mmcblk0`, observed
on this Pi. Always confirm it is the intended card. Stop the netboot diagnostic
with Ctrl-C first; the script refuses a held diagnostic/activation lock.

1. Inspect only; no changes:

   ```sh
   offline-mirror-card inspect /dev/mmcblk0
   ```

2. Create partition 3 using the remaining card capacity:

   ```sh
   offline-mirror-card create /dev/mmcblk0 --create-third-partition
   reboot
   ```

   Partitions 1 and 2 stay unchanged. The script intentionally does not ask the
   running kernel to reread its root disk; a reboot is required before formatting.
   It checks that the original boot/root entries survived the append operation.
   Creation refuses if partition 3 already exists; don't repeat it after success.

3. After reboot, format only the blank third partition:

   ```sh
   offline-mirror-card format /dev/mmcblk0 --format-new-third-partition
   ```

   This creates ext4 labelled `offline-mirror`, with no reserved-block percentage,
   and prints its UUID. It refuses to erase any existing filesystem signature.
   An interrupted format that left a signature requires investigation rather than
   automatic retry with forced formatting.

4. Configure the appliance to use it:

   ```sh
   offline-mirror-card configure /dev/mmcblk0 --use-third-partition
   systemctl start srv-offline.mount
   findmnt /srv/offline
   lsblk -f
   ```

   This creates empty generations/staging directories and sets the UUID in the
   on-device `settings.json`, `runtime.conf`, and `srv-offline.mount`. It also
   enables `srv-offline.mount` for automatic mounting on subsequent boots. Runtime
   serving uses a read-only mount. Copy the UUID into the desk/build settings
   files too so a later build or transfer uses the same storage identity.

Installer services still require a verified generation and an acknowledged clock.
No DHCP server starts merely because the partition was created. Recovery timer
state is restored when the script exits. If an operation is killed forcibly or a
mount cannot be cleaned up, investigate before clearing a maintenance flag.

Prepare the archive on desk. To populate this card, shut down the Pi and attach
it to desk; transfer/verification is a separate step. Don't write a live served
mirror. The 512 GB capacity is sufficient for initial testing and two generations
near the measured 147.31 GB package size; confirm actual required/free bytes on
future refreshes rather than assuming archive size stays fixed.

## Validation

- Shell syntax and Buildroot merged-overlay check passed.
- Defconfig/olddefconfig retain util-linux binaries, mount and wipefs selections.
- Exact sfdisk append flags tested on a sparse 512 GB regular-file disk image.
  DOS disk ID, partition 1/2 entries and data sentinels survived; partition 3
  occupied the aligned remaining sectors; sfdisk table verification passed.
- Running-root-card creation/reboot, ext4 formatting and UUID configuration on the
  physical Pi are not yet tested. No physical disk was modified during validation.

## Automatic mounting

After `configure`, systemd mounts the configured UUID at `/srv/offline` on every
boot. Builds with a real UUID in settings also enable the mount automatically;
the all-zero example UUID is not enabled by the build hook. The mount job has a
20-second timeout for absent storage. Installer services retain their separate
manifest and clock readiness checks.

For an image built before the unit gained an Install section, enable the existing
UUID-configured unit with an equivalent persistent dependency:

```sh
mkdir -p /etc/systemd/system/multi-user.target.wants
ln -s ../srv-offline.mount /etc/systemd/system/multi-user.target.wants/srv-offline.mount
systemctl daemon-reload
systemctl start srv-offline.mount
```

Use this only after the unit's What= contains the real data filesystem UUID.
New images can instead use `systemctl enable --now srv-offline.mount`.
