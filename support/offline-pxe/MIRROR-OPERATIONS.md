# Pi 5 mirror updates: an operator guide

This guide is for the working Pi 5 appliance. Run commands on the Pi as root unless
stated otherwise. You do not rebuild the firmware or move the microSD card for a
normal mirror update. Nothing downloads or switches generations automatically.

## What a generation means

A **generation** is one complete, verified snapshot: Debian packages, signed package
indexes, installer boot files, and the NVMe/SATA installation profiles together.
Its name identifies a directory. The timestamp is its creation/start time, not a
promise that every upstream package was published at that moment.

Your two generations are:

| Generation | What it represents |
| --- | --- |
| `trixie-20261010T121352Z` | Original mirror prepared on desk |
| `trixie-20261012T014154Z` | Mirror refreshed on Pi 5, repaired and successfully used for installation |

They live under `/srv/offline/generations/`. The link `/srv/offline/current` selects
which one the Pi serves. Always check it rather than assuming the newest directory
is active:

```sh
readlink /srv/offline/current
offline-mirror-update --status
```

A download first goes into `/srv/offline/.staging/NAME`. Only after successful
verification does it become `/srv/offline/generations/NAME`. It is then **available**,
but is not **active** until you activate it. Switching `current` does not copy or
merge packages and frees no space. Deleting an unused generation frees space.

The normal cycle is:

**Check space → prepare a new generation → activate it → test installation →
retain the old one temporarily → remove an obsolete generation before the next update.**

## What your current disk usage means

Your reported `df -h` on 2026-10-13 shows:

| Filesystem | Total | Used | Free | Purpose |
| --- | ---: | ---: | ---: | --- |
| `/` | 487.6 MiB | 193.0 MiB | 258.7 MiB | Buildroot OS, tools and local configuration |
| `/srv/offline` | 468.3 GiB | 277.0 GiB | 191.3 GiB | Both full mirror generations and small supporting files |
| `/run`, `/tmp`, `/dev/shm` | RAM-backed | Varies | Varies | Temporary runtime data; not extra mirror storage |

`df -h` labels binary GiB as `G`. A marketed 512 GB card has fewer binary GiB, and
partition/filesystem overhead further reduces available data capacity. Your
468.3 GiB data filesystem is consistent with this layout.

The mirror does not consume the 512 MiB root partition. Updating Debian packages
will not normally grow rootfs by hundreds of GB. Rootfs and mirror are separate
partitions; their free space cannot simply be added together.

Each current generation occupies roughly **138–140 GiB** including metadata and
installer files. Measure your actual directories with:

```sh
du -sh /srv/offline/generations/*
du -sh /srv/offline/.staging
```

The second command may say the directory does not exist if no staging directory
has been created. A retained interrupted staging directory also consumes space.
Do not delete the one you intend to resume.

Unchanged packages are **copied** from the active generation to save Internet
traffic. They still occupy space in each generation: the updater does not use
hardlinks, reflinks, or incremental storage.

### Can you start another update right now?

**Not with both current generations retained and the default reserve.**

The updater keeps a **100 GiB free-space reserve**. This is a threshold, not a
hidden 100 GiB file or partition. A fresh generation needs approximately another
138–140 GiB, so it needs roughly **239–241 GiB free** including reserve and planning
overhead. You currently have **191.3 GiB free**, approximately 48–50 GiB too little.
`offline-mirror-update --check` is the authoritative estimate for the next run.

| Situation, assuming similar snapshot sizes | Approximate used | Approximate free | Next update with 100 GiB reserve |
| --- | ---: | ---: | --- |
| One generation retained | 138–140 GiB | 328–330 GiB | Should fit |
| Your current two generations | 277 GiB | 191.3 GiB | Will not fit a fresh third generation |
| Three generations, ignoring reserve | About 416 GiB | About 52 GiB | Below the configured reserve |

After confirming the new generation works, removing the obsolete old generation
should bring free space back to roughly **330 GiB**. The next update can then keep
your current working generation while preparing its replacement. Once that update
finishes you will have two again. Repeat the same retention cycle.

