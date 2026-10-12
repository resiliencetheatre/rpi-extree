# Pi 5 manual upstream refresh — proposed design

Status: implemented in source; see PI5-MANUAL-REFRESH.md for the supported commands
and validation limits. Hardware acceptance remains outstanding.
No timer, cron job, boot-triggered download or automatic activation is included.

## Operator interface

```
offline-mirror-update --check
offline-mirror-update --no-active-installers
offline-mirror-update --status
offline-mirror-update --resume GENERATION --no-active-installers
offline-activate GENERATION --no-active-installers
```

`--check` fetches small authenticated metadata to report scope, estimated required
storage and connectivity; it does not download packages or stop PXE services.
The normal update creates a unique staging generation and prints progress and a
bounded log location. Resume selects an existing incomplete generation explicitly.
After successful verification the command reports the activation command; it does
not switch `current`. Activation remains an explicit installation-session boundary.

The first version requires a maintenance window: no running laptop installations.
It pauses PXE/HTTP service during the update, then restores service of the old
generation. A long download therefore makes installation unavailable. Existing
offline APT clients also lose access during that window. Live serving while writing
through a separate mount is outside the first version's scope.

## Image changes

Pi 5 only: add Python 3 with TLS, zlib, xz and required package decompression
support, gpgv, and a pinned Debian archive public keyring with verified provenance.
Use existing curl, CA certificates, storage tools and systemd. Resolve symbols in
the checked-out Buildroot tree, run olddefconfig, and test actual target binaries.
Keep boot/root partitions at 128/512 MiB; measure rootfs usage before acceptance.
No apt, target dpkg installation, Perl, debmirror, container or Debian chroot.

Implement a streaming Python acquisition engine and share verification primitives
with the workstation verifier. The current verifier cannot run unchanged: it
invokes dpkg-deb and lsinitramfs. Refactor its package inspection and concatenated
initramfs inspection into bounded, tested readers (including compression variants),
or package narrowly scoped inspection helpers. Unsupported formats fail closed.
Do not omit the existing installer-version, 50mirror hash or NIC-firmware checks.
Make staging verification repeatable; it currently removes seals and regenerates
TFTP content and is not a general idempotent resume operation.

## Acquisition and authenticity

Read the installed site settings; retain trixie, trixie-updates, trixie-security,
amd64 plus all, all four components, udebs and authenticated installer images.
Sources/i386 remain explicit additions. Never reduce scope to fit storage.

1. Check configured ext4 UUID, acknowledged UTC/RTC, Wi-Fi association, upstream
   route through wlan0, DNS and verified HTTPS. Reject conflicting LAN subnets.
   Restrict updater egress to the Wi-Fi interface, including redirect/retry paths;
   do not enable forwarding/NAT or change the isolated LAN DHCP/DNS contract.
2. Fetch and verify signed Release/InRelease metadata using the pinned keyring.
   Validate codename, date and validity for a fresh upstream acquisition. An expired
   local snapshot remains usable offline, but is not proof of a successful refresh.
   Compare against the last accepted release dates to reject metadata rollback.
3. Fetch indexes authenticated by those releases, preferring signed by-hash paths
   when available. Stream Packages indexes, include Architecture: all and all signed
   applicable installer indexes, and deduplicate file requirements by path/hash.
   Include metadata needed by the existing installation and later APT contract,
   not just pool files. Preserve upstream signatures and local per-source expiry
   policy without modifying Release contents.
4. Reuse matching files from the active generation by copying into staging after
   checking hashes. Never hardlink mutable files or write into the active tree.
   Download missing files over HTTPS into temporary names; bounded retries,
   resumable partials and final size/SHA256 verification precede atomic rename.
   Restart a partial if HTTP Range is unsupported or its expected hash changes.
5. Download installer images and establish the existing signed checksum trust
   chain. Generate boot trees only after validating installer compatibility.
