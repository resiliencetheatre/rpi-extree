#!/bin/sh
set -eu
export OFFLINE_PXE_BASE_POST_BUILD="$BR2_EXTERNAL/board/raspberrypi5/post-build.sh"
export OFFLINE_PXE_DEFCONFIG=rpi5_offline_pxe_defconfig
"$BR2_EXTERNAL/board/rpi4-offline-pxe/post-build.sh" "$@"
install -m 755 "$BR2_EXTERNAL/support/offline-pxe/runtime-rtc.sh" "$TARGET_DIR/usr/sbin/offline-rtc"
mkdir -p "$TARGET_DIR/etc/systemd/system/multi-user.target.wants"
ln -sf ../offline-rtc.service "$TARGET_DIR/etc/systemd/system/multi-user.target.wants/offline-rtc.service"
# The common Pi 4 setup owns Ethernet and removes competing network profiles.
# Add the Pi 5 upstream Wi-Fi exception only after that common setup completes.
install -m 644 "$BR2_EXTERNAL/board/rpi5-offline-pxe/wifi.network" \
    "$TARGET_DIR/etc/systemd/network/20-offline-wifi.network"
# iwd uses resolved over D-Bus. Its DNS stub is disabled by the Pi 5 overlay,
# so it does not compete with dnsmasq for port 53 or supply DNS to PXE clients.
rm -f "$TARGET_DIR/etc/systemd/system/systemd-resolved.service"
for service in iwd systemd-resolved; do
    test -f "$TARGET_DIR/usr/lib/systemd/system/$service.service"
    ln -sf "/usr/lib/systemd/system/$service.service" \
        "$TARGET_DIR/etc/systemd/system/multi-user.target.wants/$service.service"
done
ln -sf /usr/lib/systemd/system/systemd-resolved.service \
    "$TARGET_DIR/etc/systemd/system/dbus-org.freedesktop.resolve1.service"
ln -snf ../run/systemd/resolve/resolv.conf "$TARGET_DIR/etc/resolv.conf"
for tool in iwctl iw htop nano; do
    if [ ! -x "$TARGET_DIR/usr/bin/$tool" ] && [ ! -x "$TARGET_DIR/usr/sbin/$tool" ]; then
        echo "offline-pxe: missing $tool; reload the Pi 5 defconfig and rebuild its package" >&2
        exit 1
    fi
done
for suffix in bin clm_blob txt; do
    test -s "$TARGET_DIR/lib/firmware/brcm/brcmfmac43455-sdio.raspberrypi,5-model-b.$suffix"
done
# Manual updater only: no update timer/service is installed or enabled.
support="$BR2_EXTERNAL/support/offline-pxe"
updater="$TARGET_DIR/usr/lib/offline-pxe"
mkdir -p "$updater/preseed"
for script in common.py render.py archive_inspect.py verify-mirror.py prepare-unattended.py mirror_acquire.py mirror_update.py; do
    install -m 644 "$support/$script" "$updater/$script"
done
for template in "$support"/preseed/*; do
    install -m 644 "$template" "$updater/preseed/"
done
cat > "$TARGET_DIR/usr/bin/offline-mirror-update" <<'SCRIPT'
#!/bin/sh
export PYTHONDONTWRITEBYTECODE=1
exec /usr/bin/python3 -u /usr/lib/offline-pxe/mirror_update.py "$@"
SCRIPT
chmod 755 "$TARGET_DIR/usr/bin/offline-mirror-update"
for tool in python3 gpgv; do
    test -x "$TARGET_DIR/usr/bin/$tool"
done
test -s "$TARGET_DIR/usr/share/keyrings/debian-archive-keyring.gpg"
