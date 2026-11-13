# EdgeMap Lite Raspberry Pi 4 signed A/B updates

For everyday configuration, rebuilds, publication and serial-console updates,
use the [workflow cheat sheet](CHEATSHEET.md).

Start with [EEPROM preparation](EEPROM.md). It was the first implementation
artifact for this port. EEPROM recovery runs separately from the factory/SWU
flow and needs explicit operator authorization.

This opt-in profile derives from `raspberrypi4_edgemap_lite_defconfig` and reuses
the local PocketTerm Pi 4 controller, factory, signature and HTTPS mechanisms.
The baseline profile and overlay are unchanged. This is a source implementation;
no release build, image inspection, device install, EEPROM write or hardware
acceptance has been performed for EdgeMap.

## Workspace and scope

Discovered workspace: `/home/tech/laboratory/rpi4base`; instructions: its
`AGENTS.md` (no nested instruction files found). Buildroot revision:
`dc55155cbd8b2ca6f3344895944207014b69b969`; rpi-extree revision before port:
`b650b95da2229d66dca7367b5902212a13855fd4`, external name `rpi`. Both repository
worktrees were clean before this work. The workspace itself is not a Git repo.

| Setting | Value |
|---|---|
| Baseline | `rpi-extree/configs/raspberrypi4_edgemap_lite_defconfig` |
| A/B profile | `rpi-extree/configs/raspberrypi4_edgemap_lite_ab_defconfig` |
| Integration | `rpi-extree/board/edgemap-ab` |
| Baseline output | `WORKSPACE/output-edgemap-baseline` |
| A/B output | `WORKSPACE/output-edgemap-ab` |
| Profile / layout | `edgemap-lite-situation-rpi4-v1` / `1` |
| Release directory | `WORKSPACE/edgemap-releases` |
| Development private/public keys | `WORKSPACE/ab-development-private.pem`, `WORKSPACE/ab-development-public.pem` |
| Public channel | `https://resilience-theatre.eu/rpi4edgemap/latest.json` |

The supplied development RSA keys match. Only the public key is installed at
`/etc/edgemap-ab/public.pem`; signing stays on the host. Keys remain outside the
external-tree repository. This establishes signed updates under the installed
OS/key's trust, not secure boot. Use separate production trust deliberately.

Target: Pi 4 Model B, AArch64 Cortex A72, Buildroot default GCC 15.3.0 C++ toolchain,
systemd, baseline Waveshare kernel configuration and display settings.
Kernel: **6.18.62**, commit `ef71464298cd2dd89f6d190c08e812296240281e`,
matching the current rpi4console PocketTerm A/B source pin and inspected
`output-pocketterm-ab-clean-dev13` kernel release `6.18.62-v8`. Kernel headers
use the 6.18 series. EdgeMap retains its Waveshare configuration and A/B fragment;
this is the same source revision, with target-specific configuration.
Base rpi-firmware: `063bcab6c8a90efb0d19f69d88cbbc7ec79cab68`; matched tryboot
start4/fixup4 assets: `ab5c7f86283ceb58b7adb269cae1d16092a31bf6`.
SWUpdate: `2026.05.1`; genimage: `20`.
Application: package `situation-map`, Git source
`https://github.com/resiliencetheatre/map.git`, pinned to
`abc22dfe44045da76260eed166ed263d34d7230a`. It installs under `/opt/situation`
and serves HTTP on port 8080 using Python's standard library. The selected Lite
profile enables Situation map and optional TAK/Meshtastic adapters; the legacy
`edgemap` web package is disabled. No LVGL dependency is introduced.

Actual board revision, EEPROM version/configuration, display/input behavior,
media model, native SD versus USB reader/controller and boot topology remain
operator records to fill in. The controller accepts native SD and USB with
matching firmware boot-mode evidence; neither is physically validated here.
eMMC, SATA and NVMe are rejected. This port does not cover CM4 or Pi 5.

## Build and package (operator runs)

Use a fresh output for the 6.18 kernel/header transition; do not reuse an output
configured with 6.12 headers. No build is started automatically by this handoff.

From the workspace root, use fresh separate absolute outputs. These commands
start builds only when the operator runs them. Never reuse an output in use.

