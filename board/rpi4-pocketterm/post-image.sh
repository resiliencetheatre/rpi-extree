#!/bin/sh

set -eu

BOARD_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

# Stage board overlays before the shared Raspberry Pi hook creates boot.vfat.
install -d "${BINARIES_DIR}/rpi-firmware/overlays"
install -m 0644 "${BOARD_DIR}"/*.dtbo "${BINARIES_DIR}/rpi-firmware/overlays/"
