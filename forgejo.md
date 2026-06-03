# Forgejo on Raspberry Pi 5 Buildroot image

This document describes the Forgejo setup, backup/restore usage, and maintenance notes for the Raspberry Pi 5 based Buildroot vault image.

The base system setup is handled by `init-vault.sh`. That script prepares the persistent data partition, the `git` runtime user, Forgejo configuration, systemd service, and system OpenSSH integration. This document focuses on how the resulting Forgejo instance is laid out and how to maintain it.

---

## Setup model

The image uses this model:

```text
Unix user running Forgejo: git
Unix user receiving SSH:  git
Forgejo web users:        independent Forgejo accounts managed in the UI
```

System OpenSSH accepts `git@HOST` connections. Forgejo manages the `git` user's `authorized_keys` file and writes forced-command entries there. Do not manually add normal unrestricted public keys to that file. Add user keys from the Forgejo web UI instead.

The normal clone style after adding a key in Forgejo is:

```sh
git clone git@vault:USER/REPO.git
```

Replace `vault`, `USER`, and `REPO` with the actual hostname, Forgejo user or organization, and repository name.

---

## Persistent storage setup

`init-vault.sh` creates a third MicroSD partition:

```text
/dev/mmcblk0p3
```

It formats it as ext4 with label:

```text
data
```

and mounts it at:

```sh
/opt/data
```

The fstab entry is expected to look like:

```fstab
LABEL=data /opt/data ext4 defaults,noatime 0 2
```

Forgejo persistent data lives under:

```sh
/opt/data/forgejo
```

Before writing persistent Forgejo state, make sure `/opt/data` is really mounted:

```sh
mount | grep ' on /opt/data '
```

or:

```sh
findmnt /opt/data
```

---

## Important paths

### Forgejo runtime/data root

```sh
/opt/data/forgejo
```

Observed runtime layout:

```text
/opt/data/forgejo/
├── certs/
├── custom/
├── data/
├── log/
└── repositories/
```

### Forgejo configuration

The `init-vault.sh` setup writes the main Forgejo config here:

```sh
/etc/forgejo/app.ini
```

Important generated settings include:

```ini
APP_NAME = vault Forgejo
RUN_USER = git
WORK_PATH = /opt/data/forgejo

[server]
APP_DATA_PATH = /opt/data/forgejo/data
DOMAIN = vault
HTTP_ADDR = 0.0.0.0
HTTP_PORT = 3000
ROOT_URL = http://vault:3000/
DISABLE_SSH = false
START_SSH_SERVER = false
SSH_DOMAIN = vault
SSH_PORT = 22
SSH_LISTEN_PORT = 22
SSH_USER = git
SSH_ROOT_PATH = /opt/data/forgejo/.ssh
SSH_CREATE_AUTHORIZED_KEYS_FILE = true
SSH_AUTHORIZED_KEYS_BACKUP = false

[database]
DB_TYPE = sqlite3
PATH = /opt/data/forgejo/data/forgejo.db
SQLITE_TIMEOUT = 500

[repository]
ROOT = /opt/data/forgejo/repositories

[log]
MODE = console
LEVEL = Info
ROOT_PATH = /opt/data/forgejo/log
```

Check the live config with:

```sh
sed -n '1,220p' /etc/forgejo/app.ini
```

or only the important paths:

```sh
grep -E '^(APP_NAME|RUN_USER|WORK_PATH|APP_DATA_PATH|DOMAIN|HTTP_PORT|ROOT_URL|DB_TYPE|PATH|ROOT|SSH_)' \
    /etc/forgejo/app.ini
```

Some older/manual experiments may also have files under:

```sh
/opt/data/forgejo/custom
```

For this image, treat `/etc/forgejo/app.ini` as the canonical service config created by `init-vault.sh`.

### Repositories

```sh
/opt/data/forgejo/repositories
```

Example:

```text
/opt/data/forgejo/repositories/resiliencetheatre/
├── forgejo-ca-toolkit.git
├── rpi-extree.git
└── testrepo.git
```

These are bare Git repositories.

### SQLite database

```sh
/opt/data/forgejo/data/forgejo.db
/opt/data/forgejo/data/forgejo.db-wal
/opt/data/forgejo/data/forgejo.db-shm
```

The presence of `forgejo.db-wal` and `forgejo.db-shm` means SQLite is using WAL mode. For simple safe backups, stop Forgejo before archiving the data tree.

### Application data

```sh
/opt/data/forgejo/data
```

This can contain:

```text
actions_artifacts/
actions_id_token/
actions_log/
attachments/
avatars/
forgejo.db
forgejo.db-shm
forgejo.db-wal
indexers/
jwt/
lfs/
packages/
queues/
repo-archive/
repo-avatars/
sessions/
tmp/
```

### SSH key file managed by Forgejo

```sh
/opt/data/forgejo/.ssh/authorized_keys
```

Permissions should be:

```sh
chmod 700 /opt/data/forgejo/.ssh
chmod 600 /opt/data/forgejo/.ssh/authorized_keys
chown -R git:git /opt/data/forgejo/.ssh
```

Do not add unrestricted keys manually. Add keys in the Forgejo web UI.

### systemd service

The service is installed as:

```sh
/etc/systemd/system/forgejo.service
```

Expected service model:

```ini
[Unit]
Description=Forgejo
After=network-online.target opt-data.mount
Wants=network-online.target
RequiresMountsFor=/opt/data/forgejo

[Service]
Type=simple
User=git
Group=git
WorkingDirectory=/opt/data/forgejo
Environment=USER=git
Environment=HOME=/opt/data/forgejo
Environment=GITEA_WORK_DIR=/opt/data/forgejo
ExecStart=/usr/bin/forgejo web --config /etc/forgejo/app.ini
Restart=always
RestartSec=2s

[Install]
WantedBy=multi-user.target
```

Check it with:

```sh
systemctl cat forgejo
```

---

## Initial setup using init-vault.sh

Run the initialization script on a freshly flashed image:

```sh
./init-vault.sh vault
```

The hostname argument becomes the local Forgejo domain and appears in clone URLs and `ROOT_URL`.

After the script runs:

```sh
systemctl start forgejo
journalctl -u forgejo -f
```

Then open:

```text
http://vault:3000/
```

During first web setup, make sure the generated paths remain aligned with `/etc/forgejo/app.ini`:

```text
Database type: SQLite3
Database path: /opt/data/forgejo/data/forgejo.db
Repository root: /opt/data/forgejo/repositories
Application data path: /opt/data/forgejo/data
Run user: git
```

After creating users in the web UI, add SSH keys through the Forgejo web UI, not by editing `/opt/data/forgejo/.ssh/authorized_keys` manually.

---

## OpenSSH hardening for git user

`init-vault.sh` appends a `Match User git` block to sshd config. The important point is that there is no global `ForceCommand` in sshd for the `git` user, because Forgejo writes its own forced commands into `authorized_keys`.

Expected block:

```sshconfig
Match User git
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    PermitTTY no
    AllowTcpForwarding no
    X11Forwarding no
    PermitTunnel no
```

Check with:

```sh
grep -A10 'Match User git' /etc/ssh/sshd_config
```

Reload sshd after changes:

```sh
systemctl reload sshd.service 2>/dev/null || systemctl reload ssh.service
```

---

# Backup

## Backup strategy

Use a cold filesystem backup:

1. Stop Forgejo.
2. Archive `/opt/data/forgejo`.
3. Also archive `/etc/forgejo` and `/etc/systemd/system/forgejo.service` when making a full instance backup.
4. Write a checksum.
5. Start Forgejo again.
6. Copy the backup off the device.

