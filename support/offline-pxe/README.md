# Raspberry Pi 4 offline Debian appliance

The Pi 5 variant adds [console Wi-Fi with iwd, htop and nano](WIFI-UPLINK.md),
while keeping Ethernet dedicated to the installation LAN.

Workstation path setup (adjust once for your checkout):

```sh
WORKSPACE=/path/to/workspace
export BR2_EXTERNAL="$WORKSPACE/rpi-extree"
```


For explicitly enabled NVMe and SATA profiles based on private preseeds,
see [UNATTENDED-PROFILES.md](UNATTENDED-PROFILES.md). Each unattended selection
automatically replaces its configured client disk; the menu waits by default.

Status: implementation under validation. The defconfig resolves, but no image boot,
full mirror, PXE boot, desktop installation, expired-metadata installation or Secure
Boot test has yet been completed. A successful configuration check is not hardware
acceptance. Use `rpi4_offline_pxe_defconfig`. The user performs the image build.

## Trust and HTTPS

The Pi profile now explicitly includes CA certificates, OpenSSL and the curl binary
with its OpenSSL backend. Buildroot configures curl to use
`/etc/ssl/certs/ca-certificates.crt` and `/etc/ssl/certs`; post-build checks require
the executable and nonempty bundle. CA certificates are built into the image;
refresh the image when updating trust roots. Do not rely on BusyBox wget for
upstream HTTPS verification. BusyBox wget in the installer accesses only local HTTP.

HTTPS validates upstream servers. Debian archive signing keys independently
validate Release/InRelease metadata; SHA256 hashes connect signed indexes to
packages and installer artifacts. The Debian archive keyring is a workstation
prerequisite, separate from the TLS CA bundle. Never bypass certificate or archive
signature errors. Set an accurate UTC clock before using TLS or APT.

The Pi serves the isolated LAN over HTTP and TFTP, so it needs no HTTPS server
certificate or private key. It has no runtime mirror updater. Complete acquisition
uses a connected Debian 13 workstation; the USB SSD is then transferred to the Pi.
Installing curl enables upstream connectivity diagnostics, not full mirroring on
Buildroot. Running the complete downloader on the Pi would require a separate
runtime design, contrary to the default scope in AGENTS.md.

