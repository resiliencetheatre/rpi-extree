# Pi serial inspection, 2026-10-10

Connected through `screen /dev/ttyUSB0 115200`. Console was already logged in as
root. Inspected configuration; no reboot, disk formatting, network reconfiguration,
DHCP startup, clock change or production configuration write was performed.
Temporary nginx configuration tests were made under `/tmp` only.

Observed:

- Pi boots AArch64 Linux `6.18.52-v8`, with systemd and about 4 GB RAM.
- Onboard Ethernet is `end0`, driver `bcmgenet`, bus `fd580000.ethernet`, MAC
  `d8:3a:dd:b0:8d:d2`. It is DOWN and has no IP address. Configuration matches `eth0`.
- `/proc/cmdline` and `/boot/cmdline.txt` lack `net.ifnames=0` and contain an older
  display-oriented command line. The source profile has `net.ifnames=0`.
- Only microSD is detected: about 238 GiB, with 128 MiB boot and 512 MiB rootfs
  partitions. No USB SSD/data partition is detected. No repartitioning performed.
- SSD UUID remains `00000000-0000-0000-0000-000000000000`; `/srv/offline` is empty.
- Pi clock reads March 13, 2026, rather than inspection date October 10, 2026.
- `dnsmasq 2.93` includes DHCP and TFTP; `dnsmasq --test` passes.
- `curl 8.22.0` reports HTTPS and OpenSSL 3.6.5. CA bundle exists (216590 bytes).
  No live upstream connection was attempted: the Pi has no configured uplink.
- `findmnt` is absent; `lsblk` is the BusyBox applet without `-o` support.
- `nginx 1.30.3 -t` fails on nonexistent `nogroup`. After correcting the group in
  a temporary config, it also reveals nonexistent cache parent directories.
  A temporary config using group `nobody`, `/tmp` cache paths and loopback
  `127.0.0.1:18080` passes `nginx -t`. The configured LAN address cannot be used
  until Ethernet is configured. No nginx server was launched.
- Offline DHCP and nginx services are inactive; the recovery timer runs but its
  service exits at reset-failed for units that systemd has garbage-collected.
- IPv4 forwarding is 0. Stale WireGuard symlinks to `/mnt/usb` remain from another
  board overlay, further evidence that an existing output tree was reused.

Build output inspection supports a stale incremental-build diagnosis: `buildroot/.config`
selects the new command line and util-linux binaries, while `buildroot/output/images`
still contains the old command line and its target tree has no findmnt. Buildroot
package stamps do not reliably rebuild everything after changing board configurations.
Use a fresh output directory, not the previously used `buildroot/output` tree.

Source fixes made following inspection:

- nginx uses Buildroot's `nobody` group and writable runtime temporary directories;
- recovery continues past a benign reset-failed error, while mount/start failures
  still fail the service;
- post-build rejects a target missing findmnt with a fresh-output diagnostic.

Shell/Python syntax checks passed for these changes. Rebuild and reflash are needed
for the running Pi to receive them. No image build was started by the agent.

Next test:

1. Fresh appliance build and boot; confirm Ethernet is `eth0` with
   `192.168.50.1/24`, findmnt is present and stale overlays are absent.
2. Attach the intended SSD, identify its UUID and set it consistently in settings.
   Do not format/repartition the existing microSD as part of this test.
3. For the production service path, acquire/verify a complete generation and
   activate it with no active installers, after establishing correct UTC time.
4. Connect the laptop on an isolated direct cable, choose one-shot x86_64 UEFI PXE,
   capture DHCP architecture 7/9, next-server and boot filename, then check TFTP
   progress into Debian Installer. Test BIOS and Secure Boot separately.

A quicker installer-welcome-screen-only test could use a separate, explicitly
scoped diagnostic DHCP/TFTP configuration with authenticated Debian netboot files,
without first acquiring the whole archive. That diagnostic mode is not currently
implemented or running; it would not prove offline installation or mirror coverage.
Do not forge a readiness manifest or weaken the production readiness gate to do it.
