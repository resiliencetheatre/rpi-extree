#!/bin/sh
set -eu
target_dir="${1:?missing target directory}"
if [ ! -x "${target_dir}/usr/bin/python3" ]; then
    echo "reTerminal PTT requires BR2_PACKAGE_PYTHON3=y in the active Buildroot configuration; enable it and rebuild." >&2
    exit 1
fi
# Remove obsolete service files when reusing an older PocketTerm output tree.
rm -f "${target_dir}/etc/systemd/system/lvgl-com.service" \
    "${target_dir}/etc/systemd/system/multi-user.target.wants/lvgl-com.service"

# Enable the board button bridge alongside the existing userspace services.
install -d "${target_dir}/etc/systemd/system/multi-user.target.wants"
ln -sf ../reterminal-ptt.service \
    "${target_dir}/etc/systemd/system/multi-user.target.wants/reterminal-ptt.service"