Stopping Forgejo avoids SQLite WAL consistency problems and keeps repositories, database, attachments, LFS objects, avatars, packages, certificates, and config in a consistent state.

Do not copy only:

```sh
/opt/data/forgejo/data/forgejo.db
```

Recent transactions may be in:

```sh
/opt/data/forgejo/data/forgejo.db-wal
```

The safest small-system backup is the whole stopped-service instance.

---

## BusyBox tar note

On this Buildroot image, BusyBox `tar` may not support gzip directly:

```text
tar: invalid option -- 'z'
```

Do not rely on:

```sh
tar -czf backup.tar.gz directory
```

Use this portable pattern instead:

```sh
tar -cf - directory | gzip -c > backup.tar.gz
```

To list contents:

```sh
gzip -dc backup.tar.gz | tar -tf -
```

To extract:

```sh
gzip -dc backup.tar.gz | tar -xf -
```

---

## Backup script usage

Install the backup script as:

```sh
/usr/local/sbin/forgejo-backup.sh
```

Make it executable:

```sh
chmod +x /usr/local/sbin/forgejo-backup.sh
```

Run manually:

```sh
/usr/local/sbin/forgejo-backup.sh
```

Default output location:

```sh
/opt/data/backups/forgejo/forgejo-YYYYMMDD-HHMMSS.tar.gz
/opt/data/backups/forgejo/forgejo-YYYYMMDD-HHMMSS.tar.gz.sha256
```

Recommended BusyBox-compatible backup script:

```sh
#!/bin/sh
set -eu

FORGEJO_SERVICE="${FORGEJO_SERVICE:-forgejo}"
FORGEJO_ROOT="${FORGEJO_ROOT:-/opt/data/forgejo}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/data/backups/forgejo}"
KEEP_DAYS="${KEEP_DAYS:-14}"

TS="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_ROOT/forgejo-$TS.tar.gz"
TMPDIR="$BACKUP_ROOT/.tmp-forgejo-backup-$TS"

mkdir -p "$BACKUP_ROOT"
rm -rf "$TMPDIR"
mkdir -p "$TMPDIR"

cleanup() {
    rm -rf "$TMPDIR"
}
trap cleanup EXIT INT TERM

echo "== Forgejo backup =="
echo "Forgejo data: $FORGEJO_ROOT"
echo "Output:       $OUT"

echo "Stopping Forgejo service..."
systemctl stop "$FORGEJO_SERVICE"

# Include non-/opt config needed to recreate the running instance.
mkdir -p "$TMPDIR/etc" "$TMPDIR/systemd"
[ -d /etc/forgejo ] && cp -a /etc/forgejo "$TMPDIR/etc/"
[ -f /etc/systemd/system/forgejo.service ] && \
    cp -a /etc/systemd/system/forgejo.service "$TMPDIR/systemd/forgejo.service"

echo "Checking SQLite files before backup..."
ls -lh "$FORGEJO_ROOT/data"/forgejo.db* 2>/dev/null || true

echo "Creating archive..."
(
    cd /opt/data
    tar -cf - forgejo | gzip -c > "$OUT.data.tmp"
)

# Append extra config by making one staging archive layout.
# Simpler and more predictable: build a staging tree, then archive it.
rm -f "$OUT.data.tmp"
mkdir -p "$TMPDIR/opt/data"
cp -a "$FORGEJO_ROOT" "$TMPDIR/opt/data/forgejo"

(
    cd "$TMPDIR"
    tar -cf - opt etc systemd | gzip -c > "$OUT"
)

echo "Writing checksum..."
sha256sum "$OUT" > "$OUT.sha256"

echo "Starting Forgejo service..."
systemctl start "$FORGEJO_SERVICE"

echo "Pruning old backups..."
find "$BACKUP_ROOT" -type f -name 'forgejo-*.tar.gz' -mtime +"$KEEP_DAYS" -delete
find "$BACKUP_ROOT" -type f -name 'forgejo-*.tar.gz.sha256' -mtime +"$KEEP_DAYS" -delete

echo "Done."
ls -lh "$OUT" "$OUT.sha256"
```

