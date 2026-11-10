# PocketTerm development and release lifecycle

All PC commands run from `/home/tech/laboratory/rpi4console`. Commands here are
operator instructions: building, publishing and flashing are separate actions.
Examples use dev-10/dev-11/dev-12 only to illustrate order. Choose unused numbers
above your real release history; never copy an old example number blindly.

## Outputs, artifacts and what a device displays

| Purpose | Defconfig | Default build output |
|---|---|---|
| Local development and SWU releases | `raspberrypi4_pocketterm_ab_defconfig` | `output-pocketterm-ab` |
| Public factory defaults | `raspberrypi4_pocketterm_public_defconfig` | `output-pocketterm-public` |
| Optional original single-slot regression | `raspberrypi4_pocketterm_defconfig` | `output-pocketterm-baseline` |

| Command | Builds | Publishes | Artifact |
|---|---|---|---|
| `release.sh dev-N` | Existing A/B output, LVGL refreshed | Local desk HTTPS document root | `pocketterm-releases/dev-N/dev-N.swu` |
| `release-public.sh dev-N` | Existing A/B output, LVGL refreshed | Public host using rclone | SWU, versioned checksum, signed `latest.json` |
| `build-public-image.sh dev-N` | Separate public output, LVGL refreshed | Nothing | `pocketterm-factory-images/dev-N/pocketterm-public-dev-N.img.xz` |

All compile on the PC. An SWU contains boot assets and the complete rootfs,
including the application and kernel modules. Installation replaces only the
inactive boot/root pair, then trial-boots and confirms it; Data and GPT remain.
A factory image replaces the entire card, including Data, and provisions both
slots. EEPROM firmware is outside both artifacts and requires a separate update.

**Installed** is the version running on the device. **Available** comes from the
configured server's signed `latest.json`. Building a factory image, uploading a
factory image or installing locally does not update that offer. For example,
building dev-8 while the server's metadata still names dev-6 leaves Available at
dev-6. Never change the embedded version marker to relabel an old image.

## Editing configuration with menuconfig

Run menuconfig against the existing output directory you intend to release from.
For the clean A/B output introduced in the dev-13 workflow below:

```sh
cd /home/tech/laboratory/rpi4console
export RELEASE_OUTPUT="$PWD/output-pocketterm-ab-clean-dev13"
mkdir -p build-config-backups
cp "$RELEASE_OUTPUT/.config" \
  "build-config-backups/pocketterm-ab-before-menuconfig-$(date +%Y%m%d-%H%M%S).config"
make -C buildroot O="$RELEASE_OUTPUT" menuconfig
```

Stop/wait for builds and release wrappers using that output before editing it.
Save and exit to update its `.config`. Menuconfig does not build or publish a
release. The `dev13` directory suffix records when the output was created; it
does not constrain future release versions. Keep `RELEASE_OUTPUT` exported when
running `release-public.sh` in the same shell, and export it again in a new shell.
Otherwise the wrapper defaults to the older `output-pocketterm-ab` directory.
If deliberately using another configured output, substitute its absolute path.

To preserve the reviewed configuration in the A/B source profile as well:

```sh
make -C buildroot O="$RELEASE_OUTPUT" savedefconfig \
  BR2_DEFCONFIG="$PWD/rpi-extree/configs/raspberrypi4_pocketterm_ab_defconfig"
git -C rpi-extree diff -- configs/raspberrypi4_pocketterm_ab_defconfig
```

`savedefconfig` writes the source profile; menuconfig alone changes only the
selected output. Review the diff before retaining it, especially if the profile
already has local edits. Do not rerun the `raspberrypi4_pocketterm_ab_defconfig`
target merely to open configuration: that reloads the saved profile and can
discard unsaved output-specific choices.

Public factory images use an independent configuration:

```sh
export PUBLIC_OUTPUT="$PWD/output-pocketterm-public"
cp "$PUBLIC_OUTPUT/.config" \
  "build-config-backups/pocketterm-public-before-menuconfig-$(date +%Y%m%d-%H%M%S).config"
make -C buildroot O="$PUBLIC_OUTPUT" menuconfig
make -C buildroot O="$PUBLIC_OUTPUT" savedefconfig \
  BR2_DEFCONFIG="$PWD/rpi-extree/configs/raspberrypi4_pocketterm_public_defconfig"
git -C rpi-extree diff -- configs/raspberrypi4_pocketterm_public_defconfig
```

