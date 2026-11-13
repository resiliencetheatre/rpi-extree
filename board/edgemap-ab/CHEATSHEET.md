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
export RELEASE_PUBLIC_URL="https://resilience-theatre.eu/rpi4edgemap"
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

**Required next step for a fresh output: build the initial images (section 5),
then publish (section 6).** The defconfig command above creates `.config` only;
it does not create boot/root images. Calling `release-public.sh` immediately
will stop with `Build and inspect the factory artifacts first`.

For example, if your next unused release is dev-7, after configuration run:

```bash
AB_RELEASE_VERSION=dev-7 AB_VERIFY_KEY="$WORKSPACE/ab-development-public.pem" \
  make -C buildroot O="$AB_OUTPUT" -j32
```

After that command succeeds, inspect the images using section 5, then run:

```bash
RELEASE_OUTPUT="$AB_OUTPUT" \
  rpi-extree/board/edgemap-ab/release.sh --public dev-7
```

Use the same chosen version in both commands. The wrapper rebuilds before
packaging, signing and publication. A new output does not require deleting the
old output; retain it until you no longer need its configuration or artifacts.

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

## 6. Build, sign and publish a release (public, local, or both)

Choose a destination explicitly:

```bash
rpi-extree/board/edgemap-ab/release.sh --public dev-8
rpi-extree/board/edgemap-ab/release.sh --local dev-8
rpi-extree/board/edgemap-ab/release.sh --public --local dev-8
```

These are alternatives, not three commands to run in sequence. Choose the next
unused version/sequence. Both flags build one signed SWU and publish it to both
channels with separate signed metadata binding each channel URL. No flags retains
build/sign-only behavior. `release-public.sh dev-N` remains a compatibility alias
for `release.sh --public dev-N`. Public mode alone does not need a local server;
local mode alone does not need rclone or a remote account.

For an existing output with initial factory artifacts, the wrapper performs the
full build itself. A separate manual build is optional. Fresh outputs must first
complete section 5 because wrapper preflight requires existing factory artifacts.

Choose a version/sequence above the current public offer, never reuse an already
published version. Set the output explicitly, even if a previous shell used it:

```bash
export RELEASE_OUTPUT="$AB_OUTPUT"
export RELEASE_NOTES="Describe the changes in this release"
rpi-extree/board/edgemap-ab/release.sh --public dev-6
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
edgemap-releases/dev-6/public/latest.json
edgemap-releases/dev-6/local/latest.json  (when --local is selected)
https://resilience-theatre.eu/rpi4edgemap/dev-6.swu
https://resilience-theatre.eu/rpi4edgemap/latest.json
```

The script may rebuild even after a manual build. It preserves the output's
configuration and does not reload the defconfig. It does not install on a Pi.
If it fails, inspect the error and partial local/remote artifacts; do not overwrite
published bundles or delete/reinitialize keys. Pre-publication failures preserve
the previous offer. Publication/cache verification failures require checking the
actual public state before recovery.

### Local Python HTTPS server: set up once on the PC

The local path uses verified HTTPS, the same signed offer/bundle checks and
immutable publication ordering as the public path. Plain `python -m http.server`
over LAN HTTP is not accepted by devices. Use the supplied Python HTTPS host.
Keep its directory outside rpi-extree and outside the served `www` directory.

Choose your actual LAN IPv4 address and an unused host directory:

```bash
export RELEASE_HOST="$WORKSPACE/edgemap-update-host"
export LOCAL_ADDRESS=192.168.1.50  # replace with this PC's actual LAN IPv4
export RELEASE_LOCAL_URL="https://$LOCAL_ADDRESS:9443"
export RELEASE_LOCAL_CA="$RELEASE_HOST/tls/ca.pem"
python3 rpi-extree/board/edgemap-ab/api/https_host.py init \
  --directory "$RELEASE_HOST" --address "$LOCAL_ADDRESS" --port 9443
```

`init` creates local TLS trust and refuses to overwrite a nonempty directory.
Run it once, not per release. The server certificate lasts 30 days and the CA
365 days; plan deliberate renewal before expiry, preserving trust appropriately.
Changing the address requires a matching certificate, not bypassing TLS checks.
No release signing keys or remote credentials belong in this host directory.

Start the server in another terminal and keep it running while publishing and
while devices check/download. Export/set the same host variables again there:

```bash
python3 rpi-extree/board/edgemap-ab/api/https_host.py serve \
  --directory /home/tech/laboratory/rpi4base/edgemap-update-host
```

It serves only allowlisted metadata, bundles, checksums and health; TLS/private
files are outside `www`. No server/firewall is started or changed by release.sh.
The chosen address/port must already be reachable from the Pi. Check manually:

```bash
curl --cacert "$RELEASE_LOCAL_CA" "$RELEASE_LOCAL_URL/health.json"
# Build/sign/publish to the local server only:
rpi-extree/board/edgemap-ab/release.sh --local dev-8
# Or build once and publish to both (instead of the previous command):
rpi-extree/board/edgemap-ab/release.sh --public --local dev-8
```

