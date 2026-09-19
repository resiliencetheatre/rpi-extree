# Pi 4 videoterm: Camera Module v1.3 JPEG capture

`raspberrypi4_videoterm_defconfig` enables the OV5647 camera on the Pi 4
CSI connector alongside the Waveshare DSI display. Power off before attaching
the camera ribbon to the CAMERA connector.

The firmware config loads `dtoverlay=ov5647` explicitly. Buildroot installs
the kernel's DT overlays through the default
`BR2_PACKAGE_RPI_FIRMWARE_INSTALL_DTB_OVERLAYS=y` setting. The kernel fragment
retains the OV5647, Unicam and BCM2835 ISP drivers. No legacy camera firmware
mode or `start_x=1` is needed.

Userspace includes libcamera's `rpi/vc4` pipeline and GStreamer source,
GStreamer tools, video conversion, JPEG and multifile plugins. Selecting libevent
also enables libcamera's `cam` diagnostic utility in this Buildroot version.

After rebuilding and booting the new image, check detection and plugins:

```sh
cam -l
gst-inspect-1.0 libcamerasrc
gst-inspect-1.0 jpegenc
gst-inspect-1.0 multifilesink
```

Save one JPEG to the root filesystem:

```sh
gst-launch-1.0 -e libcamerasrc ! \
  'video/x-raw,format=NV12,width=1296,height=972,framerate=15/1,colorimetry=bt709' ! \
  queue ! jpegenc quality=90 snapshot=true ! filesink location=/root/camera.jpg
```

`snapshot=true` sends EOS after one encoded frame, so the file contains one
JPEG and the command exits. For full sensor resolution, try `width=2592`,
`height=1944`, and `framerate=5/1`. The first frame may be captured before
automatic exposure and white balance settle; this is a basic capture test.
Choose a writable persistent mount for long-term storage (`/tmp` is volatile).

To allow exposure and white balance time to settle, continuously replace a
test JPEG in RAM. Wait 5–10 seconds, press Ctrl+C, then inspect the file:

```sh
gst-launch-1.0 -e libcamerasrc ! \
  'video/x-raw,format=NV12,width=1296,height=972,framerate=15/1,colorimetry=bt709' ! \
  queue ! jpegenc quality=90 ! multifilesink location=/tmp/camera.jpg
```

After stopping, copy a satisfactory image to persistent storage:

```sh
cp /tmp/camera.jpg /root/camera.jpg
```

If Motion is running, stop it with `systemctl stop motion` before these tests
so it does not compete for the camera device.

## Live framebuffer preview

The config includes `fbdevsink` from gst1-plugins-bad. Run this over SSH or
serial, stopping the UI and local getty so they do not draw over the preview:

```sh
systemctl stop lvgl-com.service getty@tty1.service
gst-launch-1.0 -e libcamerasrc ! \
  'video/x-raw,format=NV12,width=640,height=480,framerate=15/1,colorimetry=bt709' ! \
  queue max-size-buffers=2 leaky=downstream ! videoconvert ! \
  fbdevsink device=/dev/fb0 sync=false
```

This starts with a 640x480 preview to fit either panel orientation. It writes
directly to the framebuffer, rather than embedding video within LVGL. Check
`cat /sys/class/graphics/fb0/name` if multiple displays are attached and choose
the framebuffer corresponding to the DSI display. Console output can still
overwrite the preview.

Press Ctrl+C, then restore the UI:

```sh
systemctl start getty@tty1.service lvgl-com.service
```

If detection fails, check the ribbon connection and boot overlay, then run:

```sh
dmesg | grep -Ei 'ov5647|unicam|bcm2835|camera'
LIBCAMERA_LOG_LEVELS='*:DEBUG' cam -l
```

Use `libcamerasrc` for the processed camera image; the sensor's raw Bayer
capture node alone is not a JPEG source.

References: [Raspberry Pi camera software](https://www.raspberrypi.com/documentation/computers/camera_software.html),
[libcamera GStreamer usage](https://libcamera.org/getting-started.html#using-gstreamer-plugin),
[GStreamer jpegenc](https://gstreamer.freedesktop.org/documentation/jpeg/jpegenc.html).

Configuration checks do not replace an image build and capture test on hardware.
