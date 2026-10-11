# Private NVMe and SATA PXE profiles

The default menu waits for selection. Both BIOS and UEFI offer:

- Offline Debian guided installation
- Interactive local installation
- NVMe unattended — replaces the explicitly configured NVMe disk
- SATA unattended — replaces the explicitly configured SATA disk

Selecting either unattended entry authorizes partition replacement without
further confirmation. Disk names come from the private input, not detection or
guessing. The supplied NVMe example selects `/dev/nvme0n1`; the SATA example
selects `/dev/sda`. Disconnect other client storage when using a path-based SATA
profile: `/dev/sda` is a Linux enumeration, not a hardware identity.

The adapter preserves each input's account, encryption, locale, tasks, packages,
hostname and poweroff choices. It replaces public mirror/NTP settings with the
offline sources and APT policy, preseeds initial network questions, and skips
the guided hostname prompt. Encrypted installation is unattended; booting the
installed encrypted OS still requires its passphrase.

## Workstation paths and private files

Set paths for your checkout and storage; none require a particular username:

```sh
WORKSPACE=/path/to/workspace
export BR2_EXTERNAL="$WORKSPACE/rpi-extree"
MIRROR_ROOT=/path/to/offline-pxe
PRIVATE_DIR="$HOME/.local/share/offline-pxe-private"
BUNDLE_DIR=/tmp/offline-storage-profiles
install -d -m 700 "$PRIVATE_DIR"
```

Keep private preseeds outside every source checkout. Copy your NVMe input into
`$PRIVATE_DIR/preseed-nvme.cfg` and SATA input into `$PRIVATE_DIR/preseed-sata.cfg`,
then chmod both to 0600. Do not paste passwords or passphrases into templates,
documentation, tests, shell command arguments, or git. Rootfs images do not need
these private files. Repository ignore rules also cover common private input and
generated names, but ignore rules do not protect a file already tracked by git.

Generate both profiles together:

```sh
python3 "$BR2_EXTERNAL/support/offline-pxe/prepare-unattended.py" \
  "$MIRROR_ROOT/settings.json" \
  --nvme-preseed "$PRIVATE_DIR/preseed-nvme.cfg" \
  --sata-preseed "$PRIVATE_DIR/preseed-sata.cfg" \
  --output "$BUNDLE_DIR" \
  --enable-destructive-profile
```

The output directory must be new and outside rpi-extree. It is private (0700),
and the archive is created with 0600 permissions. The command prints disk paths
and a bundle checksum, not account names, hostnames or credentials. No download,
image build, disk formatting or Pi mutation occurs during generation.

The default is `--default menu`: wait indefinitely for a choice. To deliberately
boot one unattended variant after ten seconds, add `--default nvme` or
`--default sata`. `--default guided` keeps the timed guided default. These are
not MAC restrictions: only attach intended installation clients while enabled.

## Fix clock tools on an existing Pi

Old RTC code can erase a manual clock acknowledgement when recovery retries a
failed RTC restore. New images include the fix. The bundle includes corrected
`offline-clock`, `offline-rtc` and `update-clock-tools.sh` for the existing image.

Serve the bundle temporarily from the workstation on the isolated LAN:

```sh
python3 -m http.server 8000 --bind WORKSTATION_LAN_IP --directory "$BUNDLE_DIR"
```

Replace WORKSTATION_LAN_IP with the workstation's 192.168.50.x address. On Pi:

```sh
mkdir -p /tmp/offline-storage-profiles
chmod 700 /tmp/offline-storage-profiles
cd /tmp/offline-storage-profiles
umask 077
for file in offline-clock offline-rtc update-clock-tools.sh deploy-unattended.sh unattended-profile.tar.gz; do
    curl -f "http://WORKSTATION_LAN_IP:8000/$file" -o "$file" || break
done
sha256sum unattended-profile.tar.gz
```

Ensure every transfer succeeded and compare the archive checksum with the host
output. The archive/preseeds contain private installation credentials served on
this isolated LAN; do not expose them to an untrusted network.

```sh
sh update-clock-tools.sh
offline-clock 'YYYY-MM-DD HH:MM:SS'
systemctl start offline-recover.timer
offline-ready
```

Replace the timestamp with actual UTC. Manual time now takes precedence over
an automatic RTC retry. RTC restore will not clear the acknowledgement or alter
the manually set clock. Once the battery is fitted and the time is correct,
`offline-rtc --enroll` writes RTC time and enables next-boot restoration. Do not
claim retention until a power-disconnection test has passed.

## Replace the old profile and enable the menu

Stop any laptop installation before switching. If a previous single-profile or
two-profile deployment is present, first disable it using the new script:

```sh
if [ -d /srv/offline/current/unattended-profile-backup ]; then
    sh deploy-unattended.sh --disable
fi
sh deploy-unattended.sh --enable-destructive-profile
systemctl is-active offline-dnsmasq offline-nginx
```

Deployment checks clock readiness before making changes. It verifies the old
generation seal, matching server/generation and the payload, takes a lock, stops
installer services, preserves control-file backups, updates the files and seal,
remounts read-only, and starts services. It uses separate gzip decompression and
plain BusyBox tar; tar's `-z` feature is not required. A failure after changes
begin leaves maintenance set and services stopped, with a diagnostic.

Profiles are stored on the mirror data partition, not in the firmware image:

| Menu selection | File under `/srv/offline/current/` | URL |
| --- | --- | --- |
| NVMe | `www/preseed/nvme.cfg` | `http://192.168.50.1/preseed/nvme.cfg` |
| SATA | `www/preseed/sata.cfg` | `http://192.168.50.1/preseed/sata.cfg` |

Stop the temporary host HTTP server after transfer, connect the intended laptop,
PXE boot and select its storage profile. The original disk path, account and
encryption values are maintained in each private generated preseed. Installer
menus and filenames use NVMe/SATA names; private hostnames need not match them.

Disable unattended entries after testing:

```sh
sh /tmp/offline-storage-profiles/deploy-unattended.sh --disable
```

The script restores previous menus/controls and their seal and removes new
profile files. Backups outside the HTTP root remain for diagnosis. `/tmp` is
volatile; retain the bundle on the workstation so the script can be recopied.
The mirror's signed indexes and package pool are unchanged throughout.

Both profiles require separate hardware acceptance tests, including encrypted
partitioning, complete package installation and poweroff. Local tests verify
rendering, disk constraints, privacy, deployment/rollback and clock precedence;
they do not prove a handsfree installation on either physical laptop.
