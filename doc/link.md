# Link

Link is an open-source resilience demonstration project for communication with confidence.

![Intro picture](images/title-image.png "Introduction")

Its main purpose is to serve as a training project for [critical thinking](https://resilience-theatre.com/wiki/doku.php?id=articles:cellular#mobiles) and [dogma avoidance](https://www.thesalesblog.com/blog/how-to-avoid-having-your-beliefs-become-dogma). The project is based on knowledge, experience, and lessons learned from mistakes.

## Features

* Suitable for small-scale embedded SoCs, including Broadcom, Rockchip, and RISC-V platforms
* Full source code available for on-premises builds and modifications
* Buildroot-supported [CycloneDX SBOM](https://buildroot.org/downloads/manual/manual.html#_generating_cyclonedx_sbom); see the `sbom` directory
* Fully controlled server entity for connectivity between NATed endpoints
* Server entity does not store communication content or persist data
* Fully ephemeral and point-to-point operation
* Three operating modes: Push-To-Talk (PTT), full-duplex voice, and SATCOM Push-To-Talk
* Three encryption examples: plaintext, symmetric encryption with XChaCha20, and logical XOR
* Speech compression with Opus and Codec2, depending on the selected mode
* Capable of delivering two-way speech communication via GEO satellite communication systems
* Can be used with [dark fiber](https://en.wikipedia.org/wiki/Dark_fibre) or twisted-pair copper lines
* Training platform for crypto agility: onboard your own implementation and train against platform threats
* User interface built with [LVGL](https://lvgl.io/) on top of the framebuffer
* Rekeying and configuration over a separate [MACsec](https://en.wikipedia.org/wiki/IEEE_802.1AE) LAN segment
* Uses several AI-generated components
* Delivers a maker-skills approach to your [strategy](https://resilience-theatre.com/wiki/doku.php?id=link:introduction)

## Missing and incomplete features

- [ ] Communication party selection
- [ ] Messaging
- [ ] Wi-Fi network scanning and attachment
- [ ] Gateway selection

## Out-of-scope features

- [x] TRNG provisioning environment

## Example implementations

Pictures of devices on which Link has been built and tested:

![Devices](images/link-units.png "Implementations")

## Bill of materials: Raspberry Pi

* [Raspberry Pi 4](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/)
* [HyperPixel 4.0 display](https://shop.pimoroni.com/products/hyperpixel-4?variant=12569485443155)
* [Nitrokey 3A NFC](https://shop.nitrokey.com/shop/nk3an-nitrokey-3a-nfc-147)
* USB headset
* [Case 1](https://www.printables.com/model/689580-raspberry-pi-4-hyperpixel-40-standing-portrait-cas)
* [Case 2](https://www.printables.com/model/157791-hyperpixel-40-pi-4-case)
* [PiSugar](https://www.pisugar.com/) UPS, optional

## Bill of materials: Rockchip

* [Vivid Unit](https://www.vividunit.com)

## Bill of materials: RISC-V

* [VisionFive2](https://www.waveshare.com/wiki/VisionFive2)

## Operating modes

![Intro picture](images/operation-modes.png "Operating modes")

* Full-duplex voice with Codec2 and XOR-based secrecy
* Push-To-Talk with a “word of the day” symmetric cipher using XChaCha20 and Opus
* SATCOM Push-To-Talk using RFC 5740 and the [NACK-Oriented Reliable Multicast (NORM) protocol](https://www.nrl.navy.mil/Our-Work/Areas-of-Research/Information-Technology/NCS/NORM/)

## Networking

* NAT traversal with a VPS acting as a gateway
* WireGuard inside [wstunnel](https://github.com/erebe/wstunnel)
* XOR inside WireGuard in full-duplex mode

## Data-at-rest security

* LUKS2-encrypted data partition or media using a [FIDO2 token](https://shop.nitrokey.com/shop/nk3an-nitrokey-3a-nfc-147)

## Prepare Buildroot

Clone the Buildroot and `rpi-extree` repositories:

```sh
git clone https://gitlab.com/buildroot.org/buildroot.git
git clone https://codeberg.org/resiliencetheatre/rpi-extree.git
```

## Build

Build the Link image:

```sh
cd buildroot
export BR2_EXTERNAL=[PATH]/rpi-extree
make clean
make raspberrypi4_64_com_hyperpixel_defconfig
make
```

This first step builds the image with `libfido2` enabled. After the initial build is complete, change `SYSTEMD_CONF_OPTS` in `package/systemd/systemd.mk` to enable FIDO2 support in systemd. Change `-Dlibfido2=disabled` to `-Dlibfido2=enabled`, then rebuild systemd and the full image:

```sh
make systemd-dirclean
make systemd-rebuild
make
```

You now have an image with systemd FIDO2 token support enabled.

## Create the microSD card

```sh
sudo dd if=output/images/sdcard.img of=[TARGET_DEVICE] status=progress
```

After the card has been written, reinsert it and mount the rootfs partition so that you can copy your SSH key to `/root/.ssh/authorized_keys`. This allows you to log in as root over SSH and continue with the following steps.

# Unit provisioning

![Provisioning picture](images/link-provisoning.excalidraw.png "Provisioning")

Link units are provisioned as pairs because communication party selection is not yet implemented. Units always operate as point-to-point pairs.

Unit provisioning happens in several steps. First, a LUKS2 partition is created. Second, a FIDO2 token is enrolled so that it can unlock that partition. Finally, unit configuration is onboarded for connectivity, including `wstunnel`, WireGuard, VPS settings, and OTP key material.

The provided provisioning scripts use an insecure PRNG. For real use cases, configure your TRNG environment in the provisioning scripts.

## Configure the LUKS2 partition

Boot the unit and log in over SSH with the FIDO2 token unplugged. Start by creating an encrypted partition on the microSD card:

```text
buildroot:~# create-partition.sh 
[create-partition] Starting on /dev/mmcblk0
[create-partition] Closing old mappings and unmounting old filesystems if present
[create-partition] Partition 2 ends at sector 2162688
[create-partition] Creating partition 3 from 2164736s to 100%
[create-partition] Partition device is present: /dev/mmcblk0p3
[create-partition] Zeroing first 8 MiB of /dev/mmcblk0p3
[create-partition] About to DESTROY all data on /dev/mmcblk0p3 and create a new LUKS2 container

WARNING!
========
This will overwrite data on /dev/mmcblk0p3 irrevocably.

Are you sure? (Type 'yes' in capital letters): YES
Enter passphrase for /dev/mmcblk0p3: 
Verify passphrase: 
[create-partition] Opening LUKS container as internaldrive
Enter passphrase for /dev/mmcblk0p3: 
[create-partition] Zeroing first 8 MiB of /dev/mapper/internaldrive
[create-partition] Creating ext4 filesystem with label internaldrive on /dev/mapper/internaldrive
mke2fs 1.47.4 (6-Mar-2025)
Creating filesystem with 14996224 4k blocks and 3751936 inodes
Filesystem UUID: 0f49f271-bab1-48ad-9821-24fafc45fdd1
Superblock backups stored on blocks: 
    32768, 98304, 163840, 229376, 294912, 819200, 884736, 1605632, 2654208, 
    4096000, 7962624, 11239424

Allocating group tables: done                            
Writing inode tables: done                            
Creating journal (65536 blocks): done
Writing superblocks and filesystem accounting information: done   

[create-partition] Final LUKS status
/dev/mapper/internaldrive is active.
  type:    LUKS2
  cipher:  aes-xts-plain64
  keysize: 512 [bits]
  key location: keyring
  device:  /dev/mmcblk0p3
  sector size:  512 [bytes]
  offset:  32768 [512-byte units] (16777216 [bytes])
  size:    119969792 [512-byte units] (61424533504 [bytes])
  mode:    read/write
[create-partition] Final partition table
Model: SD SD64G (sd/mmc)
Disk /dev/mmcblk0: 122167296s
Sector size (logical/physical): 512B/512B
Partition Table: msdos
Disk Flags: 

Number  Start     End         Size        Type     File system  Flags
 1      1s        65536s      65536s      primary  fat16        boot, lba
 2      65537s    2162688s    2097152s    primary  ext4
 3      2164736s  122167295s  120002560s  primary

[create-partition] Done
[create-partition] Encrypted device: /dev/mmcblk0p3
[create-partition] Mapped device:    /dev/mapper/internaldrive
buildroot:~#
```

Write down the password you entered. Keep the FIDO2 token unplugged and reboot the unit.

With the FIDO2 token still unplugged, enroll it using the script below:

```text
link:~# enroll-fido2.sh 
[enroll-fido2] Starting FIDO2 enrollment for /dev/mmcblk0p3
[enroll-fido2] Temporarily disabling udev rule /etc/udev/rules.d/99-nitrokey-luks.rules

Insert your FIDO2 token now.
When it is inserted and ready, press Enter to continue.

[enroll-fido2] Enrolling FIDO2 token to /dev/mmcblk0p3
🔐 Please enter current passphrase for disk /dev/mmcblk0p3: ••••••                  
Initializing FIDO2 credential on security token.
👆 (Hint: This might require confirmation of user presence on security token.)
Generating secret key on FIDO2 security token.
👆 In order to allow secret key generation, please confirm presence on security token.
New FIDO2 token enrolled as key slot 1.
[enroll-fido2] FIDO2 enrollment completed successfully
[enroll-fido2] Restoring udev rule /etc/udev/rules.d/99-nitrokey-luks.rules
[enroll-fido2] Done
link:~#
```

After the FIDO2 token has been enrolled, reboot the unit while keeping the token disconnected. Follow the on-screen instructions after boot, then insert the FIDO2 token. Once the token is detected, perform presence verification by touching the token while its LED is flashing.

Optional: After FIDO2 enrollment, you may remove the LUKS2 passphrase from the LUKS header.

## Provisioning a unit

Provisioning two Link units for communication uses two subprojects:

* [wg-init-link](https://codeberg.org/resiliencetheatre/wg-init-link)
* [linkprovision](https://codeberg.org/resiliencetheatre/linkprovision)

First, `wg-init-link` creates the WireGuard setup for your VPS and Link devices. Then, `linkprovision` creates the INI and environment files, along with development OTP key material.

### Reference files

Below is a configuration extract from the `10.0.0.6/24` unit. It communicates with another endpoint configured as `10.0.0.5/24`. The mount point `/mnt/internaldrive` is the LUKS2-encrypted partition.

LVGL user interface (`lvgl-com`) INI file:

```ini
# /opt/lvgl-com/lvgl.ini 
[lvgl]
ip_address=
word_of_day=oldsecret
backlight_timeout=0
backlight_wakeup=0
ptt_mode=3
ptt_word_of_day=cojot
gateway=1
```

INI file for the MACsec key exchange daemon:

```ini
# /opt/macpipe/macpipe.ini 
[settings]
my_address=[MACSEC_ADDRESS]/24
my_interface=end0
shared_secret=[SHARED_SECRET]
```

WireGuard configuration for `systemd-networkd`:

```ini
# /mnt/internaldrive/connection/wg0.netdev
[NetDev]
Name=wg0
Kind=wireguard
Description=WireGuard tunnel wg0

[WireGuard]
PrivateKey=[PRIVATE_KEY]

[WireGuardPeer]
PublicKey=[PUBLIC_KEY]
PresharedKey=[PRESHARED_KEY]
AllowedIPs=10.0.0.1/32, 0.0.0.0/0
Endpoint=127.0.0.1:51871
PersistentKeepalive=30
```

```ini
# /mnt/internaldrive/connection/wg0.network
[Match]
Name=wg0

[Link]
MTUBytes=1200

[Network]
Address=10.0.0.6/24
```

`wstunnel` configuration values for WireGuard encapsulation:

```sh
# /mnt/internaldrive/connection/wstunnel.env
WSTUNNEL_PATH=[HTTP_UPGRADE_PATH_PREFIX]
WSTUNNEL_LISTEN=udp://51871:127.0.0.1:51871?timeout_sec=0
WSTUNNEL_URL=wss://[SERVER_IP]:[SERVER_PORT]
```

NORM protocol endpoints:

```sh
# /opt/c2ptt/normhosts.env 
NORM_LOCAL=10.0.0.6
NORM_REMOTE=10.0.0.5
```

`udpproxy` inbound and outbound configuration:

```ini
# /opt/udpproxy/proxy-in.ini
[proxy]
incoming_address=10.0.0.6
incoming_port=6001
outgoing_address=127.0.0.1
outgoing_port=5002
outbound_key=/mnt/internaldrive/out.key
inbound_key=/mnt/internaldrive/in.key
outbound_counter_file=/mnt/internaldrive/out.count
inbound_counter_file=/mnt/internaldrive/in.count
```

```ini
# /opt/udpproxy/proxy-out.ini
[proxy]
incoming_address=127.0.0.1
incoming_port=5001
outgoing_address=10.0.0.5
outgoing_port=6001
outbound_key=/mnt/internaldrive/out.key
inbound_key=/mnt/internaldrive/in.key
outbound_counter_file=/mnt/internaldrive/out.count
inbound_counter_file=/mnt/internaldrive/in.count
```

Key material for `udpproxy` and counter files:

```text
# OTP keys and counter files
/mnt/internaldrive/in.count
/mnt/internaldrive/in.key
/mnt/internaldrive/out.count
/mnt/internaldrive/out.key
```

Let that sink in.

# Functionality

Link is implemented as an embedded Linux image built with Buildroot. The implementation is not based on any general-purpose Linux distribution. Instead, all components are statically built and deployed. Typically, the build system produces a bootable `sdcard.img` file under `output/images/`, and that image contains `boot` and `rootfs` partitions. The image contains no package manager or other distribution-specific tooling for updates or modifications.

The implementation follows the [Unix philosophy](https://en.wikipedia.org/wiki/Unix_philosophy) and relies heavily on systemd services and functionality. These services are activated based on the selected mode: Push-To-Talk, full-duplex, or SATCOM Push-To-Talk.

Connection configuration and OTP key material are stored on a LUKS2-protected partition, so connection setup and OTP usage are only permitted after a successful LUKS2 unlock and mounting of `/mnt/internaldrive`. Communication is deferred until the encrypted partition has been opened with a FIDO2 token.

![Functionality](images/link-operation-modes.excalidraw.png "Functional diagram")

**Note:** This section is still a work in progress.