Use your actual `PUBLIC_OUTPUT` override if different. Apply intended common
changes to both configurations separately, retaining the public factory defaults.
The factory wrapper preserves an existing output configuration. Neither saving
a defconfig nor editing one output updates the other output automatically.
After configuration changes, follow the package refresh rules below before
building; some changes require a fresh output.

## Configuration and refresh rules before any release

Buildroot builds from `OUTPUT/.config`, not directly from the saved defconfig.
Neither release wrapper reloads it. The public factory wrapper loads its defconfig
only when creating a nonexistent output directory. Editing a defconfig therefore
has no effect on an already configured output until you deliberately reload it.

Stop/wait for all builds in the selected output first. Wrappers share a lock with
each other, but do not coordinate manual make commands. Preserve local changes:

```sh
mkdir -p build-config-backups
cp output-pocketterm-ab/.config \
  "build-config-backups/pocketterm-ab-$(date +%Y%m%d-%H%M%S).config"
make -C buildroot O="$PWD/output-pocketterm-ab" \
  BR2_EXTERNAL="$PWD/rpi-extree" raspberrypi4_pocketterm_ab_defconfig
```

Review differences and reapply intentional local overrides. Do not reload a
profile during a routine app-only release; it can discard local configuration.
For the public factory output, perform the equivalent operation separately:

```sh
cp output-pocketterm-public/.config \
  "build-config-backups/pocketterm-public-$(date +%Y%m%d-%H%M%S).config"
make -C buildroot O="$PWD/output-pocketterm-public" \
  BR2_EXTERNAL="$PWD/rpi-extree" raspberrypi4_pocketterm_public_defconfig
```

These backup examples assume outputs already exist. Initial configuration is
covered below. Keep both opt-in defconfigs aligned for intended kernel/package
changes; the public profile adds public defaults, not a different hardware/layout
contract. Editing one defconfig does not update the other.

| Changed source/configuration | Refresh before the full release build |
|---|---|
| Local `lvgl-console` sources | All three wrappers run `lvgl-console-local-dirclean` automatically |
| Rootfs overlay, updater Python, systemd unit | Full image build reruns overlay/post-build integration; no package clean normally needed |
| Defconfig symbols | Reload the matching defconfig, review overrides, then refresh affected packages |
| Kernel config fragments | `make -C buildroot O="ABS_OUTPUT" linux-reconfigure` |
| Kernel source commit/tarball or kernel patches | Reload config if URL changed, then `make -C buildroot O="ABS_OUTPUT" linux-dirclean` |
| Existing package's build options | Its documented `<package>-reconfigure` or `<package>-dirclean` workflow |
| Other local package sources | Explicitly refresh that package; the wrappers refresh only LVGL |
| Toolchain, architecture, libc, broad dependency/ABI changes | Fresh separate output and full build; do not rely on incremental refresh |
| Files removed from overlays or package installations | Use explicit cleanup hooks or a fresh output; overlay copies do not delete stale files |

Buildroot does not generally rebuild reverse dependencies when a library changes.
Cleaning Linux alone does not guarantee third-party kernel module packages are
rebuilt; refresh all external module packages in the selected profile too. A fresh
output is the clearest choice when the dependency impact is uncertain. Changes to
installed package files can leave obsolete files in `target/`; `dirclean` alone
is not a general filesystem uninstall.

For a fresh output after a toolchain change, initialize the selected defconfig
and perform the full image build with `AB_RELEASE_VERSION` and `AB_VERIFY_KEY`
first, as in the one-time provisioning example below. Then pass its absolute path
as `RELEASE_OUTPUT` to the SWU wrapper. In particular, `release-public.sh` checks
an already built factory verification key under `target/`; it cannot bootstrap a
brand-new empty output by itself. The public factory wrapper can initialize and
build its own fresh `PUBLIC_OUTPUT`.

