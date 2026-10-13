#!/bin/sh
# Install code only; mirror generation repair is a separate explicit command.
set -eu
[ "$(id -u)" = 0 ] || { echo 'Run on Pi as root' >&2; exit 1; }
bundle=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$bundle"
sha256sum -c files.sha256
mkdir -p /run/offline-pxe
exec 9>/run/offline-pxe/activation.lock
flock -n 9
[ ! -e /run/offline-pxe/maintenance ]
[ ! -e /var/lib/offline-pxe/update-transaction.json ]
target=/usr/lib/offline-pxe
[ -f "$target/mirror_update.py" ]
for file in mirror_update.py mirror_acquire.py verify-mirror.py; do
    python3 -c 'import ast, sys; ast.parse(open(sys.argv[1]).read())' "$file"
done
sh -n activate-generation.sh
backup=$(mktemp -d "$target/backup-metadata-fix.XXXXXX")
for file in mirror_update.py mirror_acquire.py verify-mirror.py; do
    cp -p "$target/$file" "$backup/$file"
    cp "$file" "$target/$file.new"
    chmod 644 "$target/$file.new"
    mv "$target/$file.new" "$target/$file"
done
cp -p /usr/bin/offline-activate "$backup/offline-activate"
cp activate-generation.sh /usr/bin/offline-activate.new
chmod 755 /usr/bin/offline-activate.new
mv /usr/bin/offline-activate.new /usr/bin/offline-activate
printf 'Updater installed; previous code saved in %s\n' "$backup"
echo 'Mirror content and active generation unchanged. Run the documented repair command for the inactive generation.'
