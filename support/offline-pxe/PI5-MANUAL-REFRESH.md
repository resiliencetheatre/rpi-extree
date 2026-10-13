# Manual mirror refresh over Pi 5 Wi-Fi

For the everyday command sequence and a worked explanation of the 512 GB card,
start with [MIRROR-OPERATIONS.md](MIRROR-OPERATIONS.md). This document contains
setup and implementation details.

The Pi 5 image includes `offline-mirror-update`. No update timer, cron job,
boot-triggered download or automatic activation is installed. The existing recovery
timer can recover interrupted **local maintenance**, but never downloads content.
Pi 4 keeps the workstation acquisition workflow.

This updates an already populated, verified mirror. Use DESK-MIRROR.md and
MICROSD-DATA.md for initial population. A firmware rebuild is needed to add the
updater to an older image; copying the Python script alone is insufficient.

## Build and install

```
WORKSPACE=/path/to/workspace
export BR2_EXTERNAL="$WORKSPACE/rpi-extree"
cd "$WORKSPACE/buildroot"
make rpi5_offline_pxe_defconfig
make -j8
```

If using `O=...`, pass the same output directory to both commands. This adds Python
3 with compression/TLS support, gpgv and pinned Debian archive public keys. It does
not install apt, debmirror, Perl or a Debian chroot. The image sizes remain 128 MiB
boot and 512 MiB rootfs; the actual image build must pass the existing size checks.
Use `migrate-pi5-card.py` as described in MIGRATE-PI4-CARD-TO-PI5.md to replace only
partitions 1/2, preserving mirror partition 3. Reconfigure the existing data UUID
and acknowledge/enroll UTC after replacing rootfs, as documented there.

## Connect and check

On Pi, as root:

```
iwctl station wlan0 scan
iwctl station wlan0 get-networks
iwctl station wlan0 connect "YOUR_SSID"
offline-ready
offline-mirror-update --check
```

Wi-Fi must use a different subnet from the PXE LAN. The default upstream route
must be through wlan0; transfer sockets bind to wlan0. DNS uses the existing iwd /
systemd-resolved configuration. TLS uses the image CA certificates. HTTP redirects
and ambient proxy settings are not followed. Correct acknowledged UTC is required.

`--check` fetches signed metadata and package indexes, verifies signatures, reports
complete package bytes and checks capacity. It does not fetch pool packages or
stop PXE services. Planning indexes temporarily occupy /run and are removed when
it finishes. Expect more traffic than a simple connectivity probe. A configured
private-profile import is also checked. Index/decompression limits fail closed.

## Preserve private NVMe and SATA profiles

If you already deployed unattended menus, import your **original private input
preseeds** once. Copy the two inputs privately onto the Pi, for example using
removable storage or the trusted isolated LAN. Do not use the generated nvme.cfg /
sata.cfg served by nginx: they already contain generated hooks and are not valid
source inputs. Never put real credentials in the source tree or rootfs overlay.

With no installations or offline APT operations running:

```
offline-mirror-update --import-profiles /tmp/preseed-nvme.cfg /tmp/preseed-sata.cfg \
  --default menu --enable-destructive-profile --no-active-installers
```

Use `--default nvme` or `--default sata` only if you intentionally want that disk
profile selected automatically after the menu timeout; selecting either profile
replaces its configured client disk without further confirmation. `menu` waits.
Import pauses services briefly, then restores the old menu unchanged. It saves
inputs with private permissions in `/srv/offline/.private-profiles`, outside all
HTTP/TFTP roots. Remove temporary input copies after successful import. The inputs
persist across rootfs upgrades because they are on partition 3.

Each refreshed generation renders the imported profiles against its verified
installer. Without imported inputs, an existing unattended deployment blocks
refresh instead of silently losing profiles. Guided-only mirrors need no import.
Updated generations include the control-file backups expected by the existing
`deploy-unattended.sh --disable` rollback operation. Reimport if you change private
profiles or default selection; existing generations are not altered by import.

## Refresh, then activate explicitly

With no laptop installations or offline APT operations running:

```
offline-mirror-update --no-active-installers
```

This is a maintenance window: PXE and HTTP stop while storage is writable. Keep
power connected and allow potentially hours for copies and full verification.
The command prints its staging generation name immediately; record it. Content
coverage remains trixie/trixie-updates/trixie-security, amd64/all, all four
components and applicable udebs plus authenticated amd64 netboot artifacts.
Optional i386/source settings are honored without reducing the default scope.

Verified unchanged packages are copied from the active generation, saving Internet
traffic. They are not hardlinked; another generation needs its own storage and
writes. New packages download over HTTPS and must match signed size/SHA256.
The full destination is verified before publication. Unknown installer policy
versions or compression formats are rejected and require a reviewed software
update, not a verification bypass.

On success the old generation resumes service and the command prints:

```
offline-activate NEW_GENERATION --no-active-installers
```

Run that separately when ready. Then test PXE and offline APT with Wi-Fi disconnected.
A successfully refreshed generation is not proof of a successful laptop install;
keep the old generation until hardware tests pass.

