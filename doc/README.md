# External Buildroot Trees for Raspberry Pi

This project aims to unify external Buildroot trees for various Raspberry 
Pi hardware models and images. It is a work in progress designed to 
streamline the build environment across Edgemap and other related projects.

By consolidating configurations into a single, flexible environment, 
users can easily select the desired hardware targets and components for 
their builds. This approach leverages the official Raspberry Pi Foundation 
Linux kernel, ensuring compatibility and access to the latest kernel updates.

## Front-Deployed Development

This approach allows you to deploy embedded builds from any environment while 
retaining full control over source code and build processes. It ensures 
physical security of your development assets and, when necessary, enables 
rapid evasion or relocation—an essential capability if the development 
site comes under stress, surveillance, or physical threat.

![Intro picture](images/intro.png "Introduction")

### Equipments

- [Build host](https://www.geekompc.com/geekom-mini-it12-mini-pc/)
- [Panasonic FZ-55 development laptop](https://ruggedbooks.com/products/toughbook-fz-55-mk3-intel-core-i5-1345u-14-hd-16gb-512gb-ssd-windows-11-pro)
- [Debian](https://www.debian.org/distrib/)

## Buildroot

Check [buildroot manual](https://buildroot.org/downloads/manual/manual.html) and install mandatory packages
to your build host before building this project. Cross compilation of Raspberry Pi 5 image on Intel Core i5-8365U 
laptop takes almost 4 hours. Using dedicated build host with fast disk, lot's of RAM and powerful CPU drops this
time significantly. See equipments list above.

Baseline configurations are:

```
raspberrypi4_64_defconfig
raspberrypi5_defconfig
raspberrypicm4io_64_defconfig
raspberrypizero2w_64_defconfig
```

### Edgemap

Build Edgemap project to Raspberry Pi 5:

```
mkdir ~/build
cd ~/build
git clone https://gitlab.com/buildroot.org/buildroot.git
git clone https://codeberg.org/resiliencetheatre/rpi-extree.git
export BR2_EXTERNAL=~/build/rpi-extree
cd ~/build/buildroot
make raspberrypi5_edgemap_defconfig
make
```

Please note that this is still work in progress. If you like to
get working Edgemap, use [Edgemap](https://github.com/resiliencetheatre/rpi4edgemap) from Github.

## Linux kernel

You can store and use custom kernel config:

```
BR2_LINUX_KERNEL_CUSTOM_CONFIG_FILE="${BR2_EXTERNAL}/configs/kernel/bcm2711_defconfig"
```

To update the kernel version, obtain the commit ID from the Raspberry Pi kernel
repository and update `BR2_LINUX_KERNEL_CUSTOM_TARBALL_LOCATION` in the relevant
defconfig:

```
# Clone kernel to separate directory outside project directory
git clone https://github.com/raspberrypi/linux.git
# Get latest commit ID
git log
```

The archive hash must be added in two locations:

- Kernel: `patches/linux/custom/linux.hash`
- Toolchain kernel headers: `patches/linux-headers/custom/linux-headers.hash`

```
# Get the hash of the downloaded kernel archive
sha256sum dl/linux/linux-[COMMIT_ID].tar.gz

# Add this line to both hash files listed above:
sha256  [HASH_OF_DOWNLOADED_TAR]  linux-[COMMIT_ID].tar.gz
```

You can also create a patch for your buildroot of custom Linux kernel hash (or any
other change you do to your buildroot).

```
cd buildroot
git diff -- linux/linux.hash > $BR2_EXTERNAL/patches/buildroot/[PATHCH_NAME].patch
```

Applying patch before build:

```
cd buildroot
git apply "$BR2_EXTERNAL/patches/buildroot/[PATHCH_NAME].patch"
```


## Filesystem overlays

Default filesystem overlay is defined:

```
BR2_ROOTFS_OVERLAY="${BR2_EXTERNAL}/fs_overlay/fs_base"
```

You may change this based on your build.

# Displays

To get lvgl working with various display, check these out:

## Hyperpixel4

Add config.txt for Raspberry Pi 5 and Hyperpixel 4 display:

```
# Enable DRM VC4 V3D driver and disable uart
dtoverlay=vc4-kms-dpi-hyperpixel4
dtoverlay=vc4-kms-v3d,nohdmi
max_framebuffers=2
enable_uart=0
enable_dpi_lcd=1
disable_splash=1
```
## Waveshare 4.3 DSI

Set following to config.txt and comment out Hyperpixel4 settings to use [Waveshare 4.3"](https://www.waveshare.com/4.3inch-dsi-lcd-with-case.htm) display:

```
# waveshare 4.3" DSI
dtoverlay=vc4-kms-v3d
dtoverlay=vc4-kms-dsi-7inch
dtparam=i2c_arm=on
display_rotate=1
```

If you wish to silence boot messages, use folllowing cmdline.txt:

```
root=/dev/mmcblk0p2 rootwait console=ttyAMA0,115200 quiet loglevel=3 systemd.show_status=false rd.udev.log_level=3 vt.global_cursor_default=0 logo.nologo
```


# Sound

In case you get 'broken pipe' error with your USB-C attached HF, add following:

```
# /etc/modprobe.d/sndusbaudio.conf 
options snd_usb_audio index=0 ignore_ctl_error=1
```

