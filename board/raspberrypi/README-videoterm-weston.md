# Pi 5 Weston kiosk hardware verification

`raspberrypi5_videoterm_weston_defconfig` is a separate target derived from
`raspberrypi5_videoterm_defconfig`. It retains the existing Waveshare 6.25-inch
DSI panel, firmware configuration, kernel fragments, Ethernet, audio and security
packages. It now starts the standalone LVGL Wayland UI. gtk-pipe integration
is not included.

## Build

From the Buildroot directory, use a separate output directory:

```sh
make O=output-videoterm-weston BR2_EXTERNAL=../rpi-extree raspberrypi5_videoterm_weston_defconfig
make O=output-videoterm-weston
```

The SD image is `output-videoterm-weston/images/sdcard.img`. Write it to a spare
card using your usual image-writing procedure. The root filesystem allocation
is 1 GiB to leave room for Mesa, Weston and diagnostics; this is not a measured
runtime memory requirement.

## What this target adds

- Mesa V3D (with the automatically selected VC4 support), EGL, GLES and GBM:
  GPU rendering and buffers for presentation.
- Weston DRM backend and kiosk shell: display ownership, input and fullscreen
  application presentation. Desktop/IVI shells and XWayland are not enabled.
- Weston simple clients: EGL, shared-memory, touch and DMA-BUF diagnostics.
- libdrm test tools, including `modetest`: connector/plane inspection.
- libseat's built-in backend: seat access without a separate seatd daemon.

The target-specific overlay enables `weston-kiosk.service` and masks the base
overlay's framebuffer `lvgl-com.service`. The separate `lvgl-com-wayland.service`
starts the UI after Weston signals readiness through `systemd-notify.so`. Its
working directory remains `/opt/lvgl-com`; audio restoration and direct touch
device checks do not gate UI startup. The base defconfig and shared overlay
are unchanged.

The service runs as root on tty7 for hardware bring-up, with a private runtime
directory at `/run/weston-kiosk`. This is a bring-up service, not the final
application privilege model. It selects the connected DSI connector dynamically
instead of assuming a stable DRM card number. If DSI has not appeared yet,
systemd retries after five seconds. It deliberately does not fall back to HDMI.

Weston is explicitly started with the GL renderer. No Mesa software rasterizer
is selected. Failure to initialize accelerated output should remain visible in
the journal rather than silently turning this into a CPU-rendering test.

## Expected boot result

The DSI screen shows lvgl-com fullscreen, without desktop panels. LVGL renders
shared-memory buffers and Weston composites them with V3D. Missing touch input
does not prevent startup. Serial console and SSH remain available. The previous
triangle demo remains installed for independent graphics testing.

The existing firmware panel rotation is retained. Do not add a second Weston
rotation until checking the visible orientation and touch mapping on hardware.

## Verify on the Pi

```sh
systemctl status weston-kiosk
journalctl -b -u weston-kiosk --no-pager
ls -l /dev/dri
```

Check the journal for the selected DSI card, EGL initialization and a V3D GL
renderer. Record errors about GBM, DMA-BUF import, modifiers or scanout. The
V3D render device and RP1 DSI display device are separate: this test must verify
that the selected Mesa/Weston/kernel combination can share their buffers.

For interactive client tests from a root SSH/serial shell:

```sh
export XDG_RUNTIME_DIR=/run/weston-kiosk
export WAYLAND_DISPLAY=wayland-0
systemctl stop lvgl-com-wayland
weston-simple-touch
```

Touch should draw marks at the corresponding screen positions. Stop that client
before testing another, since the kiosk shell displays top-level windows
fullscreen. Other useful clients are `weston-simple-shm`, `weston-simple-egl`
and `weston-simple-dmabuf-egl`. Stop any manually launched test client and
restore the UI with:

```sh
systemctl start lvgl-com-wayland
```

To inspect KMS independently, stop Weston and use the DSI card name reported in
its journal (replace `cardN` below):

```sh
systemctl stop lvgl-com-wayland weston-kiosk
modetest -D /dev/dri/cardN -c -p
systemctl start weston-kiosk lvgl-com-wayland
```

Success means accelerated DSI output, stable animation and correct touch
coordinates. It does not yet demonstrate video decoding, camera capture,
zero-copy presentation, or LVGL/video composition. Those are later milestones.

For rebuild instructions after the application source reorganization, see
`lvgl-com/README.md`. The package uses that local Git checkout, so keep it
alongside this external tree on every build machine.
