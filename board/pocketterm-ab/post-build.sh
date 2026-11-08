#!/bin/sh
set -eu
board_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
target_dir="${1:?target directory}"
: "${AB_RELEASE_VERSION:?set AB_RELEASE_VERSION}"
: "${AB_VERIFY_KEY:?set AB_VERIFY_KEY to external RSA public PEM}"
case "$AB_VERIFY_KEY" in /*) ;; *) echo "AB_VERIFY_KEY must be absolute" >&2; exit 1;; esac
for binary in usr/bin/openssl usr/bin/lsblk usr/bin/swupdate; do
    test -x "$target_dir/$binary" || { echo "Missing runtime executable: $binary" >&2; exit 1; }
done
# The API imports ssl; an old Python build may retain disabled extension state
# even though the active Buildroot config now enables BR2_PACKAGE_PYTHON3_SSL.
ssl_found=no
for module in "$target_dir"/usr/lib/python*/lib-dynload/_ssl*.so; do
    if [ -f "$module" ]; then ssl_found=yes; break; fi
done
if [ "$ssl_found" != yes ]; then
    echo "Missing Python _ssl extension: enable BR2_PACKAGE_PYTHON3_SSL=y, run make python3-dirclean with the same O= directory, then rebuild." >&2
    exit 1
fi
for binary in sfdisk partx blockdev resize2fs; do
    found=no
    for directory in bin sbin usr/bin usr/sbin; do
        if [ -x "$target_dir/$directory/$binary" ]; then found=yes; break; fi
    done
    if [ "$found" != yes ]; then
        echo "Missing factory growth tool: $binary; reload the A/B defconfig, then run make util-linux-reconfigure e2fsprogs-reconfigure with the same O= directory." >&2
        exit 1
    fi
done
# Fail closed if Kconfig dropped a required security option in the pinned source.
swconfig="$BUILD_DIR/swupdate-2026.05.1/.config"
for option in SSL_IMPL_OPENSSL HASH_VERIFY SIGNED_IMAGES SIGALG_RAWRSA HW_COMPATIBILITY LIBCONFIG RAW; do
    if ! grep -qx "CONFIG_$option=y" "$swconfig"; then
        echo "Required SWUpdate option missing: CONFIG_$option" >&2
        exit 1
    fi
done
for option in SCRIPTS SHELLSCRIPTHANDLER WEBSERVER SURICATTA DOWNLOAD; do
    if grep -qx "CONFIG_$option=y" "$swconfig"; then
        echo "Unsupported SWUpdate feature enabled: CONFIG_$option" >&2
        exit 1
    fi
done
# Reject private material rather than copying it into the image.
openssl rsa -pubin -in "$AB_VERIFY_KEY" -noout >/dev/null
case "$AB_RELEASE_VERSION" in *[!a-zA-Z0-9._+-]*|'') exit 1;; esac
# The inherited overlay mounts the old MBR boot PARTUUID. It does not exist in
# this GPT layout. Selector/Data are resolved and mounted by the A/B controller.
# Keep the baseline overlay unchanged and remove only its obsolete /boot entry.
sed -i '\|^[[:space:]]*[^#[:space:]][^[:space:]]*[[:space:]][[:space:]]*/boot[[:space:]]|d' "$target_dir/etc/fstab"
install -d "$target_dir/usr/lib/pocketterm-ab" "$target_dir/etc/pocketterm-ab" "$target_dir/data" "$target_dir/selector"
install -m 644 "$board_dir/grow.py" "$target_dir/usr/lib/pocketterm-ab/"
install -m 644 "$board_dir/common.py" "$target_dir/usr/lib/pocketterm-ab/"
install -m 755 "$board_dir/control.py" "$target_dir/usr/lib/pocketterm-ab/"
install -m 644 "$AB_VERIFY_KEY" "$target_dir/etc/pocketterm-ab/public.pem"
printf '%s\n' "$AB_RELEASE_VERSION" > "$target_dir/etc/pocketterm-ab/version"
printf '%s\n' "$AB_RELEASE_VERSION" > "$BINARIES_DIR/release-version"
printf 'pocketterm-rpi4-lvgl-v1\n' > "$BINARIES_DIR/release-profile"
printf 'pocketterm-rpi4-lvgl-v1 pocketterm-rpi4-lvgl-v1\n' > "$target_dir/etc/hwrevision"
install -d "$target_dir/usr/sbin" "$target_dir/etc/systemd/system/multi-user.target.wants"
ln -sf ../lib/pocketterm-ab/control.py "$target_dir/usr/sbin/pocketterm-update"
for unit in swupdate.service swupdate.socket swupdate-usb@.service; do
    ln -sf /dev/null "$target_dir/etc/systemd/system/$unit"
done
install -m 644 "$board_dir/prepare.service" "$target_dir/etc/systemd/system/pocketterm-ab-prepare.service"
ln -sf ../pocketterm-ab-prepare.service "$target_dir/etc/systemd/system/multi-user.target.wants/pocketterm-ab-prepare.service"
install -m 644 "$board_dir/pocketterm-ab.service" "$target_dir/etc/systemd/system/"
install -m 644 "$board_dir/pocketterm-ab-failure.service" "$target_dir/etc/systemd/system/"
ln -sf ../pocketterm-ab.service "$target_dir/etc/systemd/system/multi-user.target.wants/pocketterm-ab.service"
install -d "$target_dir/etc/systemd/system/lvgl-console.service.d"
printf '[Service]\nEnvironment=LV_AB_READY=/run/lvgl-ab-ready\nEnvironment=RETERMINAL_UPDATE_SOCKET=/run/pocketterm-update-api/control.sock\nExecStartPre=/bin/rm -f /run/lvgl-ab-ready\n' > "$target_dir/etc/systemd/system/lvgl-console.service.d/ab.conf"

for service in lvgl-console udpptt sshd; do
    install -d "$target_dir/etc/systemd/system/$service.service.d"
    printf '[Unit]\nRequires=pocketterm-ab-prepare.service\nAfter=pocketterm-ab-prepare.service\n' > "$target_dir/etc/systemd/system/$service.service.d/persistence.conf"
done

install -d "$target_dir/etc/systemd/system.conf.d"
printf '[Manager]\nRuntimeWatchdogSec=15s\nRebootWatchdogSec=30s\n' > "$target_dir/etc/systemd/system.conf.d/ab-watchdog.conf"

# Stage 1 local API: installed for explicit testing, never enabled automatically.
for script in api_service.py api_client.py remote_release.py swupdate_progress.py; do
    install -m 755 "$board_dir/$script" "$target_dir/usr/lib/pocketterm-ab/$script"
done
ln -sf ../lib/pocketterm-ab/api_client.py "$target_dir/usr/sbin/pocketterm-update-client"
install -m 644 "$board_dir/api/pocketterm-update-api.service" "$target_dir/etc/systemd/system/"
install -d "$target_dir/usr/share/pocketterm-update-api"
install -m 644 "$board_dir/api/config.example.json" "$target_dir/usr/share/pocketterm-update-api/"

# Start the local API alongside LVGL only when its operator config exists.
# Do not order LVGL After=API: the API waits for trial health, which needs LVGL.
printf '[Unit]\nWants=pocketterm-update-api.service\n' > "$target_dir/etc/systemd/system/lvgl-console.service.d/update-api.conf"