References: [curl certificate validation](https://curl.se/docs/sslcerts.html),
[debmirror options](https://manpages.debian.org/trixie/debmirror/debmirror.1.en.html),
[Debian preseed](https://www.debian.org/releases/trixie/example-preseed.txt).

## Settings and build

For a third data partition on the appliance microSD, see
[MICROSD-DATA.md](MICROSD-DATA.md). Setup is explicit and never runs at boot.

`settings.json` is the single input to target network, DHCP, upstream test URLs,
installer menus, preseeds and final APT sources. Set `ssd_uuid` to the ext4 data
partition's UUID before building (obtain with `lsblk -f` or `blkid`). Its all-zero
example intentionally cannot start installer services. Use a unique generation
name for each snapshot. The selected /24 must not conflict with other client LANs.
The current board requires `eth0`, using `net.ifnames=0`; it does not guess a .link
hardware path. Verify onboard Ethernet on the actual Pi.

```sh
export BR2_EXTERNAL="$WORKSPACE/rpi-extree"
cd "$WORKSPACE/buildroot"
make O="$PWD/output-offline-pxe" rpi4_offline_pxe_defconfig
make O="$PWD/output-offline-pxe" olddefconfig
make O="$PWD/output-offline-pxe" -j8
```

To keep site settings outside git, set `OFFLINE_PXE_SETTINGS` to an absolute JSON
filename when running the build, and pass that same file to workstation tools.
Outputs: `output-offline-pxe/images/sdcard.img` and `offline-pxe-build.json`.
The latter records revisions, resolved symbols and settings. Mirror data belongs
on separate storage outside the source tree and Buildroot download cache.

## Test sequence

A fully offline install depends on populated mirror storage. The operational order
is **boot the Pi -> acquire/verify/populate the SSD -> PXE and install the laptop**.
The production service gate intentionally will not offer PXE from incomplete archive
storage. For a first boot-only test without an SSD, run `offline-netboot-test --isolated-lan`
from the rebuilt image; see the [netboot diagnostic](NETBOOT-TEST.md). It serves authenticated Debian boot files
from RAM and does not prove offline installation or mirror completeness.

### 1. Basic image boot, storage and optional upstream TLS

Use a Pi4 with a reliable power supply, cooling, microSD and powered USB3 SSD.
Leave Ethernet isolated from networks with another DHCP server. Connect a console
and check:

```sh
uname -a
ip -br link
ip -br address
networkctl status eth0
lsblk -f
systemctl status srv-offline.mount offline-recover.timer
journalctl -b -u offline-recover.service --no-pager
```

Expect `eth0` at the configured server address. With no SSD, placeholder UUID,
no verified generation or unacknowledged clock, installer services must remain
stopped and the journal must explain why. The status HTTP endpoint is available
only once storage and clock readiness pass. Wi-Fi is disabled, IP forwarding is
disabled, and the installation LAN has no default-router DHCP option.

Set the actual current UTC time with `date -u -s 'YYYY-MM-DD HH:MM:SS'`.
Once verified content is installed, use
`offline-clock 'YYYY-MM-DD HH:MM:SS'` to also acknowledge time for service startup.
With a fitted and correctly configured RTC, `offline-clock --rtc` reads it and
acknowledges it. The default image does not configure a specific RTC or local NTP.
Repeat the acknowledgement after each boot; stored timestamps are not an accurate
clock after power-off. Set the laptop's firmware clock accurately too: d-i public
NTP is disabled and the Pi is not providing NTP.

The Pi's TLS smoke test needs a deliberately configured maintenance uplink,
working upstream DNS, route and clock. Those are not provided by the isolated
installation-LAN configuration. Prefer a separate maintenance adapter; keep
onboard Ethernet reserved for PXE. Do not enable forwarding or connect the
appliance's authoritative DHCP server to a production LAN. With that connectivity:

```sh
curl --version
ls -l /etc/ssl/certs/ca-certificates.crt
offline-check-upstream-tls
```

The command fetches only three small InRelease files to `/dev/null`, with CA and
hostname verification enabled and HTTPS-only redirects. It does not prove Debian
signature verification or mirror completeness. Keep the output for acceptance.
No live ARM TLS test has been performed yet.

### 2. Workstation mirror acquisition and SSD population

For the desk host using `/mnt/data`, follow [DESK-MIRROR.md](DESK-MIRROR.md).

On a connected Debian 13 workstation install these host-only prerequisites:

```sh
sudo apt-get install ca-certificates debian-archive-keyring debmirror gpgv rsync \
  python3 liblwp-protocol-https-perl libio-socket-ssl-perl initramfs-tools-core \
  dpkg-dev xz-utils gzip tar cpio e2fsprogs util-linux
cd "$BR2_EXTERNAL/support/offline-pxe"
python3 host-preflight.py settings.json --online
```

The preflight tests the Python and Perl TLS stacks, then verifies the three upstream
InRelease files with the configured Debian keyring. `--tls-only --online` skips
mirror-tool availability checks, useful before installing debmirror. Plain
`host-preflight.py settings.json` checks local prerequisites without network use.

The following explicit command authorizes the large download. Do not run it until
you have sufficient dedicated storage. A 2 TB SSD is a planning starting point,
not a measured requirement; staging plus retained generations can need roughly
twice the archive size on ext4. The 100 GiB reserve setting is a stop threshold,
not an archive-size estimate.

```sh
./prepare-mirror.sh settings.json /mnt/mirror-staging --allow-download
```

This downloads complete amd64/Architecture: all coverage of all four components
for trixie, trixie-updates and trixie-security, including installer udebs and amd64
installer images. Defaults exclude sources. Optional additions are
`"architectures": ["amd64", "i386"]` for package co-architecture (not IA32 EFI PXE),
and `"sources": true`; measure their space needs before downloading.

The mirror is staged, never acquired into a served generation. The host verifier
checks signatures, signed indexes and every referenced package's size and SHA256.
Installer trust is signed Release -> SHA256SUMS -> netboot.tar.gz. Both archives
are retried if upstream changes cause inconsistency. Verification must finish
before a generation can be activated. `ready.sha256` is a fast readiness seal,
not a substitute for host verification or protection from a malicious administrator.

Use an existing dedicated ext4 partition. Formatting is optional and is a separate,
explicitly destructive operation. The helper requires `--device`, prints identity,
and refuses mounted/system disks or active holders. Never put a guessed device
name into these commands. If you choose to format, first identify the partition:

```sh
lsblk -o NAME,TYPE,SIZE,MODEL,SERIAL,FSTYPE,UUID,MOUNTPOINTS
# Only after identifying the intended disposable data partition:
# sudo ./populate-ssd.sh settings.json --device /dev/CHOSEN_PARTITION --format --destroy-partition
```

Put the resulting UUID into settings and rebuild the image before deployment.
After acquisition, detach/unmount the SSD from the Pi and attach it to the workstation.
Copy and reverify the generation (substitute your explicit partition and generation):

```sh
# sudo ./populate-ssd.sh settings.json --device /dev/CHOSEN_PARTITION \
#   --generation /mnt/mirror-staging/GENERATION
```

The tool uses an unserved SSD staging directory and retains published generations.
It does not change `current`. Attach the SSD to the Pi, set/acknowledge the clock,
start `srv-offline.mount`, then activate only after all prior installers have ended:

```sh
# offline-activate GENERATION --no-active-installers
```

Services stop during promotion; existing installation sessions must already have
ended. An atomic symlink replacement alone cannot protect an in-progress install.
The SSD is mounted read-only while serving. If activation fails, investigate the
journal and `/run/offline-pxe/maintenance`; do not clear that flag until the SSD is
read-only and a verified generation is selected. After restoring storage,
`systemctl start offline-recover.service` retries immediately; the timer also retries.

### 3. Laptop PXE, installation and later APT

Disconnect maintenance uplinks. Connect an amd64 laptop directly or through an
isolated switch. Select firmware network boot explicitly, preferably one-shot.
Firmware must support PXE on the chosen NIC; USB Ethernet is not automatically
firmware bootable. After install, prefer local disk to avoid installation loops.

On the Pi check `dnsmasq --test`, `nginx -t`, `/status/`, and capture DHCP with
`tcpdump -ni eth0 -vv 'udp port 67 or udp port 68'`. Verify:

- client address in the configured .100-.199 pool, 12-hour lease;
- DNS server is the Pi; no advertised default router;
- BIOS architecture 0 gets `pxelinux.0` and the Pi's next-server address;
- x86_64 UEFI architecture 7 or 9 gets `debian-installer/amd64/bootnetx64.efi`;
- ARM64 and IA32 UEFI do not receive an amd64 EFI executable.

Install Debian 13 with a GNOME desktop task, without uplinks. Both menu entries
use local package sources; the guided profile retains user credentials, hostname
and disk confirmation questions. No destructive zero-touch profile is provided.
Confirm no required public downloads in installer logs. Test wired NIC firmware
on the real laptop; firmware packages in the pool do not prove firmware is present
in the installer initrd. Secure Boot must be tested separately on hardware or an
enrolled-key OVMF VM; preserved signed loaders alone do not establish support.

Boot the laptop's disk. Verify `/etc/apt/sources.list.d/offline.sources`, run
`apt update`, and install a previously unused package. Only local sources should
be active. Check-Valid-Until is disabled only on those sources; Debian signatures,
package checksums and date/future checks remain enabled. No new security updates
arrive after the snapshot date. Test expired updates/security metadata with the
correct current date before accepting frozen-snapshot installation support.

Finally test missing SSD, recovery, interrupted acquisition, checksum corruption,
insufficient storage, failed activation and preservation of the prior generation.
Record Pi storage/network and real laptop firmware results separately from VM tests.

## Checks performed before the image build

- Buildroot revision: `4ab7d13248ef9229cbd94961baec6023e6827f07`.
- External-tree base revision: `18336b80558ace548c738e2ae3d5c207857a2d9d` plus these uncommitted changes.
- Defconfig and olddefconfig: passed; curl/OpenSSL/CA, DHCP/TFTP, nginx HTTP,
  and systemd-networkd selections survive.
- Shell and Python syntax: passed.
- Workstation CA/keyring installed; Python and Perl HTTPS plus gpgv checks passed
  against all three suites on 2026-10-10. Only small metadata files were fetched.
- Full host preflight currently reports missing `debmirror`; install the above
  prerequisites before acquiring. No full mirror has been downloaded.
- Image build and ARM execution: not completed; the user will build the image.
- Nginx runtime, DHCP capture, PXE, offline desktop install, storage recovery and
  Secure Boot acceptance: not yet performed.
# Existing PXE installer source conflict

For the new Pi 5 server target, build commands, serial connector and battery RTC
setup, see [RASPBERRY-PI-5.md](RASPBERRY-PI-5.md). The Pi 4 target remains available.
To reuse its populated microSD without replacing partition 3, follow
[MIGRATE-PI4-CARD-TO-PI5.md](MIGRATE-PI4-CARD-TO-PI5.md) after the Pi 5 build.

For `Conflicting values set for option Check-Valid-Until` during software
selection, see [INSTALLER-POLICY-FIX.md](INSTALLER-POLICY-FIX.md). Apply the
server-side repair before restarting installation. New generated profiles include
the fix; rebuilding firmware alone does not modify an existing data generation.


## Pi 5 manual upstream refresh

See [PI5-MANUAL-REFRESH.md](PI5-MANUAL-REFRESH.md) for the Pi 5-only Wi-Fi
refresh command, private-profile preservation and separate activation. No refresh
is scheduled. Initial acquisition and Pi 4 retain the workstation workflow.
