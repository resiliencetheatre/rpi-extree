# vcgencmd

Standalone mailbox implementation from Raspberry Pi's utils repository:
https://github.com/raspberrypi/utils/blob/master/vcgencmd/vcgencmd.c

Vendored source snapshot retrieved 2026-11-06. The BSD-3-Clause copyright and
license are retained at the top of the source. No legacy userland libraries are
needed. Local changes bound command assembly and firmware-response copying. The utility communicates through `/dev/vcio_gencmd` or `/dev/vcio`.

Both reTerminal defconfigs enable this package and their shared kernel fragment
requires `CONFIG_RASPBERRYPI_FIRMWARE=y` and `CONFIG_BCM_VCIO=y`.

After boot, run as root:

```sh
vcgencmd bootloader_version
vcgencmd bootloader_config
vcgencmd version
```

Reload the corresponding reTerminal defconfig before building an existing output
directory, or enable `BR2_PACKAGE_VCGENCMD=y` in menuconfig. Defconfig edits do not
automatically change an existing output's active configuration. Preserve any
local configuration changes before reloading a defconfig. A normal complete build
then includes `/usr/bin/vcgencmd` in the rootfs. For A/B builds, supply the release
version and absolute public-key path as documented in the board README.