```sh
export WORKSPACE="$PWD"
export BASE_OUTPUT="$WORKSPACE/output-edgemap-baseline"
export AB_OUTPUT="$WORKSPACE/output-edgemap-ab-6.18.62"
export AB_VERIFY_KEY="$WORKSPACE/ab-development-public.pem"
export AB_SIGN_KEY="$WORKSPACE/ab-development-private.pem"
# Optional baseline regression build:
make -C "$WORKSPACE/buildroot" O="$BASE_OUTPUT" \
  BR2_EXTERNAL="$WORKSPACE/rpi-extree" raspberrypi4_edgemap_lite_defconfig
make -C "$WORKSPACE/buildroot" O="$BASE_OUTPUT" -j4
# New opt-in factory/release output:
make -C "$WORKSPACE/buildroot" O="$AB_OUTPUT" \
  BR2_EXTERNAL="$WORKSPACE/rpi-extree" raspberrypi4_edgemap_lite_ab_defconfig
AB_RELEASE_VERSION=dev-1 make -C "$WORKSPACE/buildroot" O="$AB_OUTPUT" -j4
mkdir -p "$WORKSPACE/edgemap-releases/dev-1"
python3 rpi-extree/board/edgemap-ab/package.py \
  --images "$AB_OUTPUT/images" --version dev-1 --key "$AB_SIGN_KEY" \
  --output "$WORKSPACE/edgemap-releases/dev-1/dev-1.swu"
PYTHONPATH="$WORKSPACE/rpi-extree/board/edgemap-ab" python3 -c \
  'import sys; from pathlib import Path; from remote_release import verify_bundle; verify_bundle(Path(sys.argv[1]), "dev-1", Path(sys.argv[2]))' \
  "$WORKSPACE/edgemap-releases/dev-1/dev-1.swu" "$AB_VERIFY_KEY"
```

Use unused version identifiers. The complete release includes boot files, kernel,
DTBs, complete rootfs, EdgeMap application and modules. Inspect the factory image
before any flash: `images/sdcard-ab.img`, `genimage-ab.cfg`, `release-profile`,
`release-version`, GPT protective MBR, partition identities/capacities and both
boot cmdlines. For example `sfdisk --json "$AB_OUTPUT/images/sdcard-ab.img"`
and `mdir -i "$AB_OUTPUT/images/boot-a.vfat" ::/`, then
`mtype -i "$AB_OUTPUT/images/boot-a.vfat" ::/cmdline.txt` (repeat for B).
Rootfs must fit its fixed slot; packaging rejects oversized payloads.

| GPT index | Role | Capacity |
|---|---|---|
| 1 | Selector FAT | 32 MiB |
| 2 / 3 | Boot A / B FAT | 128 MiB each |
| 4 / 5 | Root A / B ext4 | 3584 MiB each, 3000 MiB filesystem |
| 6 | Persistent Data ext4 | 16384 MiB, grows on first normal A boot |

Use spare media with at least 32 GB advertised capacity. Factory image length is
about 23.3 GiB. Data has room for a downloaded bundle and the 8200 MiB staging
reserve; application/map data reduces that room. GPT PARTUUIDs are
`e7d64be2-62b4-4c70-a134-000000000001` through `000000000006`, independent
of PocketTerm/reTerminal. Selector uses `tryboot_a_b=1`, normal partition 2,
trial partition 3. A roots partition 4, B roots partition 5. Both factory slots
contain the same release. Filesystem UUIDs are never used for slot selection.

For subsequent local releases, after a successful inspected initial factory build:

```sh
RELEASE_OUTPUT="$AB_OUTPUT" rpi-extree/board/edgemap-ab/release.sh dev-2
```

This checks the selected profile, existing artifacts and installed trust, matches
keys, takes a wrapper lock, refreshes `situation-map` with `situation-map-dirclean`, builds,
signs, hashes and verifies. It refuses an existing version directory. The app
is a pinned remote package, so changing upstream without changing its pin does
not select new source. Refresh other changed packages separately. Wrappers do
not coordinate manual make invocations. Overrides are listed by `--help`.

For existing output settings use `make -C buildroot O="$AB_OUTPUT" menuconfig`;
back up `.config` first. Save reviewed settings with
`make -C buildroot O="$AB_OUTPUT" savedefconfig BR2_DEFCONFIG="$WORKSPACE/rpi-extree/configs/raspberrypi4_edgemap_lite_ab_defconfig"`.
Do not reload a defconfig over intentional edits. Saved profiles do not update
existing outputs. Kernel source changes require `linux-dirclean` and refresh of
external modules, then a full image build; toolchain/ABI changes require a fresh
output. Preserve all existing outputs.

## Provisioning, persistence and health

Back up deployed data. Identify spare whole-card media with
`lsblk -o NAME,SIZE,MODEL,TRAN,MOUNTPOINTS`, unmount it and separately authorize
its destination before using an image writer. Factory flashing replaces the
partition table, both slots and Data. Single-slot media needs offline
reprovisioning and selective data restore; an SWU cannot migrate it.

The A/B hook removes obsolete `/opt/boot`, `/opt/data` and `/boot` fstab mounts;
masks legacy `partition`/`bootstrap` services; disables the single-slot
`create-partition*` and `init-edgemap.sh` commands. Do not run old bootstrap
scripts on A/B media. Factory Data growth uses the verified parent disk and
partition 6 only, with a replayable backup and opt-in marker. Routine updates
never rewrite GPT or Data.

