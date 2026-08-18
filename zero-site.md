# Raspberry Pi Zero 2 W Dual Wi-Fi Site Setup

This document describes the working Raspberry Pi Zero 2 W Wi-Fi setup used in the Buildroot image.

The Zero 2 W uses its single onboard Wi-Fi radio simultaneously as:

- a managed Wi-Fi client (`wlan0`) using `iwd`
- a local Wi-Fi access point (`ap0`) using `hostapd`

The Broadcom/Cypress Wi-Fi implementation supports concurrent managed + AP operation, but both interfaces must share the same Wi-Fi channel.

The system therefore discovers the upstream channel used by `wlan0`, creates `ap0`, generates a matching runtime `hostapd` configuration, and starts the local AP. A small watcher monitors the upstream connection and restarts the AP on the new channel if `wlan0` later changes channel.

---

## Architecture

```text
                    Upstream Wi-Fi
                    e.g. FRITZ!Box
                          |
                          | iwd / managed STA
                          |
                        wlan0
                  192.168.178.x/24
                          |
                +-------------------+
                | Raspberry Pi      |
                | Zero 2 W          |
                |                   |
                | iwd               |
                | hostapd           |
                | dnsmasq           |
                | systemd-networkd  |
                +-------------------+
                          |
                         ap0
                   192.168.50.1/24
                          |
                     SSID: zero
                     /         \
                  phone       laptop
```

The wireless PHY advertises support for:

```text
#{ managed } <= 1, #{ AP } <= 1, ...
total <= 4, #channels <= 1
```

The important restriction is:

```text
#channels <= 1
```

For example:

```text
wlan0  managed  channel 1
ap0    AP       channel 1
```

If the upstream AP moves to channel 6, the local AP must also move to channel 6.

---

# Required Buildroot Packages

The image should include at least:

```text
iwd
iw
hostapd
dnsmasq
iproute2
systemd
```

Recommended:

```text
wireless-regdb
```

If clients connected to `ap0` will later be routed/NATed through `wlan0`, also include:

```text
nftables
```

`wpa_supplicant` and NetworkManager are not required because `iwd` handles the upstream client connection and `systemd-networkd` handles interface addressing.

---

# Files in the Filesystem Overlay

Recommended overlay layout:

```text
fs_overlay/
├── etc/
│   ├── dnsmasq.conf
│   └── systemd/
│       ├── network/
│       │   └── 30-ap0.network
│       └── system/
│           ├── wifi-ap-prepare.service
│           ├── wifi-ap-channel-watch.service
│           ├── hostapd.service
│           └── dnsmasq.service
└── usr/
    └── bin/
        ├── prepare-wifi-ap
        └── wifi-ap-channel-watch
```

The generated hostapd configuration is stored under `/run` and therefore must **not** be placed in the filesystem overlay.

---

# 1. AP Preparation Helper

Install as:

```text
/usr/bin/prepare-wifi-ap
```

Contents:

```sh
#!/bin/sh

set -eu

STA_IF="wlan0"
AP_IF="ap0"
RUNTIME_CONF="/run/hostapd-ap0.conf"

SSID="zero"
PASSPHRASE="YOUR_PASSWORD"
COUNTRY="LU"

CHANNEL="${1:-}"

if [ -z "$CHANNEL" ]; then
    echo "prepare-wifi-ap: waiting for ${STA_IF} to associate"

    while :; do
        if /usr/bin/iw dev "$STA_IF" link 2>/dev/null |
           grep -q '^Connected to '; then
            break
        fi

        sleep 1
    done

    CHANNEL="$(
        /usr/bin/iw dev "$STA_IF" info |
        awk '$1 == "channel" { print $2; exit }'
    )"

    if [ -z "$CHANNEL" ]; then
        echo "prepare-wifi-ap: unable to determine ${STA_IF} channel" >&2
        exit 1
    fi
fi

case "$CHANNEL" in
    *[!0-9]*|'')
        echo "prepare-wifi-ap: invalid channel: ${CHANNEL}" >&2
        exit 1
        ;;
esac

echo "prepare-wifi-ap: using channel ${CHANNEL}"

if ! /usr/bin/iw dev "$AP_IF" info >/dev/null 2>&1; then
    echo "prepare-wifi-ap: creating ${AP_IF}"
    /usr/bin/iw dev "$STA_IF" interface add "$AP_IF" type __ap
fi

TMP_CONF="${RUNTIME_CONF}.tmp"

cat >"$TMP_CONF" <<EOF
interface=${AP_IF}
driver=nl80211

ssid=${SSID}

country_code=${COUNTRY}
ieee80211d=1

hw_mode=g
channel=${CHANNEL}

wpa=2
wpa_passphrase=${PASSPHRASE}
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF

chmod 600 "$TMP_CONF"
mv "$TMP_CONF" "$RUNTIME_CONF"

echo "prepare-wifi-ap: generated ${RUNTIME_CONF} for channel ${CHANNEL}"
```

