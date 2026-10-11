#!/bin/sh
set -eu
# Preserve old source files as inactive evidence, then use only the local archive.
mkdir -p /target/etc/apt/sources.list.d /target/etc/apt/offline-disabled
for file in /target/etc/apt/sources.list /target/etc/apt/sources.list.d/*.list /target/etc/apt/sources.list.d/*.sources; do
    [ ! -f "$file" ] || mv "$file" /target/etc/apt/offline-disabled/
done
wget -O /target/etc/apt/sources.list.d/offline.sources http://@ADDRESS@/preseed/offline.sources
# No global validity exception is installed, either during d-i or in the target.
chroot /target apt-get update
