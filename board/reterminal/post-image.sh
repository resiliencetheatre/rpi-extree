#!/bin/sh
set -eu
board_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
# Use the same host dtc as the kernel build. Overlays need symbol/fixup sections.
install -d "${BINARIES_DIR}/rpi-firmware/overlays"
# rpi-firmware is not automatically reinstalled when these board files change.
install -m 0644 "${board_dir}/config.txt" "${BINARIES_DIR}/rpi-firmware/config.txt"
install -m 0644 "${board_dir}/cmdline.txt" "${BINARIES_DIR}/rpi-firmware/cmdline.txt"
"${HOST_DIR}/bin/dtc" -@ -I dts -O dtb \
    -o "${BINARIES_DIR}/rpi-firmware/overlays/reTerminal.dtbo" \
    "${board_dir}/reTerminal-overlay.dts"
support/scripts/genimage.sh \
    -c "${board_dir}/genimage.cfg"