Make executable:

```sh
chmod 755 /usr/bin/prepare-wifi-ap
```

## What it does

Without arguments:

```sh
/usr/bin/prepare-wifi-ap
```

the helper:

1. waits until `iwd` has associated `wlan0`
2. reads the active Wi-Fi channel
3. creates virtual AP interface `ap0` if necessary
4. generates `/run/hostapd-ap0.conf`
5. sets hostapd to the same channel as `wlan0`

It can also be called with an explicit channel:

```sh
/usr/bin/prepare-wifi-ap 6
```

This is used by the runtime channel watcher.

---

# 2. Channel Watcher

Install as:

```text
/usr/bin/wifi-ap-channel-watch
```

Contents:

```sh
#!/bin/sh

set -eu

STA_IF="wlan0"
CONF="/run/hostapd-ap0.conf"
INTERVAL=5

get_sta_channel()
{
    /usr/bin/iw dev "$STA_IF" info 2>/dev/null |
        awk '$1 == "channel" { print $2; exit }'
}

get_ap_config_channel()
{
    if [ -r "$CONF" ]; then
        sed -n 's/^channel=//p' "$CONF" | head -n1
    fi
}

echo "wifi-ap-channel-watch: started"

LAST_CHANNEL=""

while :; do
    if /usr/bin/iw dev "$STA_IF" link 2>/dev/null |
       grep -q '^Connected to '; then

        CHANNEL="$(get_sta_channel || true)"

        if [ -n "$CHANNEL" ] &&
           [ "$CHANNEL" != "$LAST_CHANNEL" ]; then

            AP_CHANNEL="$(get_ap_config_channel || true)"

            echo "wifi-ap-channel-watch: wlan0=${CHANNEL} ap=${AP_CHANNEL:-unknown}"

            if [ "$CHANNEL" != "$AP_CHANNEL" ]; then
                echo "wifi-ap-channel-watch: channel change detected"

                /usr/bin/prepare-wifi-ap "$CHANNEL"
                /usr/bin/systemctl restart hostapd.service
            fi

            LAST_CHANNEL="$CHANNEL"
        fi
    else
        LAST_CHANNEL=""
    fi

    sleep "$INTERVAL"
done
```

Make executable:

```sh
chmod 755 /usr/bin/wifi-ap-channel-watch
```

## What it does

The watcher checks `wlan0` every five seconds.

When it sees a new upstream channel:

```text
wlan0 channel=6
AP config=1
```

it runs:

```sh
/usr/bin/prepare-wifi-ap 6
/usr/bin/systemctl restart hostapd.service
```

The local AP therefore follows the upstream AP channel.

Clients connected to `ap0` will briefly disconnect while hostapd restarts.

---

# 3. systemd-networkd Configuration

Install as:

```text
/etc/systemd/network/30-ap0.network
```

Contents:

```ini
[Match]
Name=ap0

[Network]
Address=192.168.50.1/24
ConfigureWithoutCarrier=yes
```

`ConfigureWithoutCarrier=yes` is important because `ap0` may initially show:

```text
NO-CARRIER
state DOWN
```

before hostapd starts beaconing.

The static AP address is:

```text
192.168.50.1/24
```

---

# 4. dnsmasq Configuration

Install as:

```text
/etc/dnsmasq.conf
```

Contents:

```ini
interface=ap0
bind-interfaces

dhcp-range=192.168.50.10,192.168.50.100,255.255.255.0,12h
dhcp-option=3,192.168.50.1
dhcp-option=6,192.168.50.1
```

This gives hotspot clients addresses in:

```text
192.168.50.10 - 192.168.50.100
```

with:

```text
gateway: 192.168.50.1
DNS:     192.168.50.1
```

At this stage the configuration provides access to the Raspberry Pi itself.

Routing or NAT from `ap0` to `wlan0` is a separate optional feature and is not required for the dual Wi-Fi stack itself.

---

# 5. Wi-Fi AP Preparation Service

Install as:

```text
/etc/systemd/system/wifi-ap-prepare.service
```

Contents:

```ini
[Unit]
Description=Prepare concurrent Wi-Fi access point
After=iwd.service systemd-networkd.service
Requires=iwd.service
Before=hostapd.service

[Service]
Type=oneshot
ExecStart=/usr/bin/prepare-wifi-ap
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

This service waits for the upstream iwd connection and prepares the AP before hostapd starts.

---

# 6. hostapd Service

Install as:

```text
/etc/systemd/system/hostapd.service
```

Contents:

```ini
[Unit]
Description=Wi-Fi Access Point
Requires=wifi-ap-prepare.service
After=wifi-ap-prepare.service

[Service]
Type=simple
ExecStart=/usr/bin/hostapd /run/hostapd-ap0.conf
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

The hostapd configuration is generated dynamically by `prepare-wifi-ap`.

Example generated file:

```text
/run/hostapd-ap0.conf
```

Example contents while the upstream network is on channel 1:

```ini
interface=ap0
driver=nl80211

ssid=zero

country_code=LU
ieee80211d=1

hw_mode=g
channel=1

wpa=2
wpa_passphrase=YOUR_PASSWORD
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
```

Do not place this generated file in the overlay.

---

# 7. dnsmasq Service

Install as:

```text
/etc/systemd/system/dnsmasq.service
```

Contents:

```ini
[Unit]
Description=DHCP/DNS server for Wi-Fi AP
Requires=hostapd.service
After=hostapd.service systemd-networkd.service

[Service]
Type=simple
ExecStart=/usr/bin/dnsmasq --keep-in-foreground --conf-file=/etc/dnsmasq.conf
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

---

# 8. Channel Watch Service

Install as:

```text
/etc/systemd/system/wifi-ap-channel-watch.service
```

Contents:

```ini
[Unit]
Description=Watch upstream Wi-Fi channel for concurrent AP
Requires=hostapd.service
After=hostapd.service iwd.service

[Service]
Type=simple
ExecStart=/usr/bin/wifi-ap-channel-watch
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

---

# Service Startup Flow

The resulting boot flow is:

```text
systemd
   |
   +--> iwd.service
   |       |
   |       +--> wlan0 associates to upstream Wi-Fi
   |
   +--> systemd-networkd.service
   |
   +--> wifi-ap-prepare.service
           |
           +--> wait for wlan0 association
           +--> read wlan0 channel
           +--> create ap0
           +--> generate /run/hostapd-ap0.conf
                    |
                    v
              hostapd.service
                    |
                    +--> AP starts beaconing
                    |
                    v
              dnsmasq.service
                    |
                    +--> DHCP for ap0 clients

              wifi-ap-channel-watch.service
                    |
                    +--> monitors wlan0 channel
                    +--> regenerates hostapd config
                    +--> restarts hostapd if needed
```

---

# Enabling Services

On the running target:

```sh
systemctl daemon-reload

systemctl enable wifi-ap-prepare.service
systemctl enable hostapd.service
systemctl enable dnsmasq.service
systemctl enable wifi-ap-channel-watch.service
```

To enable immediately:

```sh
systemctl enable --now wifi-ap-prepare.service
systemctl enable --now hostapd.service
systemctl enable --now dnsmasq.service
systemctl enable --now wifi-ap-channel-watch.service
```

For a Buildroot image, these services should ultimately be enabled as part of the root filesystem construction rather than manually after every flash.

---

# Verification

After boot:

```sh
systemctl status iwd
systemctl status wifi-ap-prepare
systemctl status hostapd
systemctl status dnsmasq
systemctl status wifi-ap-channel-watch
```

Check interfaces:

```sh
/usr/bin/iw dev
```

Expected:

```text
phy#0
    Interface ap0
        type AP
        channel 1

    Interface wlan0
        type managed
        ssid <upstream SSID>
        channel 1
```

Both interfaces must show the same channel.

Check addresses:

```sh
ip addr show wlan0
ip addr show ap0
```

Expected approximately:

```text
wlan0:
    192.168.178.x/24

ap0:
    192.168.50.1/24
```

Check generated hostapd configuration:

```sh
cat /run/hostapd-ap0.conf
```

Check upstream association:

```sh
/usr/bin/iw dev wlan0 link
```

Check connected hotspot clients:

```sh
/usr/bin/iw dev ap0 station dump
```

Watch the channel watcher:

```sh
journalctl -fu wifi-ap-channel-watch
```

Typical normal output:

```text
wifi-ap-channel-watch: started
wifi-ap-channel-watch: wlan0=1 ap=1
```

If the upstream changes channel:

```text
wifi-ap-channel-watch: wlan0=6 ap=1
wifi-ap-channel-watch: channel change detected
prepare-wifi-ap: using channel 6
prepare-wifi-ap: generated /run/hostapd-ap0.conf for channel 6
```

---

# Testing DHCP

When a client associates with the `zero` SSID, it should receive an address such as:

```text
192.168.50.10
```

The Pi is reachable at:

```text
192.168.50.1
```

A basic client-side test is:

```sh
ping 192.168.50.1
```

---

# Manual Debugging

Create/update the AP configuration using the current STA channel:

```sh
/usr/bin/prepare-wifi-ap
```

Force generation for a specific channel:

```sh
/usr/bin/prepare-wifi-ap 6
```

Check the result:

```sh
grep '^channel=' /run/hostapd-ap0.conf
```

Run hostapd manually with debug logging:

```sh
/usr/bin/hostapd -dd /run/hostapd-ap0.conf
```

A successful client connection includes messages similar to:

```text
AP-STA-CONNECTED
WPA: pairwise key handshake completed
EAPOL-4WAY-HS-COMPLETED
```

Run dnsmasq in foreground:

```sh
/usr/bin/dnsmasq --no-daemon --conf-file=/etc/dnsmasq.conf
```

Successful DHCP activity should show:

```text
DHCPDISCOVER
DHCPOFFER
DHCPREQUEST
DHCPACK
```

---

# Operational Notes

## One radio, one channel

The Zero 2 W uses one physical Wi-Fi radio.

Concurrent STA + AP operation works, but the AP and client interfaces must share the same channel.

This is why `hostapd` must not be permanently hardcoded to an arbitrary channel.

## Upstream disconnect

If `wlan0` disconnects, the channel watcher clears its remembered channel and waits.

When `iwd` reconnects, the new channel is detected and hostapd is adjusted if needed.

## Channel change

Changing hostapd channel requires a hostapd restart in the current implementation.

Clients connected to `ap0` therefore experience a short interruption when the upstream Wi-Fi channel changes.

## `/run` configuration

The generated configuration lives at:

```text
/run/hostapd-ap0.conf
```

`/run` is volatile.

This is intentional: the configuration is regenerated on every boot based on the actual upstream Wi-Fi channel.

## Security

Replace:

```text
YOUR_PASSWORD
```

in `/usr/bin/prepare-wifi-ap` with the actual AP WPA2 passphrase or move the site-specific credential into a separate protected configuration file if desired.

The generated hostapd file is created with mode:

```text
0600
```

---

# Current Network Layout

```text
Upstream Wi-Fi:
    interface: wlan0
    manager:   iwd
    addressing: upstream DHCP

Local Wi-Fi:
    interface: ap0
    manager:   hostapd
    address:   192.168.50.1/24
    DHCP:      dnsmasq
    pool:      192.168.50.10-192.168.50.100

Channel:
    dynamically follows wlan0
```

This provides a self-contained local Wi-Fi access network on the Raspberry Pi Zero 2 W while the same onboard radio remains connected to an upstream Wi-Fi network.
