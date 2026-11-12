# EdgeMap Lite / Situation A/B workflow cheat sheet

PC commands run in `/home/tech/laboratory/rpi4base`. Device commands run as root
on the Pi through SSH or serial. These are operator-run commands: documentation
changes never start a build, publication or device update.

## 1. Set the PC environment in every new terminal

```bash
cd /home/tech/laboratory/rpi4base
export WORKSPACE="$PWD"
export AB_OUTPUT="$WORKSPACE/output-edgemap-ab-6.18.62-lite-overlay"
export AB_PROFILE="$WORKSPACE/rpi-extree/configs/raspberrypi4_edgemap_lite_ab_defconfig"
export AB_VERIFY_KEY="$WORKSPACE/ab-development-public.pem"
export AB_SIGN_KEY="$WORKSPACE/ab-development-private.pem"
export RELEASE_OUTPUT="$AB_OUTPUT"
export RELEASE_BASE_URL="https://resilience-theatre.eu/rpi4edgemap"
export RELEASE_REMOTE="hetzner-web:public_html/rpi4edgemap"
export RELEASE_JOBS=32
```

Set `AB_OUTPUT` to the actual output you intend to use. Shell variables do not
carry into a new terminal. Keep signing keys outside rpi-extree. Confirm the
rclone destination maps to the stated URL. Stop other builds using this output;
the wrapper lock does not coordinate manual make commands.

## 2. Change configuration and save it

```bash
# Back up this output's current configuration.
cp "$AB_OUTPUT/.config" "$AB_OUTPUT/.config.backup-$(date +%Y%m%d-%H%M%S)"
make -C buildroot O="$AB_OUTPUT" menuconfig
# Save and exit menuconfig, then save the reviewed source profile:
make -C buildroot O="$AB_OUTPUT" savedefconfig BR2_DEFCONFIG="$AB_PROFILE"
git -C rpi-extree diff -- configs/raspberrypi4_edgemap_lite_ab_defconfig
```

`menuconfig` saves the output's `.config`. `savedefconfig` saves its minimal
settings to the source profile. Neither builds an image. Do not reload a
defconfig over intentional menuconfig changes. Editing the source defconfig does
not update an existing output automatically. After deliberately editing the
source profile, either configure a fresh output (below), or back up the existing
`.config` and explicitly reload the profile, reviewing lost local overrides:

```bash
make -C buildroot O="$AB_OUTPUT" BR2_EXTERNAL="$WORKSPACE/rpi-extree" \
  raspberrypi4_edgemap_lite_ab_defconfig
```

Keep Situation map, Python 3 with SSL/SQLite, SWUpdate, public CA certificates,
OpenSSL tools, util-linux binaries/partx, resize2fs and tryboot firmware enabled.
The legacy `edgemap` package is not required. The Lite overlay is
`${BR2_EXTERNAL}/fs_overlay/fs_edgemap_lite`.

## 3. Choose the refresh required by your change

Run package refresh commands only after stopping other builds. Replace `PACKAGE`
with its Buildroot package name. Every refresh is followed by a full image build
or the release wrapper, not by copying `output/target` to the Pi.

| Change | Action before full image build / release |
|---|---|
| Add or edit overlay files, updater scripts, systemd units | Full image build reruns overlay and hooks |
| Delete/rename overlay files or switch overlay directories | Fresh output; old target files otherwise remain |
| Disable/remove packages or many Python modules | Fresh output; Buildroot does not uninstall old files |
| Change toolchain, compiler ABI or kernel-header series | Fresh output |
| Edit a package's already-extracted local sources | `make -C buildroot O="$AB_OUTPUT" PACKAGE-rebuild` |
| Change package source pin, patches or source-copy method | `make -C buildroot O="$AB_OUTPUT" PACKAGE-dirclean` |
| Edit kernel config or fragments | `make -C buildroot O="$AB_OUTPUT" linux-reconfigure` |
| Change kernel source revision or kernel patches | `make -C buildroot O="$AB_OUTPUT" linux-dirclean`; refresh enabled external module packages too |
| Edit only saved defconfig | Apply deliberately to output or configure fresh output; saving alone does not apply it |

Situation sources are pinned in `rpi-extree/package/situation-map/situation-map.mk`.
Change `SITUATION_MAP_VERSION` to select new upstream code. The release wrapper
already runs `situation-map-dirclean`; it does not refresh unrelated packages.
A local-source package may need `dirclean` to recopy its original sources rather
than merely rebuild an existing extracted directory.

Kernel source is pinned by `BR2_LINUX_KERNEL_CUSTOM_TARBALL_LOCATION` in the A/B
profile. The current 6.18.62 pin is
`ef71464298cd2dd89f6d190c08e812296240281e`. Keep the headers series appropriate;
changing that series requires a new toolchain output. After a kernel source
change, rebuild enabled external kernel modules from clean package directories,
then build the complete image so kernel, rootfs and modules agree. Keep the
EdgeMap hardware config and A/B fragment when updating the kernel.

## 4. Fresh output when cleanup is needed

Save the reviewed profile first (section 2). Select a new, unused directory;
preserve old output/configuration for reference. Example:

```bash
export AB_OUTPUT="$WORKSPACE/output-edgemap-ab-fresh-01"
export RELEASE_OUTPUT="$AB_OUTPUT"
# This must print 'unused' before configuring it.
if test -e "$AB_OUTPUT"; then echo 'STOP: choose a new output'; else echo unused; fi
```

Only after confirming the directory is unused:

```bash
make -C buildroot O="$AB_OUTPUT" BR2_EXTERNAL="$WORKSPACE/rpi-extree" \
  raspberrypi4_edgemap_lite_ab_defconfig
```

