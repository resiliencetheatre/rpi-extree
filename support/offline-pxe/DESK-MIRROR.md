# Acquire the mirror on desk

Workstation path setup (adjust once for your checkout):

```sh
WORKSPACE=/path/to/workspace
export BR2_EXTERNAL="$WORKSPACE/rpi-extree"
```


Use the connected Debian 13 workstation. Keep `/mnt/data` mounted. No disk
formatting or repartitioning is involved. The Pi and its microSD are not involved
in acquisition. At the measured 2026-10-10 snapshot, unique packages totalled
147.31 GB (137.19 GiB); allow extra space for installer images and metadata.
The existing 100 GiB free-space reserve is appropriate for this large workstation
volume. A complete acquisition and installation have not yet been tested end to end.

Install prerequisites once:

```sh
sudo apt-get update
sudo apt-get install debmirror debian-archive-keyring ca-certificates gpgv rsync \
  python3 liblwp-protocol-https-perl libio-socket-ssl-perl initramfs-tools-core \
  dpkg-dev xz-utils gzip tar cpio util-linux
```

Check the volume is mounted, and create only our workspace owned by your user:

```sh
findmnt /mnt/data
sudo install -d -o "$(id -u)" -g "$(id -g)" /mnt/data/offline-pxe
cd "$BR2_EXTERNAL/support/offline-pxe"
./prepare-desk-mirror.sh --check
```

This creates `/mnt/data/offline-pxe/settings.json` from the repository defaults
with a unique generation name. It checks dependencies, HTTPS and signed upstream
metadata, without downloading packages. The card UUID can remain the placeholder
at this acquisition stage; fill it in before transferring/configuring the Pi's
production storage. Do not change the architecture/components to make a failed
run pass. Defaults are trixie, updates and security, amd64/all, all four components,
no sources, with installer images and udebs. Both archive runs explicitly include
all four component/debian-installer sections. Installer-image mirroring is enabled
only for the main Debian archive, never security. Because debmirror skips
*-updates installer sections, the wrapper separately fetches their signed empty
indexes and rejects unexpected nonempty content rather than omitting packages.

Start the full download explicitly (run as your normal user):

```sh
./prepare-desk-mirror.sh --download
```

Use a persistent terminal such as screen if disconnecting from desk. The wrapper
prints the log filename; logs remain under `/mnt/data/offline-pxe/logs/`. Run the
same command again after a network interruption. Keep settings and generation name
unchanged for a retry. Existing downloaded files can be reused, while indexes may
refresh for consistency. Verification hashes all referenced packages and can take
some time after network transfers finish. A checksum/signature or unsupported
installer-version failure must be investigated; do not bypass it.

A successful run prints `Verified staging generation: ...`. Its directory contains
`debian/`, `debian-security/`, `tftp/`, `www/preseed/`, `manifest.json`, and
`ready.sha256`. Confirm verification outcome:

```sh
python3 - <<'PY'
import json
from pathlib import Path
base=Path('/mnt/data/offline-pxe')
s=json.loads((base/'settings.json').read_text())
g=base/'staging'/s['generation']
m=json.loads((g/'manifest.json').read_text())
assert m['outcome']=='verified'
assert (g/'ready.sha256').is_file()
print('Verified generation:',g)
print('Package files:',m['package_files'])
print('Package bytes:',m['package_bytes'])
PY
```

This last command reports the completed host verification; it does not itself rerun
the full hash scan. Do not copy a partially downloaded tree to the Pi. Stop after
verification: transfer onto the microSD data partition and activation are separate
steps that must use the actual card partition layout. No transfer or format command
is run by this wrapper.

For a later refresh, keep the previous verified directory intact and assign a new
generation name in the desk settings file. The downloader refuses to modify a
sealed, verified generation.