This means giving up the *older* rollback copy before starting another update;
you still retain the current, tested working generation throughout acquisition.
To retain two completed generations while building a third with the same reserve,
use larger storage. Do not assume 512 GB accommodates unlimited updates/history.
Actual package growth and staging files affect all estimates.

## The commands you normally need

| Command | What it does | Changes active generation? |
| --- | --- | --- |
| `offline-mirror-update --status` | Lists active, staged and completed generations, plus free bytes | No |
| `offline-mirror-update --check` | Checks Wi-Fi/HTTPS, signed indexes, profiles and estimated capacity | No |
| `offline-mirror-update --no-active-installers` | Prepares and verifies a new full generation | No |
| `offline-mirror-update --resume NAME --no-active-installers` | Continues an interrupted staged generation | No |
| `offline-activate NAME --no-active-installers` | Switches the served snapshot to an existing verified generation | **Yes** |
| `offline-ready` | Checks mount, clock and active generation readiness | No |

`--no-active-installers` is **your assertion** that no clients are installing or
using offline APT. It does not detect clients for you. Finish/stop those operations
before updating, switching or deleting a generation. Do not switch while a laptop
is between installer screens: it could mix files from two snapshots.

## Step 1: prepare and check

Check which generation is active and how much storage remains:

```sh
offline-mirror-update --status
df -h /srv/offline
offline-ready
```

Connect Wi-Fi if needed:

```sh
iwctl station wlan0 show
iwctl station wlan0 scan
iwctl station wlan0 get-networks
iwctl station wlan0 connect "YOUR_SSID"
```

The connection command prompts for the password. Saved networks normally reconnect.
The Wi-Fi subnet must differ from the PXE LAN's `192.168.50.0/24`. Correct UTC from
the RTC or the documented `offline-clock` workflow is required for HTTPS.

Then run:

```sh
offline-mirror-update --check
```

This fetches metadata/indexes, not the complete package mirror, and leaves PXE
running. If it reports insufficient space, resolve retention first. Do not ignore
a signature or profile error. Your already-imported private profiles remain on
partition 3 and need not be imported again for each update.

## Step 2: prepare the new snapshot

With no client installations or offline APT operations running:

```sh
offline-mirror-update --no-active-installers
```

Write down the printed `Staging generation: NAME`. Leave the Pi powered and the
command running. PXE/HTTP service pauses while the partition is writable. Downloads,
local copies and complete hashing can take hours, especially on a slow Wi-Fi link
or microSD card. `Packages: .../...` is progress, not final success.

Success is the final **`Verified generation: NAME`** message. The updater restores
the read-only mount and serves the old generation again. It prints the activation
command for the new generation. You can choose to activate later.

If interrupted, use the same name:

```sh
offline-mirror-update --status
offline-mirror-update --resume NAME --no-active-installers
```

Replace `NAME` with the actual `Staging` name; do not type it literally. Resume
reuses already-verified staged packages. It does not need another full generation
beside that staging directory. A fresh `--check` estimates a fresh generation,
not the remaining bytes of a partially completed resume.

An "upstream metadata changed" failure also calls for resume. Do not repeatedly
start new generations: that leaves partial copies consuming space. If rotation
continues to prevent completion, retain staging and investigate rather than
bypassing verification.

## Step 3: switch to the new generation

With no installation or offline APT session running:

```sh
offline-activate NAME --no-active-installers
readlink /srv/offline/current
offline-ready
systemctl is-active offline-dnsmasq offline-nginx
curl -fI http://192.168.50.1/debian/dists/trixie/Release
curl -fI http://192.168.50.1/debian/dists/trixie/Release.gpg
```

Use the exact name reported as verified. Both services should be `active`, both
HTTP requests should return 200, and `readlink` should name the new generation.
The activation command stops services, checks the generation, switches the link,
restores the read-only mount and starts services. It does not download anything.

Start a fresh PXE boot and select the intended NVMe or SATA profile. Those choices
replace the configured client disk. Test the relevant laptop installation and,
after installation, local `apt update` and a package install. Disconnecting Wi-Fi
for this test proves the client can use the local mirror independently of upstream.
Keep the previous generation until testing succeeds.