Persistence initializes from factory defaults, then preserves `/etc/default`,
`/etc/ssh`, `/etc/apache2`, `/var/lib`, `/opt/data` and `/opt/situation/maps`.
Situation's SQLite database is `/var/lib/situation/situation.db`; PMTiles archives
belong in `/opt/situation/maps`. Application code stays slot-local. Do not persist
all of `/opt/situation`, as this would mask new application code. Shared formats
must remain compatible with the previous release during rollback.

Critical health requires verified Data/selector mounts, firmware/root agreement,
active `situation-map.service`, this slot's `python-front.py` and web index, and
`http://127.0.0.1:8080/api/status` reporting exactly
`{"status":"ok","service":"Situation"}` within 60 seconds. Apache, the old
EdgeMap engine, GPS, TAK and Meshtastic availability do not authorize commit.
Map rendering, maps availability and actual adapter operation still need physical
acceptance. Legacy EdgeMap engine/map support units are masked in the A/B image.
Situation server and adapter drop-ins require persistence preparation first.
The API starts after trial health. systemd watchdog is 15s, reboot watchdog 30s;
pre-root/kernel coverage still needs measurement on the actual board.

## Install and recover locally

```sh
edgemap-update status
cat /etc/edgemap-ab/version
cat /data/ab/factory-growth.json
journalctl -b -u edgemap-ab-prepare -u edgemap-ab -u situation-map
# Copy a real signed release into /data first:
edgemap-update install /data/dev-2.swu
```

Never invoke SWUpdate directly. The controller serializes installation, rejects
trial installs, cloned identities, wrong profile/layout, signatures, payload hashes,
invalid mounts, sizes and firmware evidence. It authenticates a fixed manifest,
writes only the inactive pair and checks readback before recording a pending
trial and requesting `systemctl reboot --reboot-argument='0 tryboot'`. Failed
writes preserve default selection; the inactive slot is unusable until a complete
successful install. SWUpdate's service/socket/USB activation paths are masked.

After health succeeds require `state.phase: committed`, then `systemctl reboot`
(or API `finish --accept`); require the same slot/version with `trial:false` before
another install. An ordinary boot into the previous slot records fallback.
Inspect `/data/ab/state.json` and `events.jsonl`. Health failure requests ordinary
reboot on a trial; normal-boot failures leave a diagnostic console.

Manual rollback: power off, mount selector FAT offline, preserve Data and records,
and select a known-good slot in `autoboot.txt`. For A use:

```ini
[all]
tryboot_a_b=1
boot_partition=2
[tryboot]
boot_partition=3
```

For B exchange 2 and 3. Back up Data offline and reflash an archived known-good
factory image if neither slot boots. Selector staging/flush/rename on FAT is
best-effort: loss of both boot paths in power-cut testing blocks deployment.

## Public HTTPS channel

The factory default points to `https://resilience-theatre.eu/rpi4edgemap/latest.json`
using the system public CA store and the selected RSA trust key. Existing devices
retain their persistent `/etc/default/edgemap-updates.json`; change that explicitly
to switch channels. Verified HTTPS needs working DNS, networking and a valid clock.
Post-build also requires Python's actual `_ssl` module. API uses a root-only Unix
socket, with no network listener and no automatic check/download/install.

```sh
edgemap-update-client check
edgemap-update-client wait
# Read offer.offer_id from status, then explicitly accept each step:
edgemap-update-client download --offer OFFER_ID --accept
edgemap-update-client wait
edgemap-update-client install --offer OFFER_ID --accept
# After committed trial, explicit normal reboot:
edgemap-update-client finish --accept
```

Offers bind profile/layout, version, increasing sequence, expiry, HTTPS URL,
length and SHA256. Install requires fresh preflight and verification. Progress
observation uses pinned SWUpdate little-endian ABI v2.0; unknown/missing progress
falls back to stage-only reporting and cannot authorize activation. Browser update
controls are a separate task; the local CLI works independently.

Public host setup/credentials are operator-owned. Do not copy PocketTerm hosting
accounts or TLS keys. Configure an existing rclone remote mapping to the web
folder serving `/rpi4edgemap`; it must support server-side moves. For an authorized
publication, the operator runs (replace the remote with the actual configured one):

```sh
RELEASE_OUTPUT="$AB_OUTPUT" RELEASE_REMOTE='YOUR_REMOTE:path/to/rpi4edgemap' \
  rpi-extree/board/edgemap-ab/release.sh --public dev-3
```

