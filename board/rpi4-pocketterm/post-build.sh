#!/bin/sh

set -eu

# Overlay copies do not remove files left by older builds.
# PocketTerm now installs and enables only lvgl-console.service.
target_dir="${1:?missing target directory}"
rm -f "${target_dir}/etc/systemd/system/lvgl-com.service" \
    "${target_dir}/etc/systemd/system/multi-user.target.wants/lvgl-com.service"