6. Run full destination verification of all selected indexes and referenced pool
   files. Recheck upstream metadata for rotation; restart affected acquisition
   state with a bounded retry policy if consistency cannot be established. An
   unavailable old pool file is a retry/failure, never a silently omitted package.
7. Write manifest and readiness seal last, fsync files/directories, then rename
   staging into generations on the same filesystem. Keep current unchanged.

Constrain archive URLs/redirects to approved HTTPS upstreams. Reject path traversal,
escaping symlinks, malicious archive entries, duplicate conflicting metadata and
unbounded decompression. Do not execute downloaded package maintainer scripts.
Key rotation requires an authenticated keyring/image update, never accepting a key
merely because it arrived with a failing signature.

## Space and storage lifecycle

Use `/srv/offline/.staging/GENERATION` and the existing
`/srv/offline/generations/GENERATION` layout. Store journal/state and bounded logs
outside the served generation roots; no mirror data in rootfs or /tmp.

Budget a complete additional generation, metadata, temporary files and a reserve;
do not assume ext4 reflinks or promise only changed-package storage. Reusing local
files saves bandwidth but this initial copy-based design still writes another full
generation. Compute unique required bytes from signed indexes, account for existing
verified staging files, and continuously check free space. Report byte estimates
before stopping services. Never delete the active or previous generation to fit.
The existing 100 GiB reserve may prevent a third retained generation on a 512 GB
card; report this clearly. Cleanup must be an explicit separate administrator action
which rejects current, staging-in-use and rollback-protected generations.

Hold the existing activation lock for all write operations, coordinated with
deployment, recovery and storage scripts. Persist an update transaction record
before remounting read-write. Set maintenance, stop recovery timer/service and
installer services, then remount the data filesystem read-write. On success or
controlled failure, sync, restore read-only, clear maintenance only when safe, and
restore prior service/timer state after readiness checks. Failure leaves staging
resumable and the old generation unchanged. If read-only restoration fails, keep
installer services stopped and report the cause.

The persistent record is necessary because /run disappears on power loss. Boot
recovery performs no downloads: it reconciles interrupted transactions, mounts
read-only and verifies the old active generation before serving. It never promotes
an unsealed staging directory. If storage integrity or publication state is
ambiguous, fail visibly. SIGINT and termination use the same cleanup path.

## Private NVMe/SATA profiles

New generations must not silently revert to a stock menu or copy old generated
hooks whose assumptions may differ. Preserve private source profiles and explicit
disk/default selections in a root-only persistent directory outside HTTP/TFTP
roots on partition 3. Provide an explicit import operation for those inputs; do
not assume old deployed files are valid source templates. Never commit secrets or
include them in logs or public status output.

Render both profiles against the newly verified installer using the existing
adapter policy. Preserve the operator's selected menu default; wait-for-selection
is the default for new configurations. Detect existing unattended deployment: if
private source inputs are unavailable or incompatible, refuse activation readiness
and explain what must be imported. Do not silently discard or weaken a profile.
Include generated controls in the seal, with deployment rollback support.

## Implementation and acceptance

1. Refactor reusable verification/installer inspection; keep desk workflow passing.
2. Add Pi-only runtime dependencies and authenticated keyring packaging; prove
   package formats and crypto on AArch64 while retaining partition sizes.
3. Implement planning, streaming acquisition, resume and manifests with synthetic
   signed fixture repositories; then implement maintenance/crash recovery.
4. Integrate private profile regeneration, explicit activation and status reporting.
5. Test wrong signatures/hashes, upstream rotation/404, expired/future metadata,
   Wi-Fi loss, low space, interrupted copies, signals, reboot/power loss and lock
   contention. Assert the active generation's files and current link stay unchanged.
6. On Pi 5, run a real refresh with measured bandwidth/time/space, reboot and
   resume, activate manually, disconnect Wi-Fi, then test SATA/NVMe PXE installation
   and later offline apt. Report Secure Boot separately. No scheduled update unit
   should be installed or enabled.

Hardware testing and the full mirror run remain explicit operations; this design
does not authorize an unattended download or physical disk modification.
