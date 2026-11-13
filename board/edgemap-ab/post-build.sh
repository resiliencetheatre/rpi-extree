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
python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); from common import metadata; metadata(sys.argv[2], {})' "$board_dir" "$AB_RELEASE_VERSION"
# Remove single-slot boot and map mounts from the inherited overlay.
# Selector/Data are resolved and mounted by the A/B controller.
sed -i '\|^[[:space:]]*[^#[:space:]][^[:space:]]*[[:space:]][[:space:]]*/boot[[:space:]]|d' "$target_dir/etc/fstab"
sed -i '\@^[[:space:]]*[^#[:space:]][^[:space:]]*[[:space:]][[:space:]]*/opt/\(boot\|data\)[[:space:]]@d' "$target_dir/etc/fstab"
install -d "$target_dir/usr/lib/edgemap-ab" "$target_dir/etc/edgemap-ab" "$target_dir/data" "$target_dir/selector"
install -m 644 "$board_dir/grow.py" "$target_dir/usr/lib/edgemap-ab/"
install -m 644 "$board_dir/common.py" "$target_dir/usr/lib/edgemap-ab/"
install -m 755 "$board_dir/control.py" "$target_dir/usr/lib/edgemap-ab/"
install -m 644 "$AB_VERIFY_KEY" "$target_dir/etc/edgemap-ab/public.pem"
printf '%s\n' "$AB_RELEASE_VERSION" > "$target_dir/etc/edgemap-ab/version"
printf '%s\n' "$AB_RELEASE_VERSION" > "$BINARIES_DIR/release-version"
printf 'edgemap-lite-situation-rpi4-v1\n' > "$BINARIES_DIR/release-profile"
printf 'edgemap-lite-situation-rpi4-v1 edgemap-lite-situation-rpi4-v1\n' > "$target_dir/etc/hwrevision"
install -d "$target_dir/usr/sbin" "$target_dir/etc/systemd/system/multi-user.target.wants"
ln -sf ../lib/edgemap-ab/control.py "$target_dir/usr/sbin/edgemap-update"
for unit in swupdate.service swupdate.socket swupdate-usb@.service; do
    ln -sf /dev/null "$target_dir/etc/systemd/system/$unit"
done
install -m 644 "$board_dir/prepare.service" "$target_dir/etc/systemd/system/edgemap-ab-prepare.service"
ln -sf ../edgemap-ab-prepare.service "$target_dir/etc/systemd/system/multi-user.target.wants/edgemap-ab-prepare.service"
install -m 644 "$board_dir/edgemap-ab.service" "$target_dir/etc/systemd/system/"
install -m 644 "$board_dir/edgemap-ab-failure.service" "$target_dir/etc/systemd/system/"
ln -sf ../edgemap-ab.service "$target_dir/etc/systemd/system/multi-user.target.wants/edgemap-ab.service"
# Mount persistent settings before any overlay application service.
for unit in "$target_dir"/etc/systemd/system/*.service; do
    service=$(basename "$unit" .service)
    case "$service" in edgemap-ab*|edgemap-update-api|edgemap-update-finish|partition|bootstrap) continue;; esac
    install -d "$target_dir/etc/systemd/system/$service.service.d"
    printf '[Unit]\nRequires=edgemap-ab-prepare.service\nAfter=edgemap-ab-prepare.service\n' > "$target_dir/etc/systemd/system/$service.service.d/persistence.conf"
done
install -d "$target_dir/etc/systemd/system/situation-map.service.d"
printf '[Unit]\nRequires=edgemap-ab-prepare.service\nAfter=edgemap-ab-prepare.service\n' > "$target_dir/etc/systemd/system/situation-map.service.d/persistence.conf"
for unit in partition bootstrap engine gpsreader cotmulticast tacmsgrouter mirror meshpipe ircpipe userinterface wss-mirror wss-messaging wss-messaging-irc wss-gpssocket wss-status; do
    ln -sf /dev/null "$target_dir/etc/systemd/system/$unit.service"
done
# Single-slot bootstrap/partition commands must never run on GPT A/B media.
for script in create-partition.sh create-partition-noenc.sh init-edgemap.sh; do
    if [ -e "$target_dir/usr/bin/$script" ]; then
        printf '#!/bin/sh\necho "Single-slot provisioning is disabled on EdgeMap A/B; see EEPROM.md and README.md" >&2\nexit 1\n' > "$target_dir/usr/bin/$script"
    fi
done
install -m 644 "$board_dir/health.py" "$target_dir/usr/lib/edgemap-ab/"
install -d "$target_dir/opt/data" "$target_dir/opt/situation/maps"
install -d "$target_dir/etc/systemd/system.conf.d"
printf '[Manager]\nRuntimeWatchdogSec=15s\nRebootWatchdogSec=30s\n' > "$target_dir/etc/systemd/system.conf.d/ab-watchdog.conf"

# Local root-only API; no automatic download or installation.
for script in api_service.py api_client.py remote_release.py swupdate_progress.py update_wrapper.py; do
    install -m 755 "$board_dir/$script" "$target_dir/usr/lib/edgemap-ab/$script"
done
ln -sf ../lib/edgemap-ab/api_client.py "$target_dir/usr/sbin/edgemap-update-client"
install -m 644 "$board_dir/api/edgemap-update-api.service" "$target_dir/etc/systemd/system/"
install -d "$target_dir/usr/share/edgemap-update-api"
install -m 644 "$board_dir/api/config.example.json" "$target_dir/usr/share/edgemap-update-api/"
install -m 644 "$board_dir/api/sources.example.json" "$target_dir/usr/share/edgemap-update-api/"

# The root-only API starts locally; network checks require an explicit CLI request.
install -m 644 "$board_dir/api/config.example.json" "$target_dir/etc/default/edgemap-updates.json"
ln -sf ../edgemap-update-api.service "$target_dir/etc/systemd/system/multi-user.target.wants/edgemap-update-api.service"

# Situation map is the selected Lite application, independent of legacy EdgeMap.
for file in python-front.py web/index.html; do
    test -f "$target_dir/opt/situation/$file" || { echo "Situation map missing: $file (enable BR2_PACKAGE_SITUATION_MAP)" >&2; exit 1; }
done
for service in situation-gps situation-map-tak situation-map-meshtastic; do
    install -d "$target_dir/etc/systemd/system/$service.service.d"
    printf '[Unit]\nRequires=edgemap-ab-prepare.service\nAfter=edgemap-ab-prepare.service\n' > "$target_dir/etc/systemd/system/$service.service.d/persistence.conf"
done

# Interactive single-command updater; source settings persist under /etc/default.
ln -sf ../lib/edgemap-ab/update_wrapper.py "$target_dir/usr/sbin/update.sh"
install -m 600 "$board_dir/api/sources.example.json" "$target_dir/etc/default/edgemap-update-sources.json"
install -m 644 "$board_dir/edgemap-update-finish.service" "$target_dir/etc/systemd/system/"
ln -sf ../edgemap-update-finish.service "$target_dir/etc/systemd/system/multi-user.target.wants/edgemap-update-finish.service"
