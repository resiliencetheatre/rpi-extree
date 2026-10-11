# Raspberry Pi 5 offline PXE server

Workstation path setup (adjust once for your checkout):

```sh
WORKSPACE=/path/to/workspace
export BR2_EXTERNAL="$WORKSPACE/rpi-extree"
```


Use `rpi5_offline_pxe_defconfig`. The server remains AArch64; the served Debian
archive and installer remain amd64/all. The Pi 4 target is retained. The Pi 5
target reuses its appliance overlay, mirror tools and service rendering, with
separate Pi 5 firmware, device trees, kernel additions and RTC service.

The base is this checkout's stock Pi 5 configuration: Cortex-A76, bcm2712,
4 KiB pages, kernel commit `21b410140c47ffab5668399f6f143c7d7b935c8b`
(6.12.61). RP1/MACB Ethernet, PCIe, USB storage, SD, ext4 and the firmware RTC
driver are built in. The installation interface remains `eth0` with
`net.ifnames=0`, address 192.168.50.1. Wi-Fi is available as an iwd-managed upstream
client; see [WIFI-UPLINK.md](WIFI-UPLINK.md). No forwarding/NAT, public DNS for
PXE clients, or automatic runtime mirror download is added.

## Build

Keep the old Pi 4 output separate. From the workspace:

```sh
export BR2_EXTERNAL="$WORKSPACE/rpi-extree"
cd "$WORKSPACE/buildroot"
make O=output-rpi5-offline-pxe rpi5_offline_pxe_defconfig
make O=output-rpi5-offline-pxe olddefconfig
make O=output-rpi5-offline-pxe -j8
```

Outputs: `output-rpi5-offline-pxe/images/sdcard.img` and
`output-rpi5-offline-pxe/images/offline-pxe-build.json`.
The existing verified diagnostic payload in the Pi 4 overlay is shared;
on a fresh checkout follow NETBOOT-TEST.md to stage it first.
For a known data UUID, supply the existing site settings using
`OFFLINE_PXE_SETTINGS=/absolute/path/settings.json` on the final make command.
Otherwise the placeholder UUID leaves production services gated until configured.

Use a spare card for first boot. **Do not flash the whole image over the populated
512 GB mirror card:** that overwrites its partition table. Keep the desk mirror
and working Pi 4 card. Moving boot/root partitions while preserving an existing
third partition is supported by the geometry-checked procedure in
[MIGRATE-PI4-CARD-TO-PI5.md](MIGRATE-PI4-CARD-TO-PI5.md); no disk writes
are part of this configuration change. The same mirror content is reusable on
Pi 5 without another upstream download. Use the existing third-partition setup
and transfer workflow if choosing a new large card.

## Serial and first boot

The appliance uses GPIO14 TX / GPIO15 RX (physical pins 8/10) with a common
ground, UART0 (`ttyAMA0`), 115200 8N1. `uart0-pi5` enables the RP1 UART;
`enable_rp1_uart=1` requests later firmware logging on these pins. Kernel messages
are replayed when the RP1 console registers, followed by systemd and the login
prompt. Bare `earlycon` is omitted because the device-tree stdout path still
points to the dedicated debug connector (`ttyAMA10`). The earliest boot output
is not guaranteed on the GPIO header; EEPROM logging has separate controls.

Check on the Pi:

```sh
cat /proc/device-tree/model
ip -br address
cat /sys/class/rtc/rtc0/name
hwclock --show --utc --rtc=/dev/rtc0
dmesg | grep -E 'rtc|rp1|macb|eth0'
```

Confirm `eth0` and 192.168.50.1/24 before connecting a PXE client. Configure the
mirror UUID/mount using MICROSD-DATA.md or the external data-volume workflow.
The Pi 4's successful installation validates the shared installer configuration,
not Pi 5 hardware networking or storage.

## Battery backed RTC

Pi 5 has an onboard RTC, but retention across power removal requires a connected
backup battery. Charging is intentionally left disabled; only enable the official
charging setting when appropriate for the fitted rechargeable battery. See
[Raspberry Pi RTC documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#real-time-clock-rtc).

Once the battery is connected, set the **actual current UTC**, then enroll:

```sh
offline-clock 'YYYY-MM-DD HH:MM:SS'
offline-rtc --enroll
hwclock --show --utc --rtc=/dev/rtc0
```

Replace the date placeholder. `offline-clock` can return a recovery failure if
the mirror is not configured yet; verify `date -u` and `/run/offline-clock-ready`
before proceeding. Enrollment writes system time to rtc0 and saves a lower bound
on the root filesystem. On subsequent boots, offline-rtc restores UTC from rtc0
before recovery, checks it is no earlier than enrollment, then acknowledges the
clock for installer services. An unreadable or backward RTC leaves services gated.
No battery means automatic clock accuracy cannot be relied on; a plausibility
check is not a battery test or a source of accurate time.

Power down, remove main power for several minutes, and boot again:

```sh
date -u
hwclock --show --utc --rtc=/dev/rtc0
systemctl --no-pager status offline-rtc offline-dnsmasq offline-nginx
findmnt /srv/offline
curl -f http://192.168.50.1/status/
```

Compare UTC to a trusted clock. Then repeat laptop PXE and installation with all
uplinks removed. The server RTC does not set the laptop's RTC; sane client time
is still necessary for Debian signature metadata date checks.

## Checks performed

- Buildroot defconfig/olddefconfig in a new output directory; required service,
  TLS, filesystem and hwclock selections survived.
- Kernel bcm2712 config plus fragments resolved against local pinned 6.12.61
  sources; built-in RP1/MACB/storage/RTC/serial symbols and 4 KiB pages checked.
- Shell syntax and merged-overlay layout passed.
- Post-build fixture exercised shared rendering, the real bundled diagnostic
  payload checksums, Pi 5 manifest naming and RTC tool installation.
- RTC control tests covered enrollment, restore, backward time and read failure
  using mocked hardware commands.
- No full image build, Pi 5 boot or battery-retention test performed by the agent.

The user reported successful Pi 4 PXE installation after the installer-policy
repair. Desktop task selection, Secure Boot and expired-metadata acceptance
remain separate tests. Software-selection/preseed customization is deferred.