Do not copy the old `target/` into it. Existing downloads can be reused through
Buildroot's configured download directory. A fresh output rebuilds the toolchain
and dependencies.

## 5. Build images without publishing

Choose your actual release version; the example `dev-6` is not a claim that this
version is unused on your server.

```bash
export AB_RELEASE_VERSION=dev-6
make -C buildroot O="$AB_OUTPUT" -j32
```

The key environment above is required by the post-build hook. A make invocation
without a target starts the default image build. `-j32` permits parallel work.

Inspect before provisioning/release:

```bash
cat "$AB_OUTPUT/images/release-version" "$AB_OUTPUT/images/release-profile"
cat "$AB_OUTPUT/build/linux-custom/include/config/kernel.release"
sfdisk --json "$AB_OUTPUT/images/sdcard-ab.img"
mtype -i "$AB_OUTPUT/images/boot-a.vfat" ::/cmdline.txt
mtype -i "$AB_OUTPUT/images/boot-b.vfat" ::/cmdline.txt
```

Factory image: `$AB_OUTPUT/images/sdcard-ab.img`. It replaces the whole card,
including Data, when flashed. An SWU replaces only the inactive boot/root pair.
EEPROM is separate from both; see [EEPROM.md](EEPROM.md).

## 6. Build, sign and publish a release

For an existing output with initial factory artifacts, the wrapper performs the
full build itself. A separate manual build is optional. Fresh outputs must first
complete section 5 because wrapper preflight requires existing factory artifacts.

Choose a version/sequence above the current public offer, never reuse an already
published version. Set the output explicitly, even if a previous shell used it:

```bash
export RELEASE_OUTPUT="$AB_OUTPUT"
export RELEASE_NOTES="Describe the changes in this release"
rpi-extree/board/edgemap-ab/release-public.sh dev-6
```

The wrapper checks output/trust/keys and publication state, takes its lock,
refreshes Situation, builds all images, signs and verifies the bundle, writes
checksums, uploads immutable payloads, verifies HTTPS bytes and publishes signed
`latest.json` last. Default offer expiry is seven days; override with
`RELEASE_EXPIRES_DAYS` deliberately. An expired offer needs newly signed metadata
with a fresh increasing sequence.

Artifacts/URLs for the example:

```text
edgemap-releases/dev-6/dev-6.swu
edgemap-releases/dev-6/SHA256SUMS
edgemap-releases/dev-6/latest.json
https://resilience-theatre.eu/rpi4edgemap/dev-6.swu
https://resilience-theatre.eu/rpi4edgemap/latest.json
```

The script may rebuild even after a manual build. It preserves the output's
configuration and does not reload the defconfig. It does not install on a Pi.
If it fails, inspect the error and partial local/remote artifacts; do not overwrite
published bundles or delete/reinitialize keys. Pre-publication failures preserve
the previous offer. Publication/cache verification failures require checking the
actual public state before recovery.

## 7. Device: check → download → install

Run as root over serial or SSH. The device needs networking, DNS and a valid
clock, but no display.

```sh
edgemap-update status
cat /etc/edgemap-ab/version
date -u
systemctl status edgemap-update-api --no-pager
edgemap-update-client check
edgemap-update-client wait
```

Require no device/offer error and the intended version/profile. Copy the exact
`offer.offer_id` into a variable:

```sh
OFFER_ID='PASTE_THE_FULL_OFFER_ID_HERE'
edgemap-update-client download --offer "$OFFER_ID" --accept
edgemap-update-client wait
```

Require `download_ready:true` and job phase `downloaded`. Download acceptance
does not authorize installation. Explicitly install the same offer:

```sh
edgemap-update-client install --offer "$OFFER_ID" --accept
edgemap-update-client wait
```

Installation stages/verifies a multi-gigabyte bundle, writes the inactive boot/root
pair and reads it back before automatically requesting a trial reboot. Keep power
connected. This can take several minutes. To inspect progress from another shell:

```sh
edgemap-update-client status
```

`swupdate.percent` is per-image progress, not whole-release progress. A successful
write is not yet a confirmed trial. Do not run a second installer, invoke SWUpdate
directly or restart services while installation is active.

## 8. Device: confirm, then ordinary reboot

After the automatic trial reboot:

```sh
edgemap-update status
cat /etc/edgemap-ab/version
journalctl -b -u edgemap-ab -u situation-map --no-pager
```

Require the intended version, opposite slot (A→B or B→A) and
`state.phase: committed`. Situation service/HTTP health authorizes selector
commit automatically. If health fails or the device falls back, inspect status
and journals before retrying; do not force confirmation.

After committed state, finish with an ordinary reboot:

```sh
systemctl reboot
```

After that boot:

```sh
edgemap-update status
cat /etc/edgemap-ab/version
df -h /data
```

Require the same new version/slot, phase `committed` and `trial:false` before the
next installation. The ordinary reboot clears the firmware trial condition; it
does not create persistence. Data is already persistent, and selector commit
already selected the new default slot. API alternative after fresh committed
status is `edgemap-update-client finish --accept`.

## 9. What persists and what overlay edits replace

Data backs `/etc/default`, `/etc/ssh`, `/etc/apache2`, `/var/lib`, `/opt/data` and
`/opt/situation/maps`. Situation database: `/var/lib/situation/situation.db`.
Map archives: `/opt/situation/maps`. Data grows to media capacity on first normal
factory A boot; inspect `/data/ab/factory-growth.json`.

An SWU preserves existing Data. New overlay defaults under these persistent paths
will not replace the device's established copies, even after a clean host build.
Changing them needs an explicit compatible device configuration/migration step.
Other files in boot/root are replaced through the inactive slot. Keep shared
formats backward-compatible with the previous slot during the rollback window.
For manual rollback and offline recovery, see [README.md](README.md).
