#!/bin/sh
#
# BusyBox-compatible Forgejo restore script for PiVault / Buildroot.
# Restores Forgejo data plus active config/service files.
#
# Usage:
#   ./forgejo-restore.sh /path/to/forgejo-YYYYMMDD-HHMMSS.tar.gz
#

set -eu

FORGEJO_SERVICE="${FORGEJO_SERVICE:-forgejo}"
BACKUP_FILE="${1:-}"
RESTORE_SAVE_OLD="${RESTORE_SAVE_OLD:-1}"

msg() { echo "==> $*"; }
warn() { echo "WARNING: $*" >&2; }
fail() { echo "ERROR: $*" >&2; exit 1; }

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

[ -n "$BACKUP_FILE" ] || fail "Usage: $0 /path/to/forgejo-backup.tar.gz"
[ -f "$BACKUP_FILE" ] || fail "Backup file not found: $BACKUP_FILE"

need_cmd gzip
need_cmd tar
need_cmd date
need_cmd mkdir
need_cmd mv
need_cmd chown
need_cmd chmod
need_cmd systemctl

TS="$(date +%Y%m%d-%H%M%S)"

msg "Backup file: $BACKUP_FILE"

if [ -f "$BACKUP_FILE.sha256" ]; then
    msg "Verifying checksum"
    oldpwd="$(pwd)"
    cd "$(dirname "$BACKUP_FILE")"
    sha256sum -c "$(basename "$BACKUP_FILE").sha256"
    cd "$oldpwd"
else
    warn "No checksum file found: $BACKUP_FILE.sha256"
fi

msg "Stopping Forgejo service: $FORGEJO_SERVICE"
systemctl stop "$FORGEJO_SERVICE" 2>/dev/null || true

if [ "$RESTORE_SAVE_OLD" = "1" ]; then
    msg "Saving old paths aside"
    [ ! -e /opt/data/forgejo ] || mv /opt/data/forgejo "/opt/data/forgejo.before-restore-$TS"
    [ ! -e /etc/forgejo ] || mv /etc/forgejo "/etc/forgejo.before-restore-$TS"
    [ ! -e /etc/systemd/system/forgejo.service ] || mv /etc/systemd/system/forgejo.service "/etc/systemd/system/forgejo.service.before-restore-$TS"
else
    warn "RESTORE_SAVE_OLD=0 set; existing files may be overwritten"
fi

msg "Extracting archive to /"
# BusyBox-compatible restore: do not use tar -z.
gzip -dc "$BACKUP_FILE" | tar -C / -xf -

msg "Fixing ownership and permissions"
[ ! -d /opt/data/forgejo ] || chown -R git:git /opt/data/forgejo
[ ! -d /etc/forgejo ] || chown -R git:git /etc/forgejo
[ ! -d /etc/forgejo ] || chmod 750 /etc/forgejo
[ ! -f /etc/forgejo/app.ini ] || chmod 640 /etc/forgejo/app.ini
[ ! -f /etc/systemd/system/forgejo.service ] || chmod 644 /etc/systemd/system/forgejo.service
[ ! -d /opt/data/forgejo/.ssh ] || chmod 700 /opt/data/forgejo/.ssh
[ ! -f /opt/data/forgejo/.ssh/authorized_keys ] || chmod 600 /opt/data/forgejo/.ssh/authorized_keys

msg "Reloading systemd"
systemctl daemon-reload

msg "Enabling Forgejo service"
systemctl enable "$FORGEJO_SERVICE" 2>/dev/null || true

msg "Starting Forgejo service: $FORGEJO_SERVICE"
systemctl start "$FORGEJO_SERVICE"

msg "Restore complete"
systemctl status "$FORGEJO_SERVICE" --no-pager || true
