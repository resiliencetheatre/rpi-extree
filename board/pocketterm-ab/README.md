# PocketTerm Raspberry Pi 4 A/B updates

For the complete local development, kernel refresh, public SWU and factory-image
workflow, read [Development and release lifecycle](DEVELOPMENT.md) first.

Opt-in profile: `raspberrypi4_pocketterm_ab_defconfig`. The existing
`raspberrypi4_pocketterm_defconfig` stays single-slot and unchanged.
Source port of `../reterminal-ab`: signed whole-system SWUpdate, native tryboot,
health confirmation, persistent Data growth, local CLI, LVGL update panel and
optional verified HTTPS offers. The initial source port did not run builds or
hardware tests; subsequent operator observations are recorded below. Use a spare microSD; native SD and USB reader boot
are separate hardware validation combinations. EEPROM updates are separate.

## Workspace and revisions

Run commands from the workspace root `/home/tech/laboratory/rpi4console`.
Buildroot: `buildroot`, revision `261a30b253068338d8c4f1548828eddef754ffe0`;
external tree: `rpi-extree`, name `rpi`, starting revision
`93da9d68ccc85459a7bb5f228f7d86d1f78e38db`. Both were clean before this port.
Application: `lvgl-console`, local package `lvgl-console-local`; manually maintained
sources are copied by Buildroot only when explicitly refreshed.
Toolchain: Buildroot C++ toolchain, AArch64 Cortex A72 as in the baseline.
Kernel: `0b41724521c9adf5399409d02aece6c1df0a4432`, Pi 4 Model B DTB.
SWUpdate `2026.05.1`, genimage `20`, base firmware
`063bcab6c8a90efb0d19f69d88cbbc7ec79cab68`, matched tryboot start4/fixup4
firmware `ab5c7f86283ceb58b7adb269cae1d16092a31bf6`.
Record the actual EEPROM version, firmware, card, reader/controller, boot topology,
display and input before hardware acceptance. The initial source port alone did
not establish them.

## Build commands (operator runs)

Choose external absolute key paths. Keep private signing and TLS keys outside
rpi-extree. Reuse the signing trust across releases; never regenerate it as part
of a routine release. The post-build hook embeds only the public RSA PEM.
Use fresh, separate output directories; preserve existing output/configuration
and never build concurrently against an output directory.

```sh
make -C buildroot O="$PWD/output-pocketterm-ab" \
  BR2_EXTERNAL="$PWD/rpi-extree" raspberrypi4_pocketterm_ab_defconfig
AB_RELEASE_VERSION=dev-1 AB_VERIFY_KEY=/absolute/path/public.pem \
  make -C buildroot O="$PWD/output-pocketterm-ab" -j4
```

Optional baseline regression build:

```sh
make -C buildroot O="$PWD/output-pocketterm-baseline" \
  BR2_EXTERNAL="$PWD/rpi-extree" raspberrypi4_pocketterm_defconfig
make -C buildroot O="$PWD/output-pocketterm-baseline" -j4
```

Factory artifact: `output-pocketterm-ab/images/sdcard-ab.img`.
Inspect `genimage-ab.cfg`, `release-version`, `release-profile`, GPT and both boot
cmdlines after building. Boot A roots partition 4; Boot B roots partition 5.
Both factory slots contain the same release. Do not use a single-slot image.

| GPT index | Role | Capacity |
|---|---|---|
| 1 | Selector FAT | 32 MiB |
| 2 | Boot A FAT | 128 MiB |
| 3 | Boot B FAT | 128 MiB |
| 4 | Root A ext4 | 768 MiB (512 MiB filesystem) |
| 5 | Root B ext4 | 768 MiB (512 MiB filesystem) |
| 6 | Data ext4 | 4 GiB, grows to card end on first normal A boot |

GPT includes a protective MBR. Same partition scheme/capacities as reTerminal,
but independent PARTUUIDs `b9a50213-354e-49fd-a402-000000000001` through
`000000000006`. Profile `pocketterm-rpi4-lvgl-v1`, layout `1` within that profile.
reTerminal bundles and cloned/ambiguous identities are rejected.
Selector starts with `tryboot_a_b=1`, normal partition 2, trial partition 3.

## Provisioning and recovery

