# Raspberry Pi 4 PocketTerm boot overlays

`configs/raspberrypi4_pocketterm_defconfig` runs this board's `post-image.sh`
before the shared `board/raspberrypi4-64/post-image.sh` image builder.
The board hook copies every `*.dtbo` in this directory, with mode `0644`, to
`${BINARIES_DIR}/rpi-firmware/overlays/`. Currently these are:

- `waveshare-35dpi-3b.dtbo`
- `waveshare-35dpi-4b.dtbo`
- `waveshare-35dpi-5b.dtbo`

The shared image builder includes that overlays directory in `boot.vfat`,
which is placed in the boot partition of `sdcard.img`. The target mounts
this partition at `/boot`, making the files available under `/boot/overlays/`.
Existing firmware overlays are preserved, except that a board-local file
with the same name replaces the staged copy.

Load the updated `raspberrypi4_pocketterm_defconfig` and run the normal Buildroot
build (`make`) to regenerate the images. For an existing build configuration,
ensure `BR2_ROOTFS_POST_IMAGE_SCRIPT` contains both hooks in the order above.
Additional `.dtbo` files placed in this directory are included automatically.
These are precompiled overlays; the hook copies them without compiling them.
Copying an overlay does not enable it: select the appropriate `dtoverlay=`
entry in the boot `config.txt` separately.

## UTXT messaging and console startup

The PocketTerm defconfig enables `BR2_PACKAGE_UTXTRELAY` and
`BR2_PACKAGE_LVGL_CONSOLE_LOCAL`. The UTXT package fetches a pinned commit from
`https://github.com/resiliencetheatre/utxtrelay.git`; `lvgl-console-local` builds
from the sibling `lvgl-console` directory. The UTXT package installs the server,
plain terminal client and console connector under
`/usr/bin`; it depends on libsodium and builds without ncurses.

For an existing Buildroot configuration, enable `utxtrelay` in **Network and
encapsulation**, retain `lvgl-console-local` under **User interface**, and build:

```sh
make -C buildroot utxtrelay
make -C buildroot lvgl-console-local-rebuild
# After publishing connector changes and updating UTXTRELAY_VERSION
# in package/utxtrelay/utxtrelay.mk (also when switching from local sources):
make -C buildroot utxtrelay-dirclean
make -C buildroot utxtrelay
# Regenerate the filesystem/image to include overlay changes:
make -C buildroot
```

Set `UTXTRELAY_SERVER`, `UTXTRELAY_PORT`, a unique `UTXTRELAY_NAME`, and
`UTXTRELAY_ROOM` in `/etc/default/utxtrelay`. The shipped address `127.0.0.1`
is a placeholder. Run `utxtrelay-server` on the selected server; the device
services do not start a local relay automatically. The protocol default port
is UDP 5555. Names/rooms must not contain whitespace.

The overlay enables these units through `multi-user.target.wants` symlinks:

- `utxtrelay-console-client.service`: creates `/run/utxtrelay`, signals readiness
  once its local socket listens, and retries remote relay setup independently.
- `lvgl-console.service`: starts after connector readiness and uses
  `/usr/bin/lvgl-console-launcher` to restore VT state on exit. The former
  `lvgl-com.service` is an alias, preventing duplicate UI instances.

The UI can still start if the connector fails, and reconnects when it returns.
Both services run as root; the socket is restricted to that user. The connector
may restart without restarting the UI. Configure a shared secret in Messaging
using `/secret STRING` on each participant; it is memory-only and must be set
again after a connector restart.

After deploying an updated root filesystem:

```sh
systemctl daemon-reload
systemctl restart utxtrelay-console-client.service
systemctl restart lvgl-console.service
journalctl -u utxtrelay-console-client -u lvgl-console
```

Native validation is `make -C utxtrelay test` plus the LVGL CTest suite.
`make -C utxtrelay test-network` additionally runs a real loopback UDP relay
and two connectors and requires permission to bind sockets. Physical display,
keyboard, service startup and networking should also be checked on the Pi.
