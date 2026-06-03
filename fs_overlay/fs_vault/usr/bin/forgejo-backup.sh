#!/bin/sh
#
# BusyBox-compatible Forgejo backup script for PiVault / Buildroot.
# Archives Forgejo data plus active config/service files.
#
# No tar -z and no find -delete are used.
#

set -eu

FORGEJO_SERVICE="${FORGEJO_SERVICE:-forgejo}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/data/backups/forgejo}"
KEEP_DAYS="${KEEP_DAYS:-14}"

TS="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_ROOT/forgejo-$TS.tar.gz"
MANIFEST="$BACKUP_ROOT/forgejo-$TS.MANIFEST.txt"

PATHS="
/opt/data/forgejo
/etc/forgejo
/etc/systemd/system/forgejo.service
/etc/ssh/sshd_config
/etc/fstab
/etc/hostname
"

msg() { echo "==> $*"; }
warn() { echo "WARNING: $*" >&2; }
fail() { echo "ERROR: $*" >&2; exit 1; }

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

need_cmd tar
need_cmd gzip
need_cmd sha256sum
need_cmd mkdir
need_cmd date
need_cmd find
need_cmd rm
need_cmd systemctl

mkdir -p "$BACKUP_ROOT"

msg "Backup paths:"
for p in $PATHS; do
    echo "  $p"
done

msg "Stopping Forgejo service: $FORGEJO_SERVICE"
systemctl stop "$FORGEJO_SERVICE"

msg "Checking SQLite files"
ls -lh /opt/data/forgejo/data/forgejo.db* 2>/dev/null || true

# Create list of existing paths, relative to /.
TMP_LIST="/tmp/forgejo-backup-paths.$$"
: > "$TMP_LIST"
for p in $PATHS; do
    if [ -e "$p" ]; then
        # Strip leading slash because tar -C / expects relative paths.
        echo "${p#/}" >> "$TMP_LIST"
    else
        warn "Path missing, skipping: $p"
    fi
done

msg "Creating archive: $OUT"
# BusyBox-compatible gzip archive: do not use tar -z.
tar -C / -cf - -T "$TMP_LIST" | gzip -c > "$OUT"
rm -f "$TMP_LIST"

msg "Writing checksum"
sha256sum "$OUT" > "$OUT.sha256"

msg "Writing manifest: $MANIFEST"
{
    echo "Forgejo backup manifest"
    echo "Created: $TS"
    echo "Archive: $OUT"
    echo ""
    echo "Included paths:"
    for p in $PATHS; do
        if [ -e "$p" ]; then
            echo "  OK      $p"
        else
            echo "  MISSING $p"
        fi
    done
    echo ""
    echo "SQLite files at backup time:"
    ls -lh /opt/data/forgejo/data/forgejo.db* 2>/dev/null || true
} > "$MANIFEST"

msg "Starting Forgejo service: $FORGEJO_SERVICE"
systemctl start "$FORGEJO_SERVICE"

msg "Pruning old backups older than $KEEP_DAYS days"
# BusyBox find supports -exec but may not support -delete.
find "$BACKUP_ROOT" -type f -name 'forgejo-*.tar.gz' -mtime +"$KEEP_DAYS" -exec rm -f {} \;
find "$BACKUP_ROOT" -type f -name 'forgejo-*.tar.gz.sha256' -mtime +"$KEEP_DAYS" -exec rm -f {} \;
find "$BACKUP_ROOT" -type f -name 'forgejo-*.MANIFEST.txt' -mtime +"$KEEP_DAYS" -exec rm -f {} \;

msg "Backup complete"
ls -lh "$OUT" "$OUT.sha256" "$MANIFEST"