Local artifacts appear in `$RELEASE_HOST/www`, public artifacts in the rclone web
folder. Both destinations are preflighted before the build when both are selected.
Each payload is verified over its actual HTTPS URL before metadata activation.
Publication across two servers is not a distributed transaction: the first can
succeed while the second fails. Inspect both states after any error. Never rerun
a normal build over an existing version directory or overwrite a published SWU.

To add an already-built release to a channel that has not received it, avoid
rebuilding with (example: dev-8 was public-only and is now needed locally):

```bash
rpi-extree/board/edgemap-ab/release.sh --local --publish-only dev-8
```

This re-verifies the existing bundle, signs channel-specific metadata and applies
the same preflight/upload checks. It refuses a version already present at that
destination. It is not an automatic repair of partially uploaded versions; retain
partial artifacts and inspect the failure before recovery. Same version must mean
same SWU bytes on both servers. Signed URL/notes/expiry changes require a fresh
increasing sequence if that offer has already been published.

### Configure both target sources once

Images containing the new `update.sh` wrapper use two named sources in persistent
`/etc/default/edgemap-update-sources.json`. Both use the same installed verification
key and shared replay history. The source file cannot override either of them.
Public HTTPS uses the system CA store; local HTTPS uses the supplied local CA.

First copy **only** `$RELEASE_HOST/tls/ca.pem` to the Pi:

```bash
scp "$RELEASE_HOST/tls/ca.pem" root@DEVICE:/data/update-local-ca.pem
```

For serial-only access, transfer that public PEM using your serial file-transfer
method. Never transfer CA/server private keys or the release signing key.
On the Pi, set the actual PC address in the source file:

```sh
vi /etc/default/edgemap-update-sources.json
```

```json
{
  "remote": {
    "manifest_url": "https://resilience-theatre.eu/rpi4edgemap/latest.json"
  },
  "local": {
    "manifest_url": "https://192.168.178.41:9443/latest.json",
    "ca_file": "/data/update-local-ca.pem"
  }
}
```

This address is an example from the current desk setup; use the address matching
your initialized host certificate. The factory template deliberately leaves the
local URL unset. A source selection loads the file afresh; restarting the API is
unnecessary after editing it. Existing images receiving the new wrapper through
SWUpdate get a missing source file seeded from the installed template. If their
active API configuration already has a private-CA local URL, it is imported as
`local`. Existing source-file edits are never overwritten.

Source selection is allowed only while idle and outside a trial. It discards the
previous source's cached offer/download, retains sequence history and persists
the selected source for API restarts. A local CA is never applied to the remote
source. A different URL produces a different signed offer ID, so switching
channels requires a strictly higher sequence than one already accepted from the
other source. Do not delete replay history to accept an older/equal offer.

**One-time bootstrap on images without `update.sh`:** install the next signed
release using the existing client commands below, then perform its final ordinary
reboot manually. If you need local hosting for that first update, configure
`/etc/default/edgemap-updates.json` with `manifest_url` pointing to local
`latest.json`, `ca_file` set to `/data/update-local-ca.pem`, and retain
`public_key: /etc/edgemap-ab/public.pem`, `data_dir: /data/update-api`, and
`allow_http_loopback: false`. Restart `edgemap-update-api`, wait for its socket,
and use the advanced commands below. From then on use the named-source wrapper;
do not edit the active API URL to switch sources.

## 7. Device: single-command update (recommended)

Run as root over serial or SSH:

```sh
update.sh --remote   # public rclone-published channel
# OR:
update.sh --local    # local Python HTTPS channel
```

The wrapper waits for the API socket to become ready, checks the selected source,
displays the current and offered versions, source, release notes and bundle size,
then asks `Update y/n? [y/N]`. Nothing is downloaded or installed if declined.
If the offered version already runs, it exits without prompting.

Answering `y` authorizes download and installation of that exact verified offer,
a trial reboot and a final ordinary reboot only after successful trial health.
The wrapper shows download bytes/percent, verification stages and SWUpdate
per-image write progress. Unknown progress remains stage-only; it never affects
activation. Keep power connected. The serial/SSH session may disconnect during
reboot; output does not by itself prove successful trial confirmation.

After trial health commits the expected profile/layout, version and target slot,
`edgemap-update-finish.service` checks fresh API status and requests the ordinary
reboot automatically. This applies only when `update.sh` recorded that explicit
authorization before installation. Failed/unconfirmed/wrong-slot trials never
authorize that reboot. A fallback is reported without another reboot. Previously
accepted updates using the low-level client still need manual finishing.

Inspect from another shell, or after reconnecting:

```sh
update.sh --status
```

Require the intended version, phase `committed`, and `trial=False` after both
boots. `Ctrl-C` stops monitoring, not an accepted background job; inspect status
before starting anything else. A monitor timeout or lost socket during reboot
is not a success report. The API and local CLI stay available for diagnosis.
A previous committed trial from the old workflow must first be finished with
`systemctl reboot`; the wrapper will explain this rather than start another update.

If the API is unavailable:

```sh
systemctl status edgemap-update-api --no-pager -l
journalctl -b -u edgemap-update-api -u edgemap-update-finish --no-pager
```

## 8. Advanced device commands: check → download → install

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

## 9. Advanced device commands: confirm, then ordinary reboot

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

## 10. What persists and what overlay edits replace

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
