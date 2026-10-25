# Waveshare PocketTerm 3.5

These are development notes, work in progress.


Mask console 

```
systemctl mask --now getty@tty1.service
systemctl start lvgl-com.service
```

To restore console login later:

```
systemctl stop lvgl-com.service
systemctl unmask getty@tty1.service
systemctl start getty@tty1.service
```

## Display sleep and wake with LVGL

Tested on the PocketTerm with Raspberry Pi 4, `vc4drmfb`, and HDMI-A-1.
Linux exposes no backlight device under `/sys/class/backlight/`, but framebuffer
blanking provides a working display sleep/wake path. No direct power-domain
control is needed.

For a manual test over SSH or serial:

```sh
# Sleep the display.
echo 4 > /sys/class/graphics/fb0/blank

# Wake the display.
echo 0 > /sys/class/graphics/fb0/blank
```

While blanked, HDMI-A-1 reported DPMS `Off` and its CRTC reported `active=0`.
After unblanking, these returned to `On` and `active=1`. Touch also woke the
display during manual testing. Unblanking brought the backlight back up, but
the LVGL interface initially appeared only partially; swiping refreshed more
of the UI. Restoring HDMI output alone therefore did not reliably repaint the
application.

The working application sequence is:

1. Open the selected framebuffer and call
   `ioctl(fd, FBIOBLANK, FB_BLANK_POWERDOWN)`.
2. Schedule wake with an LVGL timer, keeping the event loop running.
3. Call `ioctl(fd, FBIOBLANK, FB_BLANK_UNBLANK)` when the timer fires.
4. Invalidate the active screen and the display's top and system layers, then
   call `lv_refr_now(display)` to force a complete redraw.

Run the LVGL operations in the LVGL thread. The redraw sequence is:

```c
lv_obj_invalidate(lv_display_get_screen_active(display));
lv_obj_invalidate(lv_display_get_layer_top(display));
lv_obj_invalidate(lv_display_get_layer_sys(display));
lv_refr_now(display);
```

`lvgl-console` implements this in Settings with **Sleep screen for 5 seconds**.
The five-second sleep, automatic wake, and full redraw were verified on the
PocketTerm. It uses `LV_LINUX_FBDEV_DEVICE` (default `/dev/fb0`), reports errors
in the UI and stderr, and attempts to unblank an ongoing test on normal exit.
SIGKILL cannot perform that cleanup. The process needs permission to control
the framebuffer.

The internal speaker uses HDMI audio, so display blanking may interrupt sound;
audio playback while blanked has not been verified by this test.

# udpptt

```
mkdir -p ~/.config/udpptt
ptt_dpi_keygen --secret ~/.config/udpptt/dpi.secret \
--public ~/.config/udpptt/dpi.public

mkdir -p /run/udpptt

ptt_client [SERVER_IP] \
  --alsa-device 'plughw:CARD=Audio,DEV=0' \
  --ptt-socket /tmp/udpptt.sock \
  --altgr-ptt-delay-ms 700 \
  --txid pocketterm \
  --encrypt --key shared-room \
  --jitter-ms 200 \
  --fec-loss-percent 10 \
  --preamble-id POCKT \
  --state-file /run/udpptt/state \
  --rx-state-timeout-ms 1000 \
  --dpi-id pocketterm
```
