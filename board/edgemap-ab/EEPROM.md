# Raspberry Pi 4 EEPROM preparation for A/B tryboot

Prepare the EEPROM before booting the GPT A/B factory image. This is a separate
provisioning operation: neither the factory image nor SWUpdate updates EEPROM.
These instructions create files only; executing recovery on a board requires
explicit operator authorization. Use a spare recovery microSD and stable power.
Disconnect production boot media during recovery. Record board revision, EEPROM
version/configuration, boot firmware revision and actual SD/USB topology.

The PocketTerm reference recorded incorrect GPT selection with EEPROM 2021-04-29
and working selection with 2026-10-30 revision
`13c4219f16dbe58c5b9946086b474baf572512bb`. That is reference evidence only,
not a validated minimum or an EdgeMap hardware result. Obtain that exact Pi 4
BCM2711 firmware from the official rpi-eeprom distribution, or separately validate
a selected revision. Never substitute a Pi 5 BCM2712 image.

## Record and create a configured recovery image

On the existing Pi OS maintenance system, save `vcgencmd bootloader_version`,
`vcgencmd bootloader_config`, `cat /proc/device-tree/model`, and
`lsblk -o NAME,SIZE,MODEL,TRAN,MOUNTPOINTS`. Keep the output with the acceptance
record. Preserve the original configuration for recovery.

On a maintenance PC with the official rpi-eeprom tools and a pinned checkout:

```sh
export EEPROM_SOURCE=/absolute/path/rpi-eeprom
export EEPROM_INPUT=/absolute/path/selected-pi4-pieeprom.bin
export EEPROM_WORK=/absolute/path/edgemap-eeprom-preparation
mkdir -p "$EEPROM_WORK/recovery"
"$EEPROM_SOURCE/rpi-eeprom-config" "$EEPROM_INPUT" > "$EEPROM_WORK/boot.conf"
```

Review `boot.conf` against the saved board settings. For native SD only use
`BOOT_ORDER=0xf1`; for USB then SD fallback use `BOOT_ORDER=0xf14` (digits are
processed right to left). Select the actual deployment topology; this port has
not established either topology on hardware. Set `BOOT_UART=1` if UART diagnostics
are wanted and electrically available. Do not enable secure boot, OTP programming
or change unrelated power/USB settings. `tryboot_a_b=1` belongs in selector
`autoboot.txt`, not EEPROM `boot.conf`. Preserve compatible board defaults.

```sh
"$EEPROM_SOURCE/rpi-eeprom-config" --config "$EEPROM_WORK/boot.conf" \
  --out "$EEPROM_WORK/recovery/pieeprom.upd" "$EEPROM_INPUT"
"$EEPROM_SOURCE/rpi-eeprom-config" "$EEPROM_WORK/recovery/pieeprom.upd"
sha256sum "$EEPROM_WORK/recovery/pieeprom.upd" | cut -d ' ' -f 1 \
  > "$EEPROM_WORK/recovery/pieeprom.sig"
```

Add the Pi 4 `recovery.bin` supplied by the same pinned official recovery release
as the selected EEPROM. Record source revision and SHA256SUMS of all files.
Alternatively use Raspberry Pi Imager's Pi 4 family bootloader recovery image,
then replace its EEPROM payload/configuration using the steps above. Inspect
its existing files before replacement; do not leave a second `pieeprom.bin` or
an unintended VL805 update payload. The recovery FAT must contain `recovery.bin`,
`pieeprom.upd` and its matching `pieeprom.sig`. Use the official release procedure
for any additional files required by that revision.

To produce a standalone file image without touching a host block device (requires
`sfdisk`, `mkfs.vfat`, `mcopy` from util-linux/dosfstools/mtools):

```sh
truncate -s 64M "$EEPROM_WORK/recovery.vfat"
mkfs.vfat -F 16 "$EEPROM_WORK/recovery.vfat"
mcopy -i "$EEPROM_WORK/recovery.vfat" "$EEPROM_WORK/recovery/"* ::/
truncate -s 66M "$EEPROM_WORK/pi4-eeprom-recovery.img"
printf 'label: dos\nunit: sectors\n\nstart=2048,size=131072,type=e,bootable\n' | \
  sfdisk "$EEPROM_WORK/pi4-eeprom-recovery.img"
dd if="$EEPROM_WORK/recovery.vfat" of="$EEPROM_WORK/pi4-eeprom-recovery.img" \
  bs=1M seek=1 conv=notrunc status=progress
sha256sum "$EEPROM_WORK/pi4-eeprom-recovery.img" > "$EEPROM_WORK/SHA256SUMS"
```

The file is an MBR disk image with one FAT16 recovery partition. Inspect it with
`sfdisk --json` and use a whole-disk image writer, or copy the three files to a
freshly FAT-formatted spare recovery SD card. The `sfdisk` and `dd` commands above
write only the named regular files, never a host block device.
Identify and authorize the destination separately before writing. Boot the Pi 4
from that card only after authorization. Follow the release's documented success
LED/HDMI indication; remove power and the recovery card when complete. Keep this
card and the archived original configuration for local recovery. If recovery
fails, consult the official diagnostic codes and recreate a known-good Pi 4
recovery card; do not repeatedly boot production media with unverified EEPROM.

## Verify with spare A/B media

Boot the maintenance system and record EEPROM version/config again. Boot the
EdgeMap factory media and require normal A/root partition 4, successful Data
growth, then `systemctl reboot --reboot-argument='0 tryboot'` reaching firmware
and B/root partition 5 in a controlled pending trial. Use the update controller
to establish that trial; an unrecorded trial intentionally fails health checks.
Verify fallback after a failed trial, commit after healthy A→B and B→A updates,
and ordinary reboot after commit with `trial:false`. Retest after boot firmware
or EEPROM changes. Measure pre-root/kernel watchdog coverage and perform the
power-cut cases in README.md before deployment. Never weaken selection/growth
guards to accommodate unexpected firmware behavior.

Sources: [official EEPROM tools](https://github.com/raspberrypi/rpi-eeprom),
[boot EEPROM and recovery](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#raspberry-pi-boot-eeprom),
[autoboot and tryboot](https://www.raspberrypi.com/documentation/computers/config_txt.html#autoboot-txt).
