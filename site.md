# Raspberry Pi Zero 2W Site Image

The Raspberry Pi Zero 2W **site** configuration builds a bootable MicroSD card using Buildroot.

![Intro picture](images/site-d.png "Site Introduction")

The Site image is a demonstration of running several offline-capable services on a single Raspberry Pi Zero 2W. When equipped with Whisplay and UPS HATs, the unit can operate as a fully standalone node.

The node connects to an upstream Wi-Fi network for Internet or other network connectivity while simultaneously providing its own internal Wi-Fi access point. Local users connect to this AP to access services hosted directly on the Site node.

This project is **work in progress**. Services, defaults, configuration, and this documentation are still evolving.

## Features

The image currently contains or is intended to demonstrate:

- Full-world **Situation Map** using MapLibre GL JS and PMTiles.
- Situation Map plugins for USB-connected Meshtastic radios.
- Situation Map integration with **taky-ng**, providing a local TAK/CoT server.
- Local email server with UUCP transport between nodes.
- Local news server with synchronization between nodes.
- **udpptt** Push-To-Talk for global, local, and dark-fiber connectivity.
- Reticulum stack for future experimentation and expansion.

With a Whisplay HAT, the node gains a display, speaker, microphone, and physical PTT switch on one board, allowing Push-To-Talk operation without additional user hardware.

The purpose of the Site image is to demonstrate a locally operated computing and communications node built in-house from user-controlled source code. It provides a baseline for email, news, maps, and Push-To-Talk. When several Site nodes can route traffic between each other, store-and-forward email and news can form a useful closed-loop communication system alongside real-time PTT, locally stored world maps, Meshtastic, and CoT.

# Bring-up

## Hostname

Set the node hostname in:

```text
/etc/hostname
/etc/hosts
```

Adjust `/etc/dnsmasq.conf` to match the hostname. Example for `site-d`:

```ini
domain=site-d.lan
local=/site-d.lan/
address=/site-d.lan/192.168.50.1
```

Reboot after changing the hostname and DNS configuration.

## Partitioning

Create a third MicroSD partition formatted as ext4. This partition is used to store the large `planet.pmtiles` world map.

Get its UUID:

```sh
blkid /dev/mmcblk0p3
```

Adjust and uncomment the map mount line in `/etc/fstab`, replacing the UUID with the value reported above:

```fstab
UUID=cd7a0e95-bb33-41b7-bc40-a41cf7ba74df /opt/maps ext4 rw,defaults,noatime 0 2
```

## Situation Map

After the map partition is mounted and `planet.pmtiles` has been copied to it, create the Situation Map symlink:

```sh
ln -s /opt/maps/planet.pmtiles /opt/situation/maps/planet.pmtiles
```

Situation Map is available over TLS at:

```text
https://site-d:8443
```

## Wi-Fi AP

Set the local Wi-Fi AP SSID and password with:

```sh
/usr/bin/prepare-wifi-ap
```

## Upstream Wi-Fi

Connect to the Site AP and open the upstream Wi-Fi scan/connect interface:

```text
http://192.168.50.1:8082
http://site-d:8082
```

The upstream interface provides Internet or other network connectivity while the Site AP remains available to local clients.

## Caddy Certificates

Caddy creates self-signed/internal certificates on first boot. They can be replaced if required; see the Caddy documentation for certificate configuration.

TLS is primarily required because browser location access used by the Situation Map **Report Position** function requires a secure context.

## taky-ng Certificates

Edit the hostname in:

```text
rpi-extree/utils/generate-taky-ng-server-certs.sh
```

Run the script on the build/development host. It creates a `taky-pki` directory containing:

```text
ca.crt
ca.key
server.crt
server.key
```

Copy only the following files to `/etc/taky/ssl/` on the Raspberry Pi:

```text
ca.crt
server.crt
server.key
```

Keep `ca.key` on the host; it is the CA private key.

Example:

```sh
scp taky-pki/ca.crt taky-pki/server.crt taky-pki/server.key zero:/etc/taky/ssl/
```

The taky-ng CoT TLS endpoint is:

```text
192.168.50.1:8089
```

## Certificate Server

While connected to the Site Wi-Fi AP, clients can retrieve the generated CA certificate from:

```text
http://192.168.50.1:8000/
```

## udpptt

Configure the udpptt gateway address and encryption key in:

```text
/etc/systemd/system/udpptt-client.service
```

The default demonstration configuration contains the current test VPS endpoint so PTT can be tested immediately when upstream connectivity is available.

By default udpptt is configured in **server mode**, so upstream Wi-Fi connectivity is required. Change the mode as appropriate for the deployment.

Project documentation:

https://github.com/resiliencetheatre/udpptt

---

This README intentionally covers only the basic Site concept and initial bring-up. The image, service integration, defaults, and operational documentation remain under active development.
