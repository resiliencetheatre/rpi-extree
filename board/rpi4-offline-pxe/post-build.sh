#!/bin/sh
set -eu
board=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
support="$BR2_EXTERNAL/support/offline-pxe"
"${OFFLINE_PXE_BASE_POST_BUILD:-$BR2_EXTERNAL/board/raspberrypi4-64/post-build.sh}" "$@"
python3 "$support/render.py" target "${OFFLINE_PXE_SETTINGS:-$support/settings.json}" "$TARGET_DIR"
install -m 755 "$support/runtime-ready.sh" "$TARGET_DIR/usr/sbin/offline-ready"
install -m 755 "$support/runtime-recover.sh" "$TARGET_DIR/usr/sbin/offline-recover"
install -m 755 "$support/runtime-clock.sh" "$TARGET_DIR/usr/sbin/offline-clock"
install -m 755 "$support/check-upstream-tls.sh" "$TARGET_DIR/usr/sbin/offline-check-upstream-tls"
install -m 755 "$support/activate-generation.sh" "$TARGET_DIR/usr/sbin/offline-activate"
mkdir -p "$TARGET_DIR/etc/systemd/system/timers.target.wants" "$TARGET_DIR/srv/offline"
# Catch a resolved Kconfig dependency dropping HTTPS support before packaging.
test -x "$TARGET_DIR/usr/bin/curl"
test -s "$TARGET_DIR/etc/ssl/certs/ca-certificates.crt"
if [ ! -x "$TARGET_DIR/usr/bin/findmnt" ] && [ ! -x "$TARGET_DIR/bin/findmnt" ]; then
    echo 'offline-pxe: findmnt is missing. Use a fresh output directory; existing package stamps can retain an earlier board configuration.' >&2
    exit 1
fi
for tool in sfdisk wipefs blockdev mkfs.ext4; do
    if [ ! -x "$TARGET_DIR/usr/bin/$tool" ] && [ ! -x "$TARGET_DIR/usr/sbin/$tool" ] && [ ! -x "$TARGET_DIR/sbin/$tool" ]; then
        echo "offline-pxe: missing $tool for card setup. Reload the defconfig and rebuild util-linux (util-linux-reconfigure)." >&2
        exit 1
    fi
done
ln -sf ../offline-recover.timer "$TARGET_DIR/etc/systemd/system/timers.target.wants/offline-recover.timer"
for service in dnsmasq nginx systemd-resolved systemd-networkd-wait-online systemd-timesyncd; do
    ln -sf /dev/null "$TARGET_DIR/etc/systemd/system/$service.service"
done
# Buildroot may generate its own DHCP profile; this board owns Ethernet exclusively.
for network in "$TARGET_DIR"/etc/systemd/network/*; do
    [ "$(basename "$network")" = 10-offline.network ] || { [ ! -f "$network" ] || rm "$network"; }
done
python3 - "$TARGET_DIR" "$BR2_EXTERNAL" "$BR2_CONFIG" "${OFFLINE_PXE_DEFCONFIG:-rpi4_offline_pxe_defconfig}" <<'PY'
import json, pathlib, subprocess, sys
root, ext, config = map(pathlib.Path, sys.argv[1:4])
payload = root/'usr/share/offline-pxe/netboot-test'
if not (payload/'files.sha256').is_file():
    raise SystemExit('Missing bundled netboot test data: stage the verified bundle as described in support/offline-pxe/NETBOOT-TEST.md')
subprocess.run(['sha256sum', '--quiet', '-c', 'files.sha256'], cwd=payload, check=True)
netboot = json.loads((payload/'provenance.json').read_text())
site = json.loads((root/'etc/offline-pxe/settings.json').read_text())
mount_link = root/'etc/systemd/system/multi-user.target.wants/srv-offline.mount'
if mount_link.is_symlink():
    mount_link.unlink()
if site['ssd_uuid'] != '00000000-0000-0000-0000-000000000000':
    mount_link.parent.mkdir(parents=True, exist_ok=True)
    mount_link.symlink_to('../srv-offline.mount')
for key in ('server', 'interface', 'pool_start', 'pool_end'):
    if netboot['settings'][key] != site[key]:
        raise SystemExit('Bundled netboot network settings differ: regenerate and restage the diagnostic bundle')
def rev(path):
    return subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
symbols={}
for line in config.read_text().splitlines():
    if line.startswith('BR2_') and '=' in line:
        k,v=line.split('=',1); symbols[k]=v
manifest={'buildroot_commit':rev(pathlib.Path.cwd()), 'external_commit':rev(ext),
          'defconfig':sys.argv[4], 'symbols':symbols,
          'settings':json.loads((root/'etc/offline-pxe/settings.json').read_text()),
          'bundled_netboot_test':netboot,
          'hardware_validation':'not performed by build'}
(root/'etc/offline-pxe/build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
PY