The archive layout created by this script is:

```text
opt/data/forgejo/
etc/forgejo/
systemd/forgejo.service
```

This makes restore clearer than a bare `forgejo/` archive.

---

## Verify backup

List archive contents:

```sh
gzip -dc /opt/data/backups/forgejo/forgejo-YYYYMMDD-HHMMSS.tar.gz | tar -tf - | head -80
```

Expected entries:

```text
opt/data/forgejo/
opt/data/forgejo/data/forgejo.db
opt/data/forgejo/repositories/
etc/forgejo/app.ini
systemd/forgejo.service
```

Verify checksum:

```sh
cd /opt/data/backups/forgejo
sha256sum -c forgejo-YYYYMMDD-HHMMSS.tar.gz.sha256
```

Expected result:

```text
forgejo-YYYYMMDD-HHMMSS.tar.gz: OK
```

---

## Optional systemd timer for automatic backup

Create service:

```sh
cat > /etc/systemd/system/forgejo-backup.service <<'EOF_SERVICE'
[Unit]
Description=Backup Forgejo

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/forgejo-backup.sh
EOF_SERVICE
```

Create timer:

```sh
cat > /etc/systemd/system/forgejo-backup.timer <<'EOF_TIMER'
[Unit]
Description=Run Forgejo backup daily

[Timer]
OnCalendar=*-*-* 03:20:00
Persistent=true

[Install]
WantedBy=timers.target
EOF_TIMER
```

Enable:

```sh
systemctl daemon-reload
systemctl enable --now forgejo-backup.timer
```

Check:

```sh
systemctl list-timers | grep forgejo
```

---

# Restore

## Restore strategy

A restore should:

1. Stop Forgejo.
2. Move the current `/opt/data/forgejo` tree aside.
3. Restore `/opt/data/forgejo` from backup.
4. Restore `/etc/forgejo` if present in the backup.
5. Restore `/etc/systemd/system/forgejo.service` if present in the backup.
6. Fix ownership.
7. Reload systemd.
8. Start Forgejo.

If you are restoring onto a freshly flashed image, run `init-vault.sh` first to create and mount `/opt/data`, create the `git` user, and prepare the base service model. Then run the restore script to replace the fresh Forgejo tree with the saved one.

---

## Restore script usage

Install the restore script as:

```sh
/usr/local/sbin/forgejo-restore.sh
```

Make it executable:

```sh
chmod +x /usr/local/sbin/forgejo-restore.sh
```

Restore from backup:

```sh
/usr/local/sbin/forgejo-restore.sh /opt/data/backups/forgejo/forgejo-YYYYMMDD-HHMMSS.tar.gz
```

Recommended BusyBox-compatible restore script:

```sh
#!/bin/sh
set -eu

FORGEJO_SERVICE="${FORGEJO_SERVICE:-forgejo}"
FORGEJO_ROOT="${FORGEJO_ROOT:-/opt/data/forgejo}"
RESTORE_PARENT="${RESTORE_PARENT:-/}"
FORGEJO_USER="${FORGEJO_USER:-git}"
FORGEJO_GROUP="${FORGEJO_GROUP:-git}"

usage() {
    echo "Usage: $0 /path/to/forgejo-YYYYMMDD-HHMMSS.tar.gz" >&2
    exit 1
}

[ $# -eq 1 ] || usage

BACKUP_FILE="$1"

[ -f "$BACKUP_FILE" ] || {
    echo "Backup file not found: $BACKUP_FILE" >&2
    exit 1
}

case "$BACKUP_FILE" in
    *.tar.gz) ;;
    *)
        echo "Backup file should be a .tar.gz archive" >&2
        exit 1
        ;;
esac

TS="$(date +%Y%m%d-%H%M%S)"
OLD_FORGEJO="$FORGEJO_ROOT.before-restore.$TS"
OLD_ETC="/etc/forgejo.before-restore.$TS"
OLD_SERVICE="/etc/systemd/system/forgejo.service.before-restore.$TS"

echo "== Forgejo restore =="
echo "Backup: $BACKUP_FILE"
echo "Target: $FORGEJO_ROOT"

echo "Checking archive contents..."
gzip -dc "$BACKUP_FILE" | tar -tf - | grep -q '^opt/data/forgejo/' || {
    echo "Archive does not contain opt/data/forgejo/" >&2
    exit 1
}

echo "Stopping Forgejo service..."
systemctl stop "$FORGEJO_SERVICE" 2>/dev/null || true

if [ -d "$FORGEJO_ROOT" ]; then
    echo "Moving existing Forgejo tree aside: $OLD_FORGEJO"
    mv "$FORGEJO_ROOT" "$OLD_FORGEJO"
fi

if [ -d /etc/forgejo ]; then
    echo "Moving existing /etc/forgejo aside: $OLD_ETC"
    mv /etc/forgejo "$OLD_ETC"
fi

if [ -f /etc/systemd/system/forgejo.service ]; then
    echo "Saving existing forgejo.service: $OLD_SERVICE"
    mv /etc/systemd/system/forgejo.service "$OLD_SERVICE"
fi

echo "Extracting backup into / ..."
gzip -dc "$BACKUP_FILE" | tar -C "$RESTORE_PARENT" -xf -

if [ ! -d "$FORGEJO_ROOT" ]; then
    echo "Restore failed: $FORGEJO_ROOT does not exist after extraction" >&2
    exit 1
fi

echo "Installing systemd service if backup used staging path..."
if [ -f /systemd/forgejo.service ]; then
    mkdir -p /etc/systemd/system
    cp /systemd/forgejo.service /etc/systemd/system/forgejo.service
    rm -rf /systemd
fi

echo "Fixing ownership..."
chown -R "$FORGEJO_USER:$FORGEJO_GROUP" "$FORGEJO_ROOT"
[ -d /etc/forgejo ] && chown -R "$FORGEJO_USER:$FORGEJO_GROUP" /etc/forgejo

echo "Reloading systemd..."
systemctl daemon-reload

echo "Starting Forgejo service..."
systemctl start "$FORGEJO_SERVICE"

echo "Restore complete."
echo "Previous data tree, if any: $OLD_FORGEJO"
echo "Previous config, if any:    $OLD_ETC"
echo "Previous service, if any:   $OLD_SERVICE"
echo "Check service status with:"
echo "  systemctl status $FORGEJO_SERVICE"
echo "  journalctl -u $FORGEJO_SERVICE -n 100 --no-pager"
```

---

## Restore checks

After restore:

```sh
systemctl status forgejo
journalctl -u forgejo -n 100 --no-pager
```

Check config:

```sh
ls -l /etc/forgejo/app.ini
sed -n '1,220p' /etc/forgejo/app.ini
```

Check repository tree:

```sh
ls -l /opt/data/forgejo/repositories
ls -l /opt/data/forgejo/repositories/resiliencetheatre
```

Check SQLite files:

```sh
ls -lh /opt/data/forgejo/data/forgejo.db*
```

Check ownership:

```sh
find /opt/data/forgejo \( ! -user git -o ! -group git \) -print
```

If the command prints files, fix with:

```sh
chown -R git:git /opt/data/forgejo
```

---

# Maintenance notes

## Service status

```sh
systemctl status forgejo
journalctl -u forgejo -n 100 --no-pager
```

Follow logs live:

```sh
journalctl -u forgejo -f
```

## Logs

Forgejo log directory:

```sh
/opt/data/forgejo/log
```

Systemd journal:

```sh
journalctl -u forgejo --no-pager
```

## SQLite integrity check