Back up existing data first. Identify the spare whole-card device using
`lsblk -o NAME,SIZE,MODEL,TRAN,MOUNTPOINTS`, unmount its partitions, and only after
explicitly identifying the destination use an operator-run disk writer to write
`sdcard-ab.img` to the whole card. This replaces GPT and Data. No script flashes
media. Single-slot cards require offline reprovisioning plus selective restore;
a routine SWU does not migrate their partition table.

On target:

```sh
pocketterm-update status
cat /etc/pocketterm-ab/version
cat /data/ab/factory-growth.json
systemctl --failed
journalctl -b -u pocketterm-ab-prepare -u pocketterm-ab -u lvgl-console
```

Persistence binds `/etc/default`, `/etc/ssh`, `/var/lib` onto `/data/persist`.
Additional persistent data belongs on `/data`. Slot-local edits are replaced by
updates; shared formats must stay compatible with the previous release.
Health requires active LVGL and udpptt plus a fresh PID heartbeat at
`/run/lvgl-ab-ready`, produced after app display/input/UI initialization (60-second
deadline). Confirm real display/input operation. systemd runtime watchdog is 15s;
pre-root and kernel-hang coverage still needs measurement.

Routine release (refresh other changed packages as appropriate):

```sh
make -C buildroot O="$PWD/output-pocketterm-ab" lvgl-console-local-dirclean
AB_RELEASE_VERSION=dev-2 AB_VERIFY_KEY=/absolute/path/public.pem \
  make -C buildroot O="$PWD/output-pocketterm-ab" -j4
mkdir -p pocketterm-releases/dev-2
python3 rpi-extree/board/pocketterm-ab/package.py \
  --images "$PWD/output-pocketterm-ab/images" --version dev-2 \
  --key /absolute/path/private.pem --output "$PWD/pocketterm-releases/dev-2/dev-2.swu"
```

Copy the bundle to `/data` on target, inspect status, then explicitly install:

```sh
pocketterm-update install /data/dev-2.swu
```

This verifies signatures, profile/layout, partitions, mounts and payloads; writes
only the inactive boot/root pair; verifies readback; then requests tryboot.
Keep at least 2300 MiB free for staging. Never invoke SWUpdate directly.
Wait for `phase: committed`, then ordinary `systemctl reboot`; verify the same
release/slot with `trial: false` before another update. Failed or interrupted
writes leave the inactive slot unusable until a complete successful install.
Inspect `/data/ab/state.json` and `/data/ab/events.jsonl` for outcomes.

For manual fallback, shut down and edit the selector FAT's `autoboot.txt` offline:
normal A is partition 2 with trial 3; normal B is partition 3 with trial 2.
Keep `[all]`, `tryboot_a_b=1` and `[tryboot]`. Select only a known-good previous
slot; preserve Data and records. If no boot path works, back up Data offline and
reprovision from the archived known-good factory image. FAT commit durability
requires real power-cut validation.

## Validation and handoff

Source tests: controller 17, API 13 (one socket skip), HTTPS host 5 (one socket
skip), progress 5. These are source checks, not physical acceptance.

Subsequent operator observations in this session:

- Pi 4 EEPROM 2021-04-29 booted B despite selector A and blocked factory growth.
- EEPROM 2026-10-30, revision `13c4219f16dbe58c5b9946086b474baf572512bb`,
  produced normal A and working LVGL startup.
- Device status reported dev-5 committed on A with `trial: false`.
- Public dev-6 metadata was accepted over HTTPS; later dev-8 public publication
  completed, and the operator built the dev-8 public factory archive.
- A dev-7→dev-8 install failed before writes at the controller lock. The API race
  was fixed and the temporary API replacement started successfully; a successful
  retry was not reported in this record.

These observations do not establish power-cut/fallback coverage or a validated
minimum EEPROM version. Media topology, complete image inspection and remaining
physical results must be recorded explicitly.
Before deployment test A→B and B→A, wrong-profile/tampered bundles, Data survival,
ordinary reboot after commit, unbootable kernel, root-mount failure, hung trial,
failed LVGL readiness, power cuts during both writes, before reboot and repeatedly
during selector commit. Confirm tryboot reaches firmware and GPT boots on the
actual medium. Loss of all boot paths blocks deployment.

