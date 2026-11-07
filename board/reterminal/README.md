# Original Seeed reTerminal / CM4

This defconfig retains the PocketTerm 64-bit 6.18 kernel and framebuffer
userspace, and changes the board support to the original 5-inch reTerminal.
It is not for reTerminal DM or the e-paper reTerminal series.

## Storage and build

microSD boot requires a **CM4 Lite (without eMMC)**. The factory eMMC CM4 cannot
use the carrier's microSD slot for this image. For that module, flash the disk
image to eMMC using the reTerminal USB/rpiboot procedure instead.
See https://wiki.seeedstudio.com/reTerminal-FAQ/ .

Run from the Buildroot source directory (a fresh output directory is recommended):

```sh
make O="$PWD/../output-reterminal" BR2_EXTERNAL="$PWD/../rpi-extree" raspberrypi4_reterminal_defconfig
make O="$PWD/../output-reterminal"
```

As with the source PocketTerm defconfig, the local userspace package sources
must exist beside rpi-extree, including `lvgl-console`. Consult each local
package's SITE in package/*/*.mk. They are not present in this checkout.

The result is `output-reterminal/images/sdcard.img`, containing a 64 MiB FAT
boot partition and the existing 512 MiB ext4 root partition. Write the whole
image to the microSD card, not to an individual partition. Root and boot use
fixed partition UUIDs so MMC enumeration does not select the Wi-Fi SDIO device.
Do not attach a second disk flashed with the same image when booting.

## Board support

- bcm2711-rpi-cm4.dtb and Pi 4 start4/fixup4 firmware.
- Full VC4 KMS with DRM framebuffer emulation, Seeed's `mipi_dsi.ko` display,
  backlight and touchscreen driver, loaded by systemd-modules-load.
- CM4 USB2 host, I2C3 RTC, GPIO expander, buttons and LEDs. The final kernel
  fragment restores populated peripherals disabled by linux-modest.fragment.
- Existing Ethernet DHCP, Wi-Fi firmware and userspace are retained.

The overlay is from Seeed's original reTerminal overlay:
https://github.com/Seeed-Studio/seeed-linux-dtoverlays/blob/master/overlays/rpi/reTerminal-overlay.dts
The firmware settings follow their installer:
https://github.com/Seeed-Studio/seeed-linux-dtoverlays/blob/master/scripts/reTerminal.sh
The overlay describes additional sensors, but their Seeed out-of-tree modules
and the optional charger module are not included by this display-focused port.

The panel's native mode is 720x1280. The reTerminal systemd drop-in sets
`LV_DISPLAY_ROTATION=90` to rotate LVGL clockwise in software and present a
1280x720 logical display. LVGL also transforms pointer coordinates for display
rotation. Check touch alignment on the physical device with the existing
`tp_rotate=1` controller setting.

`fbcon=rotate:1` sets text-console rotation separately. It does not rotate
application pixel writes. The post-image hook refreshes config.txt and cmdline.txt
on every image build, including when rpi-firmware is already built.
HDMI can change framebuffer allocation; test the LCD
without HDMI attached first.

## Validation

The defconfig resolves in this Buildroot checkout and selects the module
package and firmware overlays. Shell syntax and package metadata have been
checked. The initial image was reported to boot on hardware. After that test,
the display module was updated to use the DRM orientation callback and quiet
normal deferred probes, and cross-built successfully against the workspace's
6.18.60-v8 kernel. These driver fixes still need a hardware retest.

To include changes to the local module sources in an existing build, run from
the Buildroot source directory (use the same O= argument as the original build,
if any):

```sh
make reterminal-drivers-rebuild
make
```

The RTC's "low voltage detected" warning means its time is not trustworthy.
Once the system date is correct (for example after network synchronization),
write it to the reTerminal RTC using `hwclock --systohc --utc --rtc /dev/rtc0`
(check the RTC number first). If the warning returns after removing power,
check the RTC backup battery and connection.

After building and booting, check `dmesg` for `mipi_dsi`, `ls /dev/fb*`,
`cat /sys/class/graphics/fb0/virtual_size`, and
`evtest /dev/input/touchscreen`. Verify LCD backlight, touch alignment, front
buttons, USB, RTC, Ethernet and Wi-Fi before deployment. The serial console
is PL011 on GPIO14/15 at 115200 baud.

## Front-button push-to-talk

`reterminal-ptt.service` starts automatically and discovers the `gpio_keys`
input device by name. KEY_F (code 33) press sends `ptt_helper --ptt_down`, and
release sends `--ptt_up`, to `/tmp/udpptt.sock`. Autorepeat and other keys are
ignored. The device is not exclusively grabbed, so other input consumers can
still see its keys. The helper uses Python 3 standard-library modules only;
Python 3 is enabled in this defconfig.

If running the executable reports "not found" even though it exists, check
`ls -l /usr/bin/python3`: its shebang requires that interpreter. Changing the
defconfig does not update an existing `.config`. Enable Python 3 in the active
configuration and rebuild; the board post-build hook now rejects an image
missing this interpreter.

The script releases PTT on normal shutdown, input disconnect, or an evdev
queue overflow. Failed socket commands are retried, and client socket replacement
resends the current button state. After an overflow, TX remains released until a
fresh press. An uncatchable process kill cannot send a release command; the
restarted helper begins by sending UP. Use this helper as the sole producer of
socket PTT commands: the client socket has one shared pressed state rather than
separate ownership per sender. Existing keyboard PTT remains independent.

Optional device/socket overrides live in `/etc/default/reterminal-ptt`:

```sh
# Normally omit this: event numbers can change.
# RETERMINAL_PTT_DEVICE=/dev/input/event0
RETERMINAL_PTT_SOCKET=/tmp/udpptt.sock
```

Reload the updated defconfig (or enable Python 3 in your existing Buildroot
configuration), then build the image with `make`. The board post-build hook
enables the service. On the target, inspect it with
`systemctl status reterminal-ptt` and `journalctl -u reterminal-ptt -f`.
Stop the service before manually testing with `ptt_helper`.

Host integration check:

```sh
python3 ../rpi-extree/board/reterminal/tests/test_ptt.py
```

This uses native evdev records through a FIFO and a recording helper to check
command edges, autorepeat, unrelated keys, queue overflow, socket replacement,
and shutdown. Physical button/radio operation still needs a target test.

## Firmware diagnostics

Both reTerminal profiles include `/usr/bin/vcgencmd` for firmware diagnostics:

```sh
vcgencmd bootloader_version
vcgencmd bootloader_config
vcgencmd version
```

Run as root. For an existing output, enable `BR2_PACKAGE_VCGENCMD=y` in
menuconfig or reload its reTerminal defconfig before rebuilding; save local
configuration changes before reloading. The shared kernel fragment enables the
required firmware mailbox driver. Hardware execution still requires validation.