### Updating Buildroot and publishing dev-13 from a clean build

Use this workflow when updating the Buildroot checkout, especially across
release/toolchain/package changes. These commands update sources, compile a fresh
system and finally publish publicly; run them deliberately. They do not flash or
install on a device. dev-13 must be unused and sequence 13 must exceed the public
channel/device history; otherwise substitute a newer version everywhere.

First stop/wait for any builds and release wrappers. Do not change the Buildroot
checkout underneath a running build. Inspect all repositories and preserve local
changes before pulling; do not reset or discard them to make an update succeed.

```sh
cd /home/tech/laboratory/rpi4console

git -C buildroot status --short
git -C rpi-extree status --short
git -C lvgl-console status --short
mkdir -p build-config-backups/dev-13

git -C buildroot rev-parse HEAD > build-config-backups/dev-13/buildroot-before.revision
if [ -f output-pocketterm-ab/.config ]; then
  cp output-pocketterm-ab/.config build-config-backups/dev-13/pocketterm-ab-before.config
fi
```

Once Buildroot's working tree is clean (or your changes are deliberately preserved
and compatible), update its configured upstream branch without creating an
unexpected merge commit:

```sh
git -C buildroot pull --ff-only
git -C buildroot rev-parse HEAD > build-config-backups/dev-13/buildroot-after.revision
```

If the pull fails, resolve the branch/local-change issue before continuing. Review
Buildroot release/migration notes and external-tree/package/patch compatibility.
A fresh output avoids stale artifacts; it does not make incompatible external
sources compatible. Existing outputs now refer to the changed checkout, so do not
resume builds in them casually; retaining an old output is not a source rollback.
Keep the recorded old revision and matching external/app sources for recovery.

Configure a nonexistent directory and explicitly retain the channel's signing
trust. This shell block sets paths reused by the subsequent commands:

```sh
export RELEASE_OUTPUT="$PWD/output-pocketterm-ab-clean-dev13"
export AB_VERIFY_KEY="$PWD/ab-development-public.pem"
export AB_SIGN_KEY="$PWD/ab-development-private.pem"

test ! -e "$RELEASE_OUTPUT" &&
make -C buildroot O="$RELEASE_OUTPUT" \
  BR2_EXTERNAL="$PWD/rpi-extree" raspberrypi4_pocketterm_ab_defconfig
```

If the directory already exists, inspect it and select another fresh name rather
than deleting it blindly. Reapply intentional old configuration overrides using
menuconfig/review, not by replacing the new configuration wholesale with the old
`.config`. This command uses the saved A/B profile, not the public factory profile.

Build the complete system locally first:

```sh
AB_RELEASE_VERSION=dev-13 \
  make -C buildroot O="$RELEASE_OUTPUT" -j4
```

Check the exit status and inspect outputs before publishing:

```sh
cat "$RELEASE_OUTPUT/images/release-version"
cat "$RELEASE_OUTPUT/images/release-profile"
cp "$RELEASE_OUTPUT/.config" build-config-backups/dev-13/pocketterm-ab-built.config
ls -lh "$RELEASE_OUTPUT/images/sdcard-ab.img"
```

Expected markers: dev-13 and pocketterm-rpi4-lvgl-v1. Inspect GPT, both cmdlines,
image sizes and firmware/key configuration as described in the board guide.
Where possible, validate a local bundle on spare hardware before public release.

Then build/sign/verify/upload the public SWU:

```sh
rpi-extree/board/pocketterm-ab/release-public.sh dev-13
```

The exported RELEASE_OUTPUT is essential: without it the wrapper falls back to
output-pocketterm-ab. It checks the existing built verification key, refreshes
LVGL and reruns the full image build using the newly compiled toolchain/packages,
then signs and publishes. It does not recompile every unchanged dependency a
second time. A failed publication can leave partial release artifacts; inspect
them rather than rerunning with an already existing version directory.

For an additional clean public factory image from the same updated sources:

```sh
PUBLIC_OUTPUT="$PWD/output-pocketterm-public-clean-dev13" \
  rpi-extree/board/pocketterm-ab/build-public-image.sh dev-13
```