The wrapper builds/signs/verifies, uploads immutable bundle and checksum, verifies
public HTTPS bytes, then publishes signed `latest.json` last. N in dev-N is the
sequence and must exceed the previous offer. Pre-publication failure leaves the
previous offer; partial version artifacts must be inspected, retained for diagnosis
or explicitly removed before recovery. Never overwrite published bundles. Remote
moves/caching and concurrent external publishers require operator coordination.
The public URL could not be inspected through the browsing tool; its deployment
and current offer remain unverified. No hosting, release signing or publication
was performed in this port.

## Validation and remaining acceptance

Source checks performed: 22 controller/factory/health/persistence tests and 21
API/publication/progress tests (one Unix/HTTP socket integration test skipped by
sandbox restrictions); shell syntax; isolated Buildroot defconfig resolution in
`/tmp/edgemap-ab-config-check`; matching development key public components.
Signing tests use temporary fixture keys and tiny synthetic payloads, not a release.
Factory tests inspect generated configuration/staging with genimage mocked.
These checks do not establish a bootable disk image or target binary ABI.

Before deployment record actual hardware/firmware/media and test on spare media:
normal A/GPT/growth; A→B and B→A; tryboot reaching firmware; wrong-profile and
tampered bundles rejected without activation; persistent data survival; ordinary
reboot after commit; fallback; unbootable kernel; root-mount failure; hung trial;
failed Situation HTTP readiness; power loss during boot/root writes, before
trial reboot and repeatedly during selector commit. Record slot/release after
every reset. Retest EEPROM/boot firmware changes. Fleet rollout remains gated on
these physical results.

Credential audit found pre-existing EdgeMap private key files under the baseline
overlay (Apache/Taky and example application certificate directories). They are
unrelated to updater signing and were left unchanged. This tree and baseline
image must not be described as secret-free; operationally used exposed keys need
rotation and history handling agreed separately. No supplied updater private key
was copied into the repository or target.

Only rpi-extree changes. Suggested commit message:
`Add opt-in EdgeMap Lite Pi 4 signed SWUpdate and tryboot profile`.

The inherited GCC 13 selection was removed from the A/B profile because this
Buildroot revision treats it as legacy. The baseline profile is unchanged.
Use `olddefconfig` after removing that selection in an existing configuration;
do not bypass the BR2_LEGACY guard.

The A/B profile uses `python-pypubsub`, also selected by Meshtastic, rather
than the duplicate `python-pubsub` recipe. The former already supplies SCM
version metadata and Python/setuptools compatibility adjustments.

Situation-only correction: the original `edgemap_lite_defconfig` included legacy
EdgeMap. The operator's saved reduced A/B profile instead selects Situation map.
The A/B hook and health contract now follow that selection. Resume the existing
minimal build with the corrected hook; no configuration reload is required.
Use `http://DEVICE:8080/` to open Situation. Profile identity is
`edgemap-lite-situation-rpi4-v1` to reject earlier application-contract bundles.

## Unified local/public publication

Use `release.sh --public dev-N`, `release.sh --local dev-N`, or both flags to
build one bundle for both destinations. `release-public.sh` delegates to the
public mode for compatibility. A local Python HTTPS host and separate CA are
provided in `api/https_host.py`; see the [cheat sheet](CHEATSHEET.md#6-build-sign-and-publish-a-release-public-local-or-both)
for initialization, serving, device trust configuration and `--publish-only`.
Metadata is archived per channel under `edgemap-releases/dev-N/public` and
`local`, binding each URL to the same bundle. Both use the shared verified
publication engine. No servers are started and no credentials are initialized
by the release wrapper.

## Target single-command updater

New images install `/usr/sbin/update.sh`. Use `update.sh --remote` or
`update.sh --local`, review current/new versions and answer `y` to download,
install and trial-reboot. A persistent authorization allows the finish service
to request the final ordinary reboot only after the expected version/slot passes
health and is committed. `update.sh --status` reports status and progress.

Named source settings live in `/etc/default/edgemap-update-sources.json` on Data.
The remote default is the public channel; provision the local HTTPS URL and CA.
Both retain the same key and global replay protections. The API adds the root-only
`select-source` method (`{"source":"local"}` or `{"source":"remote"}`), rejected
while busy or in a trial. Selection is persistent and invalidates only the cached
offer/download, not replay history. The old CLI and API remain usable; automatic
final reboot is opt-in through the wrapper's exact-release authorization marker
`/data/ab/wrapper-reboot.json`. See the [cheat sheet](CHEATSHEET.md) for bootstrap,
source configuration, progress and both reboot stages. Physical testing of this
new wrapper and auto-finish unit remains pending; prior CLI success is not evidence
that this new flow has run on the board.

Wrapper source checks: 27 controller/factory/health/wrapper tests and 33
API/publication/source-selection tests (two socket integration skips). The
systemd verification tool was blocked by sandbox `SO_PASSCRED` restrictions;
actual startup ordering and the two-reboot wrapper flow still require spare-media
hardware tests. No build or publication was run for this wrapper change.