## Status, resume, and recovery

```
offline-mirror-update --status
offline-mirror-update --resume GENERATION --no-active-installers
```

Resume re-fetches signed indexes and reuses verified staged packages; partial
network downloads resume where supported. Upstream metadata rotation causes a
visible failure: resume explicitly to obtain a coherent newer set. There are three
bounded transfer attempts per file, not an endless acquisition loop. No failed
acquisition switches `current` or removes the old generation.

Ctrl-C/termination restores the old read-only service where possible. After power
loss, the recovery timer reconciles the persistent transaction and restores the
old generation; it does not resume downloads. Manual equivalent:

```
offline-mirror-update --recover
```

If recovery cannot verify UUID, active generation, read-only mount or clock, it
keeps services blocked. Correct the reported condition (including RTC/manual UTC)
and retry recovery. Do not delete the transaction marker to bypass readiness.
Rootfs transaction state lives in `/var/lib/offline-pxe/update-transaction.json`.
Logs are `/srv/offline/.update.log` plus one rotated file, each about 1 MiB maximum,
outside HTTP roots. Progress does not log private profile contents.

## Space and retention

The default 100 GiB free-space reserve is enforced during acquisition. Planning
adds 1 GiB overhead to package bytes; actual metadata/staging usage can be larger
and is checked during writes. A new generation requires a full copy; ext4 reflinks
are not assumed. A 512 GB card accommodated the previously measured ~140 GiB mirror,
but third/future generations may not fit while keeping the reserve. Nothing is
pruned automatically. Retain the previous generation until the replacement passes installation tests.
On the 512 GB card, normally retain only the current tested generation before
starting the next refresh; keeping two while building a third exceeds the default
space budget. Remove
only explicitly chosen, no-longer-needed inactive generations during separate
storage maintenance, or use larger storage; do not lower coverage to make a run fit.

## Trust and validation

The image pins Debian archive keyring 2025.1 from the official Debian pool, with
its package hash checked against the signed trixie Packages index. Buildroot checks
that pinned hash and the license hash. Key rotation requires a reviewed image/keyring
update, never downloading an untrusted key to bypass gpgv failures.

Signed synthetic repository tests cover signatures, indexes, Architecture: all,
package hashes, by-hash acquisition, local copies, metadata rotation, low space,
resume, publication, service restoration and private profile rendering. Archive
readers are also checked against the available Debian installer artifacts.
The planner matched the existing signed mirror exactly: 73,030 package files and
147,307,326,386 package bytes. The archive readers matched dpkg-deb policy contents
and all 2,511 lsinitramfs entries for the available installer. Fourteen updater tests,
five profile tests and six card-migration tests passed. Buildroot keyring extraction
and installed updater import/layout checks passed.

Configuration checks used Buildroot `4ab7d13248ef9229cbd94961baec6023e6827f07`
and external base `9c81460ae7875c871b4311bb1c7c838dd86c6b92`, with
`rpi5_offline_pxe_defconfig`. Python3 (SSL/XZ/ZLIB/BZIP2), GNUPG2/GPGV and
OFFLINE_DEBIAN_KEYRING selections survive olddefconfig; rootfs remains 512M.

Kconfig/olddefconfig and host-side checks do not establish target acceptance:
the user has since confirmed Pi-side refresh and a successful PXE installation
after metadata repair. Power-cut recovery and acceptance of both disk profiles
still require explicit hardware tests. No physical disk write or
full mirror download is part of implementation testing.

## Repair generations acquired before installer Release support

Older Pi-side downloads omitted `Release` and `Release.gpg`, which Debian
Installer net-retriever requires even though APT supports InRelease. Updater
verification now requires all three files and independently verifies that their
metadata agree. Activation rejects missing pairs before stopping the old server.

With the known-good generation active and no clients installing, the updated tool
can repair an inactive, sealed generation without downloads or package copies:

```
offline-mirror-update --repair-metadata GENERATION --no-active-installers
offline-activate GENERATION --no-active-installers
```

Repair extracts release text and the existing signature from that generation's
InRelease, like debootstrap's `split_inline_sig`. It does not resign or change
Debian's metadata. Both the original clearsigned envelope and the detached pair
must verify against the image keyring, with matching parsed metadata. All three
suites are validated in scratch before committing; the existing readiness seal
must also pass. The command updates metadata entries in the readiness seal and
profile rollback seal. Private profiles, pool files and `current` stay unchanged.
The original seal is retained as `ready.sha256.before-metadata-repair`. This uses
only a few MiB of scratch storage, not another mirror generation. Repeat repair
is safe; the active generation cannot be repaired in place.

`deploy-mirror-updater.sh`, accompanied by mirror_update.py, mirror_acquire.py,
verify-mirror.py, activate-generation.sh and their files.sha256, installs a hotfix
on an existing updater image under the shared lock. It preserves the previous
code, changes no mirror contents and performs no activation. Future image builds
include the corrected files through the normal Pi 5 post-build hook.