This is another full build, using the public profile/defaults. Its archive is
separate from the SWU release, so the same dev-13 label can represent the same
frozen source release. It does not upload the image or change latest.json. Keep
sources fixed between both builds and validate both artifacts. The public factory
section below gives explicit image upload commands.

### Disk space and retaining old outputs

Deleting old build directories is optional, not a clean-build requirement. A fresh
O= directory already gives a clean build. Keep at least the last known-good image,
SWU/checksums, configurations, source revisions/local changes and signing trust
before discarding an output. Prefer waiting for successful new-image testing,
trial commit and ordinary reboot. Archive backups outside the directory you will
remove. Deleting a directory cannot remove the copy running on the device, but
can remove your only recovery artifact or diagnostics.

Inspect sizes first:

```sh
du -sh output-pocketterm-ab output-pocketterm-public \
  output-pocketterm-ab-clean-dev13 pocketterm-releases pocketterm-factory-images
```

Only after checking the exact old directory, confirming no build uses it, and
archiving needed artifacts, you may remove it manually. For example, the following
explicitly destroys the old development build output, not the fresh dev-13 output:

```sh
rm -rf -- /home/tech/laboratory/rpi4console/output-pocketterm-ab
```

Do not remove source repositories, private keys, rclone configuration, HTTPS host
trust, release archives or the new output as part of build cleanup. Before deleting
an output, check where its dl/ directory points: a private download cache inside it
will also be removed, whereas a symlink's external target is not deleted by this
command. Shared Buildroot download caches can normally be retained across clean
builds to avoid downloading again; do not delete them merely to force recompilation.
Use the new RELEASE_OUTPUT explicitly for future SWU releases, or deliberately
establish a new configured default output; the wrappers do not remember your last
custom output path after the shell environment is gone.

### Changing the kernel commit

Update `BR2_LINUX_KERNEL_CUSTOM_TARBALL_LOCATION` to the intended Raspberry Pi
Linux commit in each selected defconfig. Keep URL/archive names consistent.
These profiles enforce `BR2_DOWNLOAD_FORCE_CHECK_HASHES=y`: obtain and verify the
actual archive checksum, then add the matching filename/hash entry to the relevant
Linux hash files under `BR2_GLOBAL_PATCH_DIR`. Current entries are distributed
under `board/raspberrypi/patches/linux/` and `patches/linux/` (including `custom/`).
Inspect the pinned Buildroot's selected hash path and download diagnostic; do not
guess a checksum, replace unrelated entries, or turn hash checking off. A headers
version/source change is a separate toolchain decision, not an automatic result
of updating the runtime kernel URL.

After updating source/hashes, back up and reload the A/B defconfig as above, then:

```sh
make -C buildroot O="$PWD/output-pocketterm-ab" linux-dirclean
```

The next local/public SWU wrapper compiles the new kernel as part of the full
build. It does not compile Linux from scratch every time if Linux is unchanged.
Apply the same configuration/refresh workflow to `output-pocketterm-public`
before building a new public factory image. Kernel/firmware changes require new
hardware boot, module, display/input, trial and rollback checks.

## Local-only development on desk

### One-time provisioning

Use spare media and the A/B profile. Supply your existing external public key;
future signed bundles must use its matching private key. Keep private release
keys, host TLS keys, rclone credentials and artifacts outside `rpi-extree`.

```sh
make -C buildroot O="$PWD/output-pocketterm-ab" \
  BR2_EXTERNAL="$PWD/rpi-extree" raspberrypi4_pocketterm_ab_defconfig
AB_RELEASE_VERSION=dev-10 AB_VERIFY_KEY="$PWD/ab-development-public.pem" \
  make -C buildroot O="$PWD/output-pocketterm-ab" -j4
```

Flash `output-pocketterm-ab/images/sdcard-ab.img` only to your explicitly
identified spare whole card, backing up data first. Follow the board README for
partition/first-boot inspection and recovery. The known working Pi 4 EEPROM is
2026-10-30, revision `13c4219f16dbe58c5b9946086b474baf572512bb`; the 2021 EEPROM
previously selected B unexpectedly and blocked factory growth. This records a
working version, not a proven minimum version. Verify the actual media topology.

