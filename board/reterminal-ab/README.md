# reTerminal CM4: build, flash, and update

This opt-in profile builds a complete reTerminal system with signed SWUpdate
releases and Raspberry Pi native tryboot. The validated setup is an original
reTerminal, a 32 GB microSD in a USB card reader, and BCM-USB-MSD boot. This is a
CM4/USB adaptation of the Pi 5 milestone described in the workspace AGENTS.md.

Use these two artifacts for different jobs:

| Task | Artifact | Effect |
|---|---|---|
| Initial provisioning or full recovery | `output-reterminal-ab/images/sdcard-ab.img` | Replaces the whole card, including Data |
| Routine release deployment | `releases/<version>/<version>.swu` | Updates only the inactive boot/root pair; preserves Data and the partition table |

**Do not use `images/sdcard.img` for A/B provisioning.** The inherited board hook
also generates that single-slot image, but the A/B factory artifact is
`sdcard-ab.img`. A `.swu` is installed by the target controller, never by `dd`.

## Working directories and tested platform

Run all PC commands below from the workspace root:

```sh
cd /home/tech/laboratory/rpireterm
```

- `buildroot/`: pinned Buildroot checkout.
- `rpi-extree/`: external tree containing the profile, packages, overlays and hooks.
- `output-reterminal-ab/`: A/B build output; reuse this for routine releases.
- `releases/`: archived bundles, checksums and recovery artifacts.
- `output-reterminal-baseline/`: optional regression build of the original
  single-slot profile. It is not an input to the A/B build and is not needed for
  future release builds.

Do not run two builds against the same output directory or change its sources
while a build is running. Save local configuration customizations before reloading
any defconfig. For major toolchain changes, use a fresh output directory.

The observed boot reader is VID `05e3`, PID `0715`. Its Linux disk name can change;
the controller uses the actual root disk and partition identities, not `/dev/sda`.
Keep only the intended boot reader connected during initial validation. Software
can establish USB transport but cannot prove that a USB device contains microSD.
Native SD is separately supported only on CM4 Lite; eMMC, direct NVMe, other boards
and other readers require their own validation.

Tested firmware and build revisions:

| Component | Revision |
|---|---|
| Buildroot, initial integration | `683f63f3bd3d4cc88d8262a3fd8f135e290deb83` (`2026.08-1583-g683f63f3bd`) |
| Buildroot, subsequent clean-build test | `60a3423e958dc4266565c6bdfbb619dd95839314` (`2026.08-1646-g60a3423e95`) |
| External-tree starting revision | `62804b8e40fc55f9cc74fd528ea2c2013bf2b634` plus workspace changes |
| SWUpdate / host genimage | `2026.05.1` / `20` |
| Kernel source | `0b41724521c9adf5399409d02aece6c1df0a4432` |
| Base rpi-firmware package | `063bcab6c8a90efb0d19f69d88cbbc7ec79cab68` |
| A/B `start4.elf` + `fixup4.dat` pair | `ab5c7f86283ceb58b7adb269cae1d16092a31bf6` |
| Installed EEPROM | `13c4219f16dbe58c5b9946086b474baf572512bb`, 2026-10-30 |
| USB recovery tool used | `fdb604d018693465c9aa6ec69879df866d2820da` |

