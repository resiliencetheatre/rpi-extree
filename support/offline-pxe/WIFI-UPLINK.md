# Pi 5 Wi-Fi uplink and console tools

The Pi 5 target includes htop, full nano, iwd with iwctl, iw, regulatory data and
the Pi 5 Broadcom Wi-Fi firmware. Pi 4 remains unchanged. The Pi 5 firmware
configuration no longer disables Wi-Fi; Bluetooth remains disabled.

The roles are separate:

| Interface/service | Role |
| --- | --- |
| eth0 / systemd-networkd | Static 192.168.50.1/24 installation LAN |
| dnsmasq | DHCP/TFTP and local-only DNS on the installation interface |
| wlan0 / iwd | Wi-Fi association, upstream DHCP and default route |
| systemd-resolved | Pi host resolver using DNS learned by iwd; DNS stub listener disabled |

The Pi can use the Internet over Wi-Fi. PXE clients still receive no gateway;
IP forwarding/NAT remain disabled. dnsmasq keeps `no-resolv` and does not forward
client DNS to the Wi-Fi upstream. Nginx continues listening on the installation
address. A working uplink does not initiate mirror downloads or activate a new
generation. Installation services can still operate with Wi-Fi disconnected.

## Build and migrate

```sh
WORKSPACE=/path/to/workspace
export BR2_EXTERNAL="$WORKSPACE/rpi-extree"
cd "$WORKSPACE/buildroot"
make O=output-rpi5-offline-pxe rpi5_offline_pxe_defconfig
make O=output-rpi5-offline-pxe -j8
```

Use a clean output directory when possible. If updating an existing output,
reload this defconfig first; iwd must be configured with readline for iwctl, and
systemd must be configured with resolved. Existing package stamps may require:

```sh
make O=output-rpi5-offline-pxe systemd-reconfigure iwd-reconfigure linux-reconfigure rpi-firmware-reinstall
make O=output-rpi5-offline-pxe -j8
```

Substitute your actual output directory consistently. The post-build hook checks
for iwctl, iw, htop, nano, both service units and the Pi 5 firmware files. Firmware
is read when the brcmfmac module loads after rootfs mounting. Boot/rootfs sizes
remain 128 MiB/512 MiB. Use MIGRATE-PI4-CARD-TO-PI5.md to replace only partitions
1/2 of the existing card; the helper also works for a Pi 5-to-Pi 5 update. It
backs up the old rootfs, but replacing rootfs also replaces RTC enrollment and
saved Wi-Fi profiles. Keep any intentional local configuration privately.

## Connect from the serial console

```sh
systemctl is-active iwd systemd-resolved
iwctl device list
iwctl station wlan0 scan
iwctl station wlan0 get-networks
iwctl station wlan0 connect "YOUR_SSID"
```

The connect command prompts for the passphrase, avoiding a literal secret in
shell history. The scan command has no trailing `networks` argument. The requested
noninteractive form is also supported:

```sh
iwctl --passphrase 'WIFI_PSK' station wlan0 connect 'YOUR_SSID'
```

Replace placeholders locally, never in committed files. iwd stores saved network
credentials in `/var/lib/iwd` with private permissions and normally reconnects to
known networks. Do not copy those files into the overlay or Git. If necessary,
set the actual local radio regulatory domain with `iw reg set COUNTRY_CODE`;
use the two-letter code for the country where the device is operating.

Check upstream connectivity without downloading mirror packages:

```sh
iwctl station wlan0 show
ip -4 address show wlan0
ip -4 route
resolvectl status wlan0
cat /etc/resolv.conf
offline-check-upstream-tls
```

Correct UTC is required for HTTPS; use the documented RTC/manual clock workflow.
Expected routes include 192.168.50.0/24 on eth0 and the upstream default route on
wlan0. The Wi-Fi network must not use the same 192.168.50.0/24 subnet; change the
appliance's site settings and regenerate all dependent configuration if it does.

To disconnect:

```sh
iwctl station wlan0 disconnect
```

Useful diagnostics:

```sh
journalctl -b -u iwd -u systemd-resolved --no-pager -n 80
dmesg | grep -E 'brcmfmac|cfg80211|firmware|wlan'
ss -lntup
sysctl net.ipv4.ip_forward
htop
nano /etc/iwd/main.conf
```

Port 53 must remain owned by dnsmasq, with no resolved stub listener. There is no
network-online wait or Wi-Fi dependency on the offline installer services.

## Mirror refresh scope

This connectivity/tooling change does not install a Pi-side upstream mirror
updater or an update timer. The existing manual acquisition and full verification
tools run on a connected Debian workstation; see DESK-MIRROR.md. For a refresh,
use a new generation name and preserve the last verified generation. Never run
an in-place download into the active generation during installation.

Direct upstream refresh on the Pi requires a separately validated downloader,
signature/index/package verification and staging/promotion workflow. The current
host pipeline depends on Debian debmirror, Perl HTTPS modules, Python, gpgv,
dpkg-deb and initramfs tools, which are not part of this Buildroot runtime. Adding
Wi-Fi alone does not make those host scripts executable on the Pi.

No complete image build or real Wi-Fi association is claimed by configuration
checks. Verify WPA association, DHCP, host DNS/HTTPS, retained Wi-Fi credentials,
and continued isolated PXE service on the rebuilt Pi.

Reference: [iwd upstream configuration](https://kernel.googlesource.com/pub/scm/network/wireless/iwd/+/master/src/iwd.config.rst).