Initialize the local HTTPS host once if absent (do not regenerate existing trust):

```sh
python3 rpi-extree/board/pocketterm-ab/api/https_host.py init \
  --directory "$PWD/pocketterm-update-host" --address 192.168.178.41 --port 9443
```

In a dedicated PC terminal, start it manually:

```sh
python3 rpi-extree/board/pocketterm-ab/api/https_host.py serve \
  --directory "$PWD/pocketterm-update-host"
```

Verify from another terminal:

```sh
curl --fail --cacert pocketterm-update-host/tls/ca.pem \
  https://192.168.178.41:9443/health.json
```

Use [the device bootstrap commands](api/README.md#first-time-device-trust-and-api-configuration)
to create `/data/update-api/trust`, copy `ca.pem` as `host-ca.pem`, and create
`/etc/default/pocketterm-updates.json` pointing at
`https://192.168.178.41:9443/latest.json` with that `ca_file`. This is required
before the local API starts. Configure the real PTT server/audio and relay settings
in `/etc/default`; first-boot Data persists these settings. Correct the target
clock and confirm Python SSL, Data growth, normal A and LVGL readiness.

### Daily edit/build/test cycle

1. Edit app, kernel, packages, overlay or updater sources. Review the refresh table
   above and perform any required configuration reload/package refresh.
2. Choose a unique version; build/sign/publish to desk:

   ```sh
   RELEASE_BASE_URL=https://192.168.178.41:9443 \
     rpi-extree/board/pocketterm-ab/release.sh dev-11
   ```

3. Leave the local server running. On target, Check for updates, review the offer,
   explicitly accept download, wait for verified completion, then separately
   accept installation. CLI equivalents are in the API guide.
4. After automatic trial reboot, require the expected release/slot and
   `phase: committed`. Perform Finish update → Restart (normal reboot), then
   require the same release/slot and `trial: false` before another install.
5. Check service health, display/input/audio, persistence and application behavior.
   Alternate A→B and B→A; archive release/config/source records and results.

The local wrapper updates only the local document root; it never calls rclone.
You can do many local iterations before publishing anything publicly. Do not
modify source files or run another build against that output during a release.

## Periodic public SWU release

Freeze and record the intended source revisions/local changes after local testing.
Choose a new version above the local/public release history. Both release wrappers
use `pocketterm-releases/dev-N`; attempting the same version in both wrappers
fails rather than overwriting. The simple routine below uses a fresh public
version and rebuilds from the frozen sources; it does not upload an earlier local
bundle automatically. If byte-for-byte promotion of a tested SWU is needed, use
`api/publish.py` and `api/public_release.py` explicitly with a new sequence and the
final public URL, preserving all original payload bytes.

```sh
rpi-extree/board/pocketterm-ab/release-public.sh dev-12
```

Defaults are `output-pocketterm-ab`, `hetzner-web:public_html/pocketterm`, and
`https://resilience-theatre.eu/pocketterm`. The wrapper checks existing trust,
refreshes LVGL, builds the complete image, signs/verifies the bundle, uploads the
SWU/checksum, verifies full public HTTPS download, then publishes signed metadata
last. It does not run a Python server. Configure rclone SFTP host-key validation
against a separately verified host key; keep its credentials outside the source
repository. See the API guide for remote rename/caching/failure-recovery details.

Metadata binds profile/layout, version, sequence, expiry, URL, size and hash.
The wrappers map dev-N to sequence N. Use globally increasing N when devices move
between local/public endpoints: devices retain accepted sequence state. Never
reset that state or edit signed JSON to bypass a rejection. URL, notes or expiry
changes require newly signed metadata with a fresh sequence. Current offer expiry
defaults to seven days; choose `RELEASE_EXPIRES_DAYS` deliberately for your release
interval. Expiry stops acceptance of that offer; it does not disable an already
installed system. There is no automatic scheduled release job or automatic install.

On target, switch to the [public JSON configuration](api/README.md#public-releases-with-rclone),
removing the lab `ca_file`, restart the API and explicitly check. Metadata and SWU
must use the same HTTPS hostname/scheme/port; redirects are rejected. Existing
public factory devices already have this configuration. To move a public device
back to desk, deliberately restore the local URL and CA configuration; merely
flashing/installing an SWU does not change existing persistent `/etc/default`.

Verify the live offer from the PC without piping a failed HTTP response into JSON:

```sh
curl --fail --silent --show-error \
  https://resilience-theatre.eu/pocketterm/latest.json -o /tmp/pocketterm-latest.json &&
python3 -m json.tool /tmp/pocketterm-latest.json
```

Then test download/install/commit/normal reboot on spare hardware. A publish-success
message proves upload/readback, not a successful device update. The client currently
rejects the already-running version but has no semantic version anti-downgrade
policy; keep the public offer appropriate for your fleet and do not accept an
older offered release just because it is displayed.

## Periodic public factory baseline

Build a factory baseline less often, when you want new users to flash a recent
known-good system. Use the same frozen source set and intended version as the
public SWU when offering matching artifacts. Align both defconfigs and refresh
both outputs as described above; separate builds are not inherently byte-identical.
The public profile includes the public URL and `UDPPTT_SERVER=91.98.237.100`.
Other application defaults remain documented development defaults.

```sh
rpi-extree/board/pocketterm-ab/build-public-image.sh dev-12
```

This independently builds `output-pocketterm-public` and creates
`pocketterm-factory-images/dev-12/pocketterm-public-dev-12.img.xz` plus SHA256SUMS
and local provenance records. It uses only the public verification key, never the
private signing key. This command does not upload anything or change latest.json.
You can build an SWU and factory image with the same version because their archive
directories differ; never rebuild a released version from different sources.

Inspect/test the new factory image on spare media: normal A, expanded Data,
embedded version/key, public config, PTT defaults and actual device operation.
Verify the public SWU is compatible and test its lifecycle too. Upload only the
intended image and checksum after validation:

```sh
rclone copyto --immutable \
  pocketterm-factory-images/dev-12/pocketterm-public-dev-12.img.xz \
  hetzner-web:public_html/pocketterm/pocketterm-public-dev-12.img.xz
rclone copyto --immutable pocketterm-factory-images/dev-12/SHA256SUMS \
  hetzner-web:public_html/pocketterm/pocketterm-public-dev-12.img.xz.SHA256SUMS
```

Publish the download link/checksum and minimum validated hardware/EEPROM guidance.
Newly flashed devices use public updates without copying the desk CA. Network,
DNS and correct time are still required. Checks/downloads/installs remain explicit.
Installing an SWU preserves existing PTT settings and update URL on Data; factory
flashing initializes defaults anew and erases previous Data.

## Troubleshooting and release gates

| Symptom | First check |
|---|---|
| Installed version differs from locally built version | `/etc/pocketterm-ab/version` and `pocketterm-update status`; building is not deploying |
| Available is older than expected | Which server is configured, its live signed `latest.json`, and whether a public SWU was actually published |
| Public latest.json is 404 | rclone directory listing and public web-root mapping; uploading only an image does not create an offer |
| Bundle must share metadata origin | Signed bundle URL vs configured manifest origin; re-sign/resequence metadata instead of editing JSON |
| Update service unavailable / socket missing | Config exists, API unit/journal, wait for startup and check `/run/pocketterm-update-api/control.sock` |
| Baseline installation failed | `/data/update-api/install.log` and controller/API status; do not clear locks/state |
| Lock failure at installer startup | Include the API polling/installer serialization fix; drain status calls and serve cached state while installing |
| First factory growth refuses Boot B | EEPROM, firmware selection and actual slot; never bypass the first-boot guard |

Before a public rollout, distinguish source tests, built image inspection and
physical results. Required physical gates include wrong-profile/tampered bundles,
persistence, both update directions, ordinary reboot after commit, failed kernel
and root mount, readiness failure/hung trial, and power cuts during writes and
selector commit. Keep the previous slot and compatible shared data throughout the
rollback window. Retain known-good recovery images and source/config records.

No claim is made that unrelated profiles in rpi-extree are credential-free;
pre-existing tracked EdgeMap private material is a separate cleanup/rotation task.