See [HTTPS/API setup](api/README.md) and [API contract](API.md).
Suggested rpi-extree commit: `Add opt-in PocketTerm Pi 4 signed A/B update profile`.
No other repository is changed. Legacy credentials elsewhere in the external tree
are outside this port; no claim is made that the entire tree is secret-free.

## Preconfigured public factory image

Use the separate `raspberrypi4_pocketterm_public_defconfig` for downloadable
factory images. It is the same PocketTerm A/B hardware/layout contract, with
`public-overlay` added after the development overlay. It provisions:

- `https://resilience-theatre.eu/pocketterm/latest.json` as the update source;
- public HTTPS certificate validation using the system CA store (no lab CA);
- `UDPPTT_SERVER=91.98.237.100` in `/etc/default/udpptt`;
- the externally supplied RSA public verification key through the A/B hook.

The remaining application defaults, including audio selection, PTT shared-room
key and relay settings, remain the development defaults. Configure those for the
intended deployment. The image embeds no private release signing or TLS key.
A device accepts only releases signed by the key corresponding to its embedded
public key. Use the same trust key as `release-public.sh`; do not generate a new
key per factory image. Development and production trust should remain separate
when deliberately setting up a production channel.

From the workspace root, build a fresh version (example `dev-7`; choose your
actual baseline version):

```sh
AB_VERIFY_KEY="$PWD/ab-development-public.pem" \
  rpi-extree/board/pocketterm-ab/build-public-image.sh dev-7
```

This command starts a full build when run by the operator. It uses the separate
`output-pocketterm-public`, initializes the public defconfig only for a nonexistent
output directory, checks an existing configuration without resetting it, refreshes
local LVGL and builds the complete image. It shares the release-wrapper lock;
manual builds must also stay clear of the selected output. A fresh output builds
its own toolchain and dependencies. Use `--help` for `PUBLIC_OUTPUT`,
`PUBLIC_IMAGES`, absolute workspace/key paths and job count overrides.

The download is:

```text
pocketterm-factory-images/dev-7/pocketterm-public-dev-7.img.xz
pocketterm-factory-images/dev-7/SHA256SUMS
```

Configuration/revision/status records are archived locally alongside it for
traceability. The wrapper validates generated defaults before compression, refuses
to overwrite a version directory, and never uploads, flashes or changes EEPROM.
On failure inspect the output and any partial archive before choosing a new
version. Public factory builds do not change `latest.json` or require incrementing
the public offer sequence; future SWU offers still need fresh increasing sequences.

To offer the image for download after your own inspection and spare-card test,
upload these two explicit files (substitute your built version):

```sh
rclone copyto --immutable \
  pocketterm-factory-images/dev-7/pocketterm-public-dev-7.img.xz \
  hetzner-web:public_html/pocketterm/pocketterm-public-dev-7.img.xz
rclone copyto --immutable pocketterm-factory-images/dev-7/SHA256SUMS \
  hetzner-web:public_html/pocketterm/pocketterm-public-dev-7.img.xz.SHA256SUMS
```

Distribute the versioned image URL and checksum. Flashing it replaces the whole
card, including Data; use an image writer that accepts `.img.xz`, or decompress
before writing the whole-card image. Require the validated 2026-10-30 Pi 4 EEPROM
revision `13c4219f16dbe58c5b9946086b474baf572512bb` or separately validated firmware;
EEPROM is outside this image and is not updated by flashing it.

On first normal Boot A, Data grows and `/etc/default` is initialized on Data,
including both public defaults. The local API starts alongside LVGL once its
configuration exists. Network access, DNS and a valid clock are required for
verified HTTPS. Open Settings → System update → Check for updates; a check never
automatically downloads or installs. This bootstraps public updates without
manually copying the lab CA or creating the API configuration.

These are initial defaults. Reflashing factory media initializes them anew;
installing an SWU on an existing device preserves its `/data/persist/etc/default`
settings, including its chosen update URL and PTT server. Switching existing lab
devices to the public source still requires editing their persistent configuration.
Source checks do not replace building/inspecting this new public image and testing
fresh-card boot, network/TLS, A→B/B→A updates, fallback and power cuts.
