# Repair missing application metadata after a Pi mirror update

A final preseed error with exit 100 and an APT 404 for
`main/dep11/icons-48x48.tar` means the updater omitted DEP-11 application
metadata. The updater now includes signed application descriptions for the
selected architectures and icon archives. Package coverage is unchanged.

Stop the failed installation before switching generations. On the Pi, install
the updated updater tools, connect Wi-Fi, and activate the previous known-good
generation. Then repair the inactive updated generation:

```sh
offline-activate trixie-20261010T121352Z --no-active-installers
offline-mirror-update --repair-appstream trixie-20261012T014154Z --no-active-installers
offline-activate trixie-20261012T014154Z --no-active-installers
offline-ready
```

Only run activation after repair succeeds. Restart the laptop's PXE installation
from the beginning to avoid mixing generations. No laptop configuration patch
is needed. Generation names above refer to the reported pair; use `--status`
for other cards.

Repair downloads only the omitted metadata, verifies its size and SHA256 against
the existing signed release, and extends the readiness seal. It does not download
another package mirror or change the active symlink. Downloads finish in scratch
before publishing files; failed downloads leave generation files unchanged.
Services pause during repair and the mount returns to read-only afterward.
The 100 GiB configured reserve still applies.

If upstream has retired the snapshot's by-hash objects, repair fails safely.
Do not substitute current metadata into the older snapshot. Create and verify a
fresh generation using the corrected updater instead, following
[MIRROR-OPERATIONS.md](MIRROR-OPERATIONS.md) for capacity and retention.

Future images include the updater correction through the existing post-build
installation. Rebuilding an image does not repair an already populated generation.

For a running Pi, build a plain tar bundle on the workstation from this directory:

```sh
mkdir -p /tmp/offline-appstream-fix
cp mirror_update.py mirror_acquire.py verify-mirror.py activate-generation.sh deploy-mirror-updater.sh /tmp/offline-appstream-fix/
cd /tmp/offline-appstream-fix
sha256sum mirror_update.py mirror_acquire.py verify-mirror.py activate-generation.sh deploy-mirror-updater.sh > files.sha256
tar -cf update.tar mirror_update.py mirror_acquire.py verify-mirror.py activate-generation.sh deploy-mirror-updater.sh files.sha256
python3 -m http.server 8000 --directory /tmp/offline-appstream-fix
```

On the Pi, replace `DESK_IP` with the workstation address reachable over Wi-Fi:

```sh
mkdir -p /tmp/offline-appstream-fix
cd /tmp/offline-appstream-fix
curl -f http://DESK_IP:8000/update.tar -o update.tar
tar -xf update.tar
sh deploy-mirror-updater.sh
```

Use a trusted maintenance LAN for this transfer. The installer checks the bundle's
file checksums and saves the previous updater code. Stop the workstation HTTP
server with Ctrl-C after transfer. Then run the repair commands above.