Include `sqlite3` in the Buildroot image if you want local integrity checks.

Stop Forgejo first:

```sh
systemctl stop forgejo
sqlite3 /opt/data/forgejo/data/forgejo.db 'PRAGMA integrity_check;'
systemctl start forgejo
```

Expected output:

```text
ok
```

## Repository check

Single repository example:

```sh
cd /opt/data/forgejo/repositories/resiliencetheatre/rpi-extree.git
git fsck --full
```

All repositories:

```sh
find /opt/data/forgejo/repositories -name '*.git' -type d | while read repo; do
    echo "== $repo =="
    git -C "$repo" fsck --full || exit 1
done
```

## Disk usage

```sh
du -sh /opt/data/forgejo

du -sh /opt/data/forgejo/repositories \
       /opt/data/forgejo/data/lfs \
       /opt/data/forgejo/data/attachments \
       /opt/data/forgejo/data/packages \
       /opt/data/forgejo/data/actions_artifacts 2>/dev/null
```

## Backup storage warning

A backup stored only on the same SD card does not protect against media failure.

Recommended pattern:

```text
Daily local backup under /opt/data/backups/forgejo
Regular rsync pull to laptop or another trusted machine
Occasional restore test to spare image or test rootfs
```

Example pull from laptop:

```sh
rsync -av root@vault:/opt/data/backups/forgejo/ ./forgejo-backups/
```

Or push from the device:

```sh
rsync -av /opt/data/backups/forgejo/ user@backup-host:/path/to/forgejo-backups/
```

## Security key / WebAuthn notes

Forgejo security-key authentication depends on the browser, OS USB/HID access, udev rules, and the web origin used to access Forgejo.

If security-key login works on one laptop but not another, compare:

```text
Firefox version
Firefox WebAuthn settings
udev rules for security keys
whether other WebAuthn websites work
whether the Forgejo URL/origin is exactly the same
whether the local CA is trusted by that browser, if HTTPS is used
```

A browser-side error like:

```text
the request is not allowed by the user agent or the platform in the current context
```

often points to browser/platform/origin policy rather than repository storage.

## Git hook shell note

Some Forgejo-generated hooks may use:

```sh
#!/usr/bin/env bash
```

On a minimal Buildroot image without Bash, Git pushes can fail with an error like:

```text
env: can't execute 'bash': No such file or directory
pre-receive hook declined
```

Options:

1. Include Bash in the Buildroot image.
2. Patch hook generation if appropriate.
3. Replace existing hook shebangs only if the hook content is POSIX shell compatible.

Check existing hooks:

```sh
find /opt/data/forgejo/repositories -path '*/hooks/pre-receive' -type f -exec head -n 1 {} \;
```

## Ownership

Forgejo data should be owned by `git:git`:

```sh
chown -R git:git /opt/data/forgejo
```

Config generated by `init-vault.sh` is also owned by `git:git`:

```sh
chown -R git:git /etc/forgejo
```

Check for ownership drift:

```sh
find /opt/data/forgejo \( ! -user git -o ! -group git \) -print
```

## Permissions

Repository permissions like this are normal:

```text
drwxr-xr-x git git forgejo-ca-toolkit.git
drwxr-xr-x git git rpi-extree.git
drwxr-xr-x git git testrepo.git
```

Private runtime directories may be stricter, for example:

```text
indexers/
sessions/
```

Do not blindly chmod everything to world-writable.

## Recommended routine

After important repository or configuration changes:

```sh
/usr/local/sbin/forgejo-backup.sh
```

Weekly or occasionally:

```sh
cd /opt/data/backups/forgejo
sha256sum -c forgejo-YYYYMMDD-HHMMSS.tar.gz.sha256
gzip -dc forgejo-YYYYMMDD-HHMMSS.tar.gz | tar -tf - | head
```

Occasionally test a restore on a spare image or spare `/opt/data` tree.

The real proof of a backup is a successful restore.
