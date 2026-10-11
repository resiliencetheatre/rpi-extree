#!/bin/sh
set -eu
export OFFLINE_PXE_BOARD_DIR="$BR2_EXTERNAL/board/rpi5-offline-pxe"
# Partition-only migration depends on retaining the working Pi 4 layout.
cmp "$OFFLINE_PXE_BOARD_DIR/genimage.cfg.in" \
    "$BR2_EXTERNAL/board/rpi4-offline-pxe/genimage.cfg.in"
grep -qx 'BR2_TARGET_ROOTFS_EXT2_SIZE="512M"' "$BR2_CONFIG" || {
    echo 'Pi 5 offline PXE requires a 512M rootfs to match the Pi 4 card layout' >&2
    exit 1
}
exec "$BR2_EXTERNAL/board/rpi4-offline-pxe/post-image.sh" "$@"