The A/B profile selects `BR2_PACKAGE_RPI_TRYBOOT_FIRMWARE=y` to place that matched,
hash-checked firmware pair in both boot slots and the selector. It includes the
[USB/GPT partition-selection fix](https://github.com/raspberrypi/firmware/commit/ab5c7f86283ceb58b7adb269cae1d16092a31bf6)
for [firmware issue #2047](https://github.com/raspberrypi/firmware/issues/2047).
Updating EEPROM alone does not replace these boot-slot files. Other profiles keep
the base firmware package.

## Signing keys

The commands below use the existing workspace development keys:

```text
ab-development-private.pem
ab-development-public.pem
```

Reuse the same pair across these development releases. **Do not regenerate it for
each update:** the device must already trust the public key corresponding to the
bundle signer. Keep development and production trust separate. Store production
private keys outside source trees and build outputs; do not put private keys in an
overlay, factory image, or bundle. Key rotation and anti-downgrade policy are not
implemented.

Only when starting a new development trust domain, create a pair on the PC:

```sh
umask 077
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 \
  -out ab-development-private.pem
openssl pkey -in ab-development-private.pem -pubout \
  -out ab-development-public.pem
```

The post-build hook embeds only the public PEM, profile and release identifier.
Always pass an **absolute public-key path**: `make -C buildroot` changes the working
directory, so `AB_VERIFY_KEY=ab-development-public.pem` looks in the wrong place.

## Build the initial factory image

Configure the A/B output:

```sh
make -C buildroot O="$PWD/output-reterminal-ab" \
  BR2_EXTERNAL="$PWD/rpi-extree" raspberrypi4_reterminal_ab_defconfig
```

If reusing an output from before Data-growth support, explicitly reconfigure the
packages whose options changed:

```sh
make -C buildroot O="$PWD/output-reterminal-ab" \
  util-linux-reconfigure e2fsprogs-reconfigure
```

This is not needed for a fresh output directory. Buildroot does not automatically
reconfigure already-built packages when their options change: an old util-linux
build can still contain `--disable-partx` despite the new configuration enabling it.
The factory hook checks for `sfdisk`, `partx`, `blockdev` and `resize2fs` and stops
if any are missing. Kernel fragment changes similarly require
`make -C buildroot O="$PWD/output-reterminal-ab" linux-reconfigure`; these latest
Data-growth changes do not require a kernel rebuild.

Build the complete image with a unique version (the tested expanded factory
release was `dev-6`; choose an unused version for a new release):

```sh
AB_RELEASE_VERSION=dev-6 \
AB_VERIFY_KEY="$PWD/ab-development-public.pem" \
  make -C buildroot O="$PWD/output-reterminal-ab" -j4
```

After success, inspect the release marker and output:

```sh
cat output-reterminal-ab/images/release-version
ls -lh output-reterminal-ab/images/sdcard-ab.img
```

Outputs include `sdcard-ab.img`, `selector.vfat`, `boot-a.vfat`, `boot-b.vfat`,
`rootfs.ext4`, `data.ext4`, `genimage-ab.cfg`, `release-version` and
`rpi-tryboot-firmware/`. Both factory slots contain the same complete rootfs and
matching boot assets. No bundle signing step is needed to flash the factory image;
the public verification key is provisioned for future signed updates.

Optional baseline regression build, independent of all A/B artifacts:

```sh
make -C buildroot O="$PWD/output-reterminal-baseline" \
  BR2_EXTERNAL="$PWD/rpi-extree" raspberrypi4_reterminal_defconfig
make -C buildroot O="$PWD/output-reterminal-baseline" -j4
```

## Initial flash on the PC

Reflashing destroys the whole card, including settings, SSH host keys and
application data. Back up anything needed from Data first. A deployed single-slot
card requires offline reprovisioning and selective data restoration; a routine SWU
cannot convert its partition layout.

Shut down reTerminal, disconnect its card reader, and attach the reader to the PC.
Identify the card again; device names can change:

```sh
lsblk -o NAME,SIZE,MODEL,TRAN,MOUNTPOINTS
```

The following is an example **only after the operator has verified that `/dev/sdc`
is the intended spare card**. Unmount each mounted partition belonging to that
card first, using the mountpoints shown by `lsblk`. Then write the whole disk:

```sh
sudo dd if=output-reterminal-ab/images/sdcard-ab.img \
  of=/dev/sdc bs=4M status=progress conv=fsync
```

Use `/dev/sdc`, not `/dev/sdc1`. Wait for successful completion before disconnecting
the reader. No build script flashes a host block device automatically.

Return the reader to reTerminal's USB port and boot normally. The GPIO serial
console is 115200 baud, 8N1, no flow control. First startup can take longer while
Data grows; allow preparation to finish before resetting the unit.

## First boot and full-card Data expansion

Factory GPT layout:

| Index | Role | Initial capacity | Contents |
|---|---|---|---|
| 1 | Selector | 32 MiB | `autoboot.txt`, firmware discovery files |
| 2 | Boot A | 128 MiB | Kernel, DTB, overlays, firmware, A cmdline |
| 3 | Boot B | 128 MiB | Matching B boot assets and cmdline |
| 4 | Root A | 768 MiB | Complete ext4 rootfs; currently a 512 MiB filesystem |
| 5 | Root B | 768 MiB | Complete matching rootfs |
| 6 | Data | 4 GiB, then remaining card space | Persistent state and update staging |

Fixed GPT PARTUUIDs end in `000000000001` through `000000000006` under
`67b6d541-1883-4ac4-a501-`. Boot A selects Root A's PARTUUID; Boot B selects Root B's.
Boot/root capacities remain exact. Data is checked as at least 4 GiB. Changing
slot order, identifiers or boot/root capacities requires a new layout/profile.
Duplicated filesystem UUIDs are not used for selection.

Only the factory Data filesystem carries `.reterminal-factory-grow-v1`. During
initial normal Boot A, before persistence binds or application startup, preparation:

1. Validates all six GPT entries and saves
   `/data/ab/factory-partitions-before.json`.
2. Relocates the backup GPT to the physical card end and enlarges only partition 6,
   preserving its start/identity and all boot/root entries.
3. Updates only partition 6 in the kernel using `partx`, then grows mounted ext4
   using `resize2fs`. No formatting or shrinking occurs.
4. Records `/data/ab/factory-growth.json`, flushes writes and removes the marker
   after success. A retained marker allows retry; growth requires slot A, no trial
   and no update state. Preparation has a ten-minute deadline.

On the tested 32 GB card, partition 6 is `30001315328` bytes. `df -h` reports a
27.4G filesystem, initially about 26.2G available; partition size, filesystem size
and available space differ because of ext4 overhead and reserved blocks.

After login as root, run:

```sh
cat /etc/reterminal-ab/version
cat /data/ab/factory-growth.json
reterminal-update status
lsblk
df -h /data
systemctl --failed
systemctl is-active reterminal-ab-prepare reterminal-ab lvgl-console
```

Expected: slot `a`, `trial: false`, `state: {}`, Data expanded, no failed services.
Preparation remains `active`; the successful one-shot `reterminal-ab` unit can
show `inactive`; LVGL should be `active`. Verify the actual display and touch too.
Then perform an ordinary reboot and repeat status/Data checks.

A PC may report that the backup GPT is not at the physical disk end immediately
after writing the smaller image. Factory growth corrects that on first boot. The
warning alone is not evidence of a failed flash or the USB/GPT firmware bug.

Routine SWUs contain no Data image or growth marker. They never expand existing
4 GiB installations. To reprovision such a card, back up Data and flash a new
factory image. Do not add the factory marker manually to a deployed installation.
Any separate in-place resize migration needs both slots running controllers that
accept expanded Data; old dev-4/dev-5 controllers require exactly 4 GiB and are not
suitable rollback targets on an expanded card.

## Build and sign a routine release on the PC

Use a new version for each release. The example below uses `dev-12` after the tested
`dev-11` release. For a normal incremental release, do not reload the defconfig or
rebuild the baseline. Reuse `output-reterminal-ab` and the existing signing key.

First change application sources, packages, kernel configuration or overlays.
Shared Data formats must remain compatible with the previous release. Refresh
affected local packages explicitly when necessary. For LVGL, a conservative refresh
before the complete build is:

```sh
make -C buildroot O="$PWD/output-reterminal-ab" lvgl-console-local-dirclean
```

Package option changes can require `<package>-reconfigure`; kernel configuration
changes can require `linux-reconfigure`. A new toolchain should use a fresh output.
An overlay-only or version-only release normally needs just the full build below.

```sh
AB_RELEASE_VERSION=dev-12 \
AB_VERIFY_KEY="$PWD/ab-development-public.pem" \
  make -C buildroot O="$PWD/output-reterminal-ab" -j4
```

Only after the build succeeds, sign its payloads using exactly the same version:

```sh
mkdir -p releases/dev-12
python3 rpi-extree/board/reterminal-ab/package.py \
  --images output-reterminal-ab/images \
  --version dev-12 \
  --key "$PWD/ab-development-private.pem" \
  --output releases/dev-12/dev-12.swu
sha256sum releases/dev-12/dev-12.swu > releases/dev-12/SHA256SUMS
```

Do not edit `release-version` to relabel an old rootfs: the embedded
`/etc/reterminal-ab/version` must match. The package script checks the build marker;
trial health checks verify the candidate's embedded release after boot.

Each bundle contains signed `sw-description`, separately signed release metadata,
SHA-256 hashes, both slot-specific boot images and one complete rootfs. SWUpdate
selections pair Boot A with Root A or Boot B with Root B. The target chooses the
inactive pair automatically; operators do not select a slot in the bundle command.
The current uncompressed bundle is approximately 768 MiB.

Archive the `.swu`, its checksum, version, source revisions/configuration and a
known-good factory recovery image. The next build replaces files in `images/`.
Keep the previous release bootable and avoid destructive shared-data migrations
throughout the rollback window.

## Copy and deploy on reTerminal

From the PC, replace `<IP>` with the target address:

```sh
scp releases/dev-12/dev-12.swu root@<IP>:/data/dev-12.swu
```

A second USB drive is an alternative transfer method. Keep cloned boot media
removed. The target must have more than 2300 MiB free on Data for authenticated
payload staging and the private SWUpdate snapshot:

```sh
df -h /data
ls -lh /data/*.swu
```

If needed, remove only obsolete `.swu` files that are archived on the PC. Removing
an old bundle does not remove an installed slot or its rollback release. Do not
delete `/data/persist`, update records or growth records to make space. Installation
checks space before slot writes. Payloads are staged/hashed in bounded chunks on
Data rather than retaining the whole release in RAM.

On reTerminal as root, inspect current state and create a persistence sentinel
once (keep its existing contents for subsequent tests):

```sh
reterminal-update status
test -f /data/ab-test-sentinel || printf 'expanded-data-survives\n' > /data/ab-test-sentinel
cat /data/ab-test-sentinel
sync
reterminal-update install /data/dev-12.swu
```

Before installing, require `trial: false` and no `pending`, `trial` or `committing`
transaction. From A, installation writes B; from B, it writes A. The installer
serializes installation/confirmation, verifies profile/layout and signatures,
checks same-disk GUIDs, partition capacities, firmware boot partition/transport,
running root and unmounted inactive targets. A canonical manifest restricts device
paths to controller-created aliases for that inactive pair. Both payload writes
are flushed and read back before recording pending state and requesting:

```sh
systemctl reboot --reboot-argument='0 tryboot'
```

The controller issues that command automatically after a successful install. Do
not invoke SWUpdate directly, mount the inactive targets concurrently, or manually
change selector/state files during installation. Standalone SWUpdate daemon,
socket and USB-auto-install services are masked; IPC is in a root-only directory.

## Verify the trial, commit, and ordinary reboot

After the automatic reboot, log in and run:

```sh
reterminal-update status
cat /etc/reterminal-ab/version
cat /data/ab-test-sentinel
df -h /data
systemctl --failed
```

Wait for `phase: committed` before the ordinary reboot. Startup checks the candidate
slot/release and Data, and requires critical services plus a fresh LVGL PID
heartbeat produced after display/touch/UI initialization. The UI loop refreshes
the heartbeat; the readiness deadline is 60 seconds. Application activity still
needs functional display/touch checks on hardware.

For example, the first update from factory A to release dev-7 produced:

```json
{
  "slot": "b",
  "trial": true,
  "state": {
    "layout": 1,
    "phase": "committed",
    "previous": "a",
    "profile": "reterminal-cm4-lvgl-v1",
    "target": "b",
    "version": "dev-7"
  }
}
```

The state also contains a timestamp. `trial: true` remains for that firmware boot
even after commit; it does not mean confirmation failed. Only after `committed`:

```sh
systemctl reboot
```

After login, repeat status, release, sentinel, Data and failed-service checks.
Expected: same new slot/version, `trial: false`, `phase: committed`, preserved
sentinel, unchanged Data capacity, no failed services. This verifies the committed
selector is used on a normal boot. Perform this reboot before the next update.

For the reverse direction, build/sign a new version using the same commands with
all version strings changed together, then install while running normal B. Expected
trial target and committed default are A. Never reflash the factory image for this
routine reverse-direction test.

## Persistent data, state, and failure handling

Data is `/data`; selector is `/selector`. Before application/SSH services,
`/etc/default`, `/etc/ssh` and `/var/lib` are initialized once on Data and bound onto
those paths. These preserve application settings, SSH host keys and service state.
Repeated mounts in `df` share the same Data filesystem; they do not consume
separate capacities. Mount checks verify device number, filesystem type, mount
root and destination so legitimate binds are accepted and foreign mounts rejected.

Updated defaults are not automatically merged into existing persistent settings.
Keep schemas compatible with the previous release and defer destructive migrations.
Use `/data` for additional persistent application data and identity. `/root`,
arbitrary `/etc` files, logs and systemd machine ID are not currently persisted.
Root is writable to accommodate the profile's configuration conventions; updates
replace all slot-local changes. The obsolete baseline `/boot` fstab entry is
removed only for the A/B profile.

Inspect diagnostics promptly; the system journal is not guaranteed across resets:

```sh
journalctl -b -u reterminal-ab-prepare -u reterminal-ab -u reterminal-ab-failure
journalctl -b -u lvgl-console
cat /data/ab/state.json
cat /data/ab/events.jsonl
```

Factory `state: {}` is normal; `state.json` may not exist until an update starts.
States include `installing`, `pending`, `trial`, `committing`, `committed`, `failed`
and `fallback`. A partial/failed installation leaves the inactive pair unusable
until a complete reinstall succeeds. It never intentionally changes the default
selector. A normal boot into the old default recognizes an abandoned trial and
records fallback. Commit stages and fsyncs selector contents, renames, flushes the
filesystem and reads back the result. Recovery across commit/state interruption
is designed to be replayable; FAT durability and real power cuts remain test gates.

If installation records `pending` but the reboot request failed, inspect the
record and use the same tryboot reboot argument; do not clear pending manually.
Service failures during a trial request an ordinary reset for firmware fallback.
Failures on normal boots leave the console available and dependent services
failed for diagnosis. The BCM2835/systemd watchdog covers only stages where it is
actually armed; firmware/kernel hangs and failures before root mount require
separate coverage measurements. USB disconnect and power-cut behavior remain
hardware validation targets.

## Troubleshooting and local recovery

| Symptom | Check / action |
|---|---|
| Public key file not found during post-build | Use `AB_VERIFY_KEY="$PWD/ab-development-public.pem"` from workspace root |
| Missing `partx` or `resize2fs` | Reload A/B defconfig; run `util-linux-reconfigure e2fsprogs-reconfigure`; then the complete build |
| Insufficient Data staging space | Check `df -h /data`; archive/remove obsolete `.swu` files only |
| Blank screen before Linux | Capture GPIO serial from power-on; check USB boot mode, EEPROM and fixed `start4.elf` pair |
| Startup service failure | Read the journal/traceback; verify root/slot/firmware and persistence mounts |
| FAT not properly unmounted | Often follows reset/power loss; repair only offline while unmounted, after preserving evidence |

For diagnosis of an older reboot-looping image, append these to the selected
boot partition's **single-line** `cmdline.txt` while the card is attached to the PC:

```text
systemd.mask=reterminal-ab-prepare.service systemd.mask=reterminal-ab.service
```

Boot A is partition 2; Boot B is partition 3. The masks permit console diagnosis
but disable required A/B startup handling; do not install updates in this mode.
Remove the masks before normal operation, or reprovision a corrected factory image.

For manual rollback, power off, attach the card to a maintenance PC, save Data's
update records and mount selector partition 1. Verify which pair is known-good;
never select a partially installed inactive pair. To choose A, write `autoboot.txt`:

```ini
[all]
tryboot_a_b=1
boot_partition=2
[tryboot]
boot_partition=3
```

To choose B, exchange 2 and 3. Flush and unmount before removing the card. Manual
selector editing after a committed release does not create a new trial record;
verify the actual booted release and status. Interrupted transactions may need
separate diagnosis rather than blindly editing state to suppress errors.

If selector FAT is damaged, restore partition 1 from the saved `selector.vfat` and
select the known-good pair. If both pairs are unusable, back up Data and reflash a
known-good factory image. Any loss of all boot paths during commit power-cut tests
blocks deployment. EEPROM recovery is a separate USB recovery procedure and is
never part of a `.swu` release.

## EEPROM prerequisite and diagnostics

The old 2022-08-02 EEPROM predates `[tryboot]`/`tryboot_a_b` support added in October
2022. The tested unit was updated separately with Raspberry Pi usbboot recovery.
Its observed configuration is:

```ini
[all]
BOOT_UART=1
WAKE_ON_GPIO=0
POWER_OFF_ON_HALT=1
BOOT_ORDER=0xf15
ENABLE_SELF_UPDATE=1
```

`BOOT_ORDER` is read right to left: USB 2.0, then SD/eMMC, then repeat. Keep one
entry per setting. Both reTerminal profiles include `vcgencmd`; collect:

```sh
vcgencmd bootloader_version
vcgencmd bootloader_config
vcgencmd version
```

For a different unit needing EEPROM maintenance, use the
[official CM4 USB recovery instructions](https://github.com/raspberrypi/usbboot/tree/master/recovery)
and [Seeed's switch/access diagrams](https://wiki.seeedstudio.com/reTerminal/).
The boot switch is inside the original reTerminal, under the heatsink. Disconnect
power before changing it and restore normal mode after recovery. Preserve the
unit's configuration and record the resulting EEPROM version. Updating EEPROM is
separate from building or flashing this card image.

## Validation record and remaining release gates

Hardware observations reported during 2026-11-06/07:

| Check | Result |
|---|---|
| Baseline boot through USB microSD reader; vcgencmd | Passed |
| EEPROM recovery and UART diagnostics | Passed; version/config recorded above |
| GPT + autoboot selection of Boot A over USB | Passed with fixed firmware pair |
| Factory A boot, persistence preparation, LVGL service, normal reboot | Passed; no failed services reported |
| dev-3 A -> dev-4 B trial, commit, ordinary reboot | Passed on original 4 GiB Data; sentinel preserved |
| dev-5 reverse-direction test | Build/deploy instructions provided; successful completion not recorded |
| dev-6 factory Data growth on 32 GB card | Passed: partition `30001315328` bytes, filesystem 27.4G |
| Normal reboot after expansion | Passed; capacity retained, A normal boot, empty update state |
| Expanded-card A -> dev-7 B trial and commit | Passed; release, sentinel and Data size verified |
| Ordinary reboot after dev-7 commit | Operator reported all good |
| Clean Buildroot update to dev-8, B -> A | Committed on A; subsequent dev-9 install required completion of the ordinary reboot |
| API bootstrap dev-9, A -> B | Committed, normal B boot; API client present, but Python `_ssl` missing |
| TLS correction dev-10, B -> A | Committed, normal A boot; Python reports OpenSSL 3.6.5 |
| Host baseline/API test suites | Operator ran all 17 + 11 tests successfully, including real sockets |
| Manual lab API workflow | Check, explicit download, then expected `lab_install_disabled`; no real installation |
| Device -> desk HTTPS health | Passed with custom CA and IP verification at `192.168.178.41:9443` |
| API dev-10 A -> dev-11 B | Signed offer, separate accepted download/install, trial and commit passed |
| Ordinary reboot after API dev-11 commit | Passed: B, dev-11, `trial: false`, phase committed |
| Persistence during API update | Sentinel `expanded-data-survives` retained; Data still 27.4G |

Host/build checks: both defconfigs resolve; pinned firmware hash checking,
extraction and image installation passed. Factory GPT/cmdline/firmware inspections
passed. The latest 17 controller/bundle/post-build/growth tests passed, including
real RSA signatures, tampering, clone/transport/mount checks, persistence binds,
Data-size checks and interrupted-growth replay. Sparse 32 GB GPT expansion and
regular-file ext4 expansion/read-only fsck passed. The earlier LVGL native build
and all nine CTest tests passed. Initial download/DNS blockers were subsequently
overcome and complete factory/bundle builds have been exercised on the device.

Reproduce host checks from workspace root:

```sh
python3 rpi-extree/board/reterminal-ab/test_ab.py
cmake -S lvgl-console -B /tmp/lvgl-ab-build -DLVGL_CONSOLE_TESTS=ON \
  -DLVGL_CONSOLE_ASSET_DIR="$PWD/lvgl-console/assets"
cmake --build /tmp/lvgl-ab-build -j4
ctest --test-dir /tmp/lvgl-ab-build --output-on-failure
```

These successes do not establish unattended rollout readiness. Still required:

- Exercise the remote/API B -> A direction; successful local CLI B -> A is now recorded above.
- On-target wrong-profile and tampered-bundle rejection without activation.
- Data/settings/key survival during actual fallback, not just successful commits.
- Unbootable candidate kernel, root-mount failure, hung trial and failed LVGL
  readiness; measure watchdog coverage at each boot stage.
- Power cuts during boot/root writes, after installation before trial reboot,
  repeatedly during selector commit, and during initial Data growth. Record observed
  slot/release, selector and update state after each reset.
- Verify local recovery and demonstrate that no tested commit interruption loses
  every boot path. Keep fleet distribution gated on those results.

References: [Raspberry Pi autoboot/tryboot](https://www.raspberrypi.com/documentation/computers/config_txt.html#autoboot-txt),
[SWUpdate best practices](https://sbabic.github.io/swupdate/swupdate-best-practise.html),
[Buildroot manual](https://buildroot.org/downloads/manual/manual.html).

## Remote-update API: stage 1 validated, LVGL implementation added

The original local CLI remains the independent deployment baseline. The opt-in,
root-only Unix-socket service supports signed remote release checks, accepted
downloads and separately accepted installation through that same CLI. It is not
enabled globally and exposes no web listener. Configured LVGL builds request the
service through a Wants dependency. The Settings integration below awaits device
validation; browser integration remains a separate future stage.

See [API v1](API.md), the [service/client/publishing guide](api/README.md), and the
[local HTTPS hosting guide](api/HTTPS-HOST.md). The operator ran all 17 baseline and
11 API tests on the PC, then completed a real HTTPS/API dev-10 -> dev-11 update,
trial commit and ordinary reboot. The Data sentinel and expanded capacity survived.
The restricted workspace's socket tests remain skipped there; actual host/device
results are recorded separately rather than inferred from those skipped tests.

When adding the API to an older build, reload the A/B defconfig and use
`python3-dirclean` before the complete build. Dev-9 showed that an existing Python
build could retain `_ssl=n/a` despite `BR2_PACKAGE_PYTHON3_SSL=y`; dev-10 corrected
that. The post-build hook now refuses an image without the `_ssl` shared extension.
Normal local CLI updates remain available if the API service is stopped or the
remote server is unavailable.

## LVGL Settings integration

The System update panel is implemented using the local API: Check for updates,
release-specific download consent, separate install/restart consent, and local
status/progress polling. SWUpdate per-step progress is observed read-only by the
service. The standalone CLI remains the installation baseline. Build instructions
and the spare-card acceptance checklist are in
[the LVGL-stage guide](api/README.md#stage-2-implementation-lvgl-settings-client).
No browser updater was added. The operator has now reported the LVGL update
flow working, including the corrected confirmation layout. See the validation
record below; power-cut and failure-path acceptance remains separate.


## One-command development release

From the workspace root, build, sign and publish the next release with:

```sh
rpi-extree/board/reterminal-ab/release.sh dev-14
```

The number is also the signed metadata sequence. Use a new number greater than
that in the existing `update-host/www/latest.json`. The script uses the configured
`output-reterminal-ab`, development signing/verification keys in the workspace,
and the existing HTTPS host at `https://192.168.178.41:9443`. It refreshes the local
LVGL package using `lvgl-console-local-dirclean` so UI source edits are included,
builds the image, packages/signs `releases/dev-14/dev-14.swu`, creates its
`SHA256SUMS`, verifies/signs the offer, publishes the complete bundle, then atomically
replaces `latest.json`. It preserves the existing Buildroot configuration.

Do not run alongside another build using the same output directory. The script
serializes other invocations of itself, refuses existing release artifacts and
checks the signing key pair and increasing sequence before building. On failure,
the previous offer remains published; inspect any partial release artifacts before
retrying, or use a fresh version. This does not imply power-loss durability of
publication. Keep the existing HTTPS server running; its files update without a
restart. On reTerminal use Settings → System update → Check for updates, followed
by the separate download and installation confirmations.

To supply release notes or change build parallelism:

```sh
RELEASE_NOTES='Fix update confirmation button clipping' RELEASE_JOBS=4 \
  rpi-extree/board/reterminal-ab/release.sh dev-14
```

Run `release.sh --help` for path, key, URL and expiry overrides. The script never
starts the server, changes UFW, installs on a device, flashes a card or updates
EEPROM. Configuration/dependency changes requiring a defconfig reload or package
clean beyond LVGL remain explicit preparation steps. Initial factory flashing is
still the separate procedure above. The wrapper itself has not built or published
a release during implementation.


## LVGL update operation and validation record

The Settings System update section uses borderless containers, preserves button
styling and text, and keeps confirmation buttons below a scrollable description.
**Cancel/Later is left; Download/Install and restart/Restart is right.** Download
and installation each require their own explicit acceptance of the reviewed offer.
Opening Settings polls local status only; Check for updates requests the remote
signed offer. Download progress and optional SWUpdate per-image progress are shown;
verification/readback phases without measured progress do not invent a percentage.

After installation, a committed trial offers **Finish update**. Its confirmation
provides **Restart** for an ordinary reboot and **Later** to continue using the
device. Later leaves Finish update available. New installations remain blocked
until a normal boot reports `trial: false`. The API accepts the restart only after
fresh status confirms the committed version and slot match the running system.

The operator reported successful UI operation after the layout correction and
subsequently reported the lock-race correction working. The observed dev-15 status
was slot B, committed, `trial: false`. A dev-16 attempt had failed at preflight
(`stage: verifying_bundle`) with `device_unavailable`, before slot writes. API
polling and worker preflight now serialize baseline status calls using the engine
lock, preventing those calls from racing each other for the CLI's process lock.
The UI can retry a failed job with a retained download when fresh device status
permits it; the backend repeats verification and safety checks.

If using an older API image affected by that race, stop its polling and install
the already downloaded bundle through the independent CLI:

```sh
systemctl stop reterminal-update-api
reterminal-update status
reterminal-update install /data/update-api/download.swu
```

Use this only after reviewing the offered release and accepting installation.
Do not delete `/run/reterminal-update.lock`; the file's presence is normal and
unlinking it can defeat serialization. For diagnosis, collect baseline/API status
and `journalctl -u reterminal-update-api -b --no-pager`. A baseline failure can
also mean invalid partition/mount evidence; inspect its actual traceback rather
than assuming every error is contention.

Current host checks: 11 native LVGL tests passed; 17 baseline tests passed; API
suite has 13 tests with one Unix-socket integration test skipped in the restricted
workspace; five progress decoder tests passed. These are separate from operator
hardware reports. Exact post-fix release IDs and timing were not supplied in the
latest report. Adverse-network, rejection, rollback, watchdog coverage and
power-cut tests remain deployment gates, not established by the happy path.


## Credential handling and repository audit

Keep release signing keys, TLS private keys and the initialized `update-host/`
outside `rpi-extree`, as in the workspace layout above. Targets receive only
release verification trust and the public HTTPS CA certificate. The release
wrapper takes key paths; it never copies private keys into image payloads or the
public document root. Ignore rules now cover common update-key names, PKCS#12
containers and repository-local hosting/release directories. Ignore rules do not
remove files already tracked by Git.

The current changed/untracked updater files were scanned for private-key and
common provider-token markers with no findings. This is a scoped check, not a
claim that the whole existing repository is credential-free: an audit also found
14 pre-existing private-key/PKCS#12 files under `fs_overlay/fs_edgemap/` and
credential literals in other profiles. Those unrelated inputs remain unchanged
pending a separate cleanup decision. Removing current files would not erase
historical Git copies; any keys used operationally require rotation, with history
cleanup coordinated separately. No secret values are reproduced in this guide.