## Roll back if needed

Finish or abandon the failing client installation first. Activate the previous
known-good name exactly the same way:

```sh
offline-activate trixie-20261010T121352Z --no-active-installers
offline-ready
readlink /srv/offline/current
```

That name is your current historical example, not a permanent rollback alias.
Use a generation that still exists and that you have tested. Restart the laptop's
PXE boot from the beginning after switching. Keep the failing generation and its
logs for diagnosis; do not immediately delete it.

## Free space by removing one obsolete generation

Nothing prunes generations automatically. Removal is permanent on the card: you
lose that generation's rollback option. A copy on desk remains independent.
After successful installation from `trixie-20261012T014154Z`, the original
`trixie-20261010T121352Z` is a possible removal candidate if you no longer need it.
First check `--status` and `readlink`: **never remove the active generation**.

The following is an optional, explicit maintenance operation on the Pi. It removes
only the exact old name shown, checks the configured mount UUID, holds the shared
lock, stops services and restores a read-only mount afterward. Run the entire
parenthesized block, with no clients installing or using APT. It refuses if that
old generation is active or another maintenance transaction is present.

```sh
(
    set -eu
    old=/srv/offline/generations/trixie-20261010T121352Z
    . /etc/offline-pxe/runtime.conf
    [ "$(findmnt -rn -M /srv/offline -o UUID)" = "$SSD_UUID" ]
    exec 9>/run/offline-pxe/activation.lock
    flock -n 9
    offline-ready
    [ "$(readlink -f "$old")" = "$old" ]
    [ "$(readlink -f /srv/offline/current)" != "$old" ]
    [ -f "$old/manifest.json" ]
    [ -f "$old/ready.sha256" ]
    restore() {
        sync
        if mount -o remount,ro /srv/offline; then
            rm -f /run/offline-pxe/maintenance
            systemctl start offline-recover.timer
            if offline-ready; then
                systemctl start offline-dnsmasq offline-nginx
            fi
        else
            echo 'Could not restore read-only mount; services remain stopped.' >&2
        fi
    }
    : > /run/offline-pxe/maintenance
    trap restore EXIT
    trap 'exit 1' INT TERM
    systemctl stop offline-recover.timer offline-recover.service
    systemctl stop offline-dnsmasq offline-nginx
    mount -o remount,rw /srv/offline
    rm -rf -- "$old"
)
```

Then check:

```sh
df -h /srv/offline
offline-mirror-update --status
offline-ready
```

For later cleanup, edit only the `old=` line to the exact obsolete generation you
intend to remove. Do not replace it with a wildcard, `/srv/offline/current`,
`/srv/offline/generations`, or `/srv/offline` itself. Do not remove `.private-profiles`;
it holds your original private installation inputs. Staging cleanup is a separate
decision: retain any generation you plan to resume.

## Commands that are not part of every update

- **Buildroot/migration scripts:** update the Pi firmware/rootfs, not the Debian
  repository. Routine mirror updates need neither a rebuild nor a card reflash.
- **`--import-profiles`:** needed once, or when changing your original NVMe/SATA
  inputs or menu default. New snapshots regenerate these saved profiles.
- **`--repair-metadata`:** the one-time fix for generations produced by the older
  updater that omitted Release/Release.gpg. Yours has been repaired and used for a
  successful installation. Corrected future updates include those files normally.
- **`--recover`:** restores local service state after interrupted maintenance;
  it does not download packages, resume acquisition or switch generations.

Implementation details, profile import and older-generation repair are in
[PI5-MANUAL-REFRESH.md](PI5-MANUAL-REFRESH.md). Initial mirror population on desk is
covered in [DESK-MIRROR.md](DESK-MIRROR.md).

Hardware progress: the user reports a successful Pi-side refresh and successful
PXE installation after the metadata repair. This does not establish Secure Boot,
both disk profiles, expired-metadata installation or power-cut recovery acceptance.

For a final installer APT error mentioning `dep11/icons-48x48.tar`, see
[repairing missing application metadata](REPAIR-APPSTREAM.md).
