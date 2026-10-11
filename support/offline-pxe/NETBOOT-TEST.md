# Temporary netboot-only test

Workstation path setup (adjust once for your checkout):

```sh
WORKSPACE=/path/to/workspace
export BR2_EXTERNAL="$WORKSPACE/rpi-extree"
```


## Included in the appliance image

The verified test data is now staged in this target's existing rootfs overlay:
`board/rpi4-offline-pxe/rootfs-overlay/usr/share/offline-pxe/netboot-test/`.
The defconfig already selects that overlay; ordinary rebuilding includes the files.
It adds approximately 60 MiB to the root filesystem, within the configured 512 MiB
rootfs. Only the installer diagnostic is embedded, not the Debian package mirror.
No test server starts automatically.

After rebuilding and booting the Pi, connect the isolated laptop cable and run:

```sh
offline-netboot-test --isolated-lan
```

The launcher verifies the payload, copies it into `/run` (RAM), then runs the
bundled foreground DHCP/TFTP helper. No laptop file server, static laptop address,
SSD or Internet connection is needed with this image. Select one-shot UEFI IPv4
PXE on the laptop, choose Install, and stop at the first language screen. Ctrl-C
on the Pi stops the test, restores the recovery timer's previous state and frees
the RAM copy. The on-image payload remains available for another test.

The overlay contains Debian boot files, dnsmasq settings, the runner, provenance
and checksum inventory; `/usr/bin/offline-netboot-test` is the launcher. The
post-build hook checks payload hashes, checks that its network settings match the
image, and records its provenance in `offline-pxe-build.json`.

Binary payload files are ignored by git but present in this workspace for your
build. To reproduce them in a new checkout, prepare a bundle using the command
below, then stage it with the trusted hash printed by preparation:

```sh
python3 stage-netboot-test.py /tmp/new-netboot-test.tar.gz --sha256 PRINTED_SHA256
```

The stager refuses an existing payload directory; move the old directory aside
before replacing it. A fresh checkout without staged data fails the build with a
clear diagnostic. If you change the LAN settings, regenerate and restage the
bundle using those same settings. Changing only the SSD UUID needs no new bundle.

The following manual-transfer instructions remain useful for older images.

This diagnostic boots Debian Installer into its first interactive screen. It does
not test a complete installation, firmware for every laptop NIC, or offline package
coverage. Production services and their readiness gate remain separate. No SSD or
image rebuild is required. The Pi must already have `eth0` at `192.168.50.1/24`.
Use only a direct laptop cable or an isolated switch with no other DHCP server.

## Prepare on the connected workstation

The prepared bundle from this session is `/tmp/offline-pxe-netboot-test.tar.gz`
(55,487,022 bytes), installer build `20250803+deb13u7`. Its SHA256 is:

```
5c65834a08777f5b450c19060d9cd6d98fc9e720ac0e00642f1f3c6cdfc86b2c
```

Preparation verified Debian's signed InRelease, the dated installer SHA256SUMS
against that Release, and netboot.tar.gz against SHA256SUMS. It preserved the
stock directories, relative links, BIOS modules and UEFI loader chain. Bundle
inventory and dnsmasq syntax also passed. Real laptop boot and Secure Boot remain
untested. The directory contains no mirror or preseed.

To regenerate later (network access and roughly 55 MB download required):

```sh
cd "$BR2_EXTERNAL/support/offline-pxe"
python3 prepare-netboot-test.py settings.json /tmp/new-netboot-test.tar.gz
```

Requires Python 3 with tar extraction filters, CA certificates, gpgv and
`debian-archive-keyring`. Use the newly printed SHA256 for a regenerated bundle;
its checksum will differ. No debmirror installation is needed for this diagnostic.

## Transfer over the isolated Ethernet link

While the laptop is running its normal OS, set its wired interface manually to
`192.168.50.2`, netmask `255.255.255.0`, with no gateway or DNS. If using another
computer to transfer, it must be on the same isolated link. Copy the prepared
bundle to that computer. Serve only a dedicated transfer directory, not your home
folder or all of `/tmp`:

```sh
mkdir -p /tmp/pxe-transfer
cp /tmp/offline-pxe-netboot-test.tar.gz /tmp/pxe-transfer/
python3 -m http.server 8000 --bind 192.168.50.2 --directory /tmp/pxe-transfer
```

If a workstation firewall blocks this, allow inbound TCP 8000 only on that isolated
link. The file transfer uses local HTTP; the SHA256 below verifies it against the
trusted value from the workstation before extraction.

On the Pi's serial console:

```sh
curl -q --fail --show-error --output /tmp/netboot-test.tar.gz \
  http://192.168.50.2:8000/offline-pxe-netboot-test.tar.gz
printf '%s  %s\n' \
  '5c65834a08777f5b450c19060d9cd6d98fc9e720ac0e00642f1f3c6cdfc86b2c' \
  /tmp/netboot-test.tar.gz | sha256sum -c -
```

Proceed only if this prints **OK**, then:

```sh
tar -xzf /tmp/netboot-test.tar.gz -C /tmp
sh /tmp/netboot-test/run-netboot-test.sh --isolated-lan
```

Leave the command running in the serial console. It checks the transferred files
and Ethernet address, refuses active production services, takes the activation
lock, pauses recovery, and runs foreground dnsmasq with DHCP/TFTP logging. No
router or DNS server is advertised. It never writes a production manifest.

## Boot the laptop

Stop the laptop's temporary HTTP server after transfer completes. Reboot the
laptop and use its one-shot UEFI IPv4 network-boot choice. For the initial transport
test, use Secure Boot disabled; test Secure Boot enabled separately afterward.
Firmware support for PXE on the selected Ethernet adapter is required. An OS's
static IP setting does not control firmware PXE; firmware should obtain a DHCP
address in `192.168.50.100` through `.199`.

Expected serial log progression:

1. DHCP discovery/request and offer/acknowledgement of a lease.
2. UEFI architecture 7 or 9 requests `debian-installer/amd64/bootnetx64.efi`;
   BIOS architecture 0 instead requests `pxelinux.0`.
3. TFTP loads additional loader/menu files, kernel and initrd.
4. A Debian menu appears. Choose **Install** and stop at the language-selection
   screen. Reaching it proves more than just loading the first EFI file.

Do not proceed to disk partitioning. There is no package mirror for completing the
installation. ARM64 and IA32 UEFI are unsupported by this amd64 test. NIC firmware
may require a later, separately verified installer enhancement.

Press **Ctrl-C on the Pi console** to stop DHCP/TFTP. The helper removes its
maintenance flag and restores the recovery timer only if that timer was previously
active. Production services still require their normal SSD/manifest/clock checks.
The RAM files disappear on Pi reboot. If the test is killed forcibly and cleanup
cannot run, reboot the Pi to clear the temporary state. Restore the laptop's normal
wired IP settings and prefer local-disk boot afterward.

If no lease appears, check laptop firmware IPv4 PXE and physical link. If a lease
appears but boot fails, preserve the serial dnsmasq log and exact firmware error.
TFTP uses dynamically negotiated UDP ports, not only UDP 69. An additional serial
shell can capture DHCP with `tcpdump -ni eth0 -vv 'udp port 67 or udp port 68'`.
