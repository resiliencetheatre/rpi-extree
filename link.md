# Link

Link is open source resilience demonstration for communication with confidence. 

## Features

* Suitable for small scale embedded SoC's (broadcom, rockchip, risc-v)
* Full source code available for on-prem building and modifications
* Buildroot supported [[https://buildroot.org/downloads/manual/manual.html#_generating_cyclonedx_sbom|CycloneDX SBOM]]
* Fully controlled server entity for connectivity between NAT'ed entities
* Server entity does not store communication content or presist data
* Functionality is fully ephemeral and point-to-point
* Three operating modes: Push-To-Talk (PTT), Full Duplex voice and SATCOM Push-To-Talk
* Three encryption examples: plain text, symmetric (XChaCha20) and logical XOR
* Speech compression with OPUS and CODEC2, depending the mode
* Capable to deliver two way speech communication via GEO satellite communication systems
* Can be used with [[https://en.wikipedia.org/wiki/Dark_fibre|dark fiber]] or twisted pair copper lines
* Training platform for crypto agility, onboard your implementation and train on platform threats
* User interface with [[https://lvgl.io/|LVGL]] on top of framebuffer

## Bill of materials, Rasbperry Pi

* [[https://www.raspberrypi.com/products/raspberry-pi-4-model-b/|Raspberry Pi4]]
* [[https://shop.pimoroni.com/products/hyperpixel-4?variant=12569485443155|Hyperpixel 4.0 display]
* [[https://shop.nitrokey.com/shop/nk3an-nitrokey-3a-nfc-147|Nitrokey 3A NFC]]
* USB headset
* [[https://www.printables.com/model/689580-raspberry-pi-4-hyperpixel-40-standing-portrait-cas|Case 1]]
* [[https://www.printables.com/model/157791-hyperpixel-40-pi-4-case|Case 2]]

## Bill of materials, Rockchip

* [[https://www.vividunit.com|Vivid unit]]

## Bill of materials, RISC-V

* [[https://www.waveshare.com/wiki/VisionFive2|VisionFive2]]

## Prepare buildroot

Clone buildroot and rpi-extree repositories:

    git clone https://gitlab.com/buildroot.org/buildroot.git
    git clone https://codeberg.org/resiliencetheatre/rpi-extree.git

## Build

Build 'Link' image:
    
    cd builroot
	export BR2_EXTERNAL=[PATH]/rpi-extree
	make clean
	make raspberrypi4_64_com_hyperpixel_defconfig
	make

This first step builds image with libfido2 enabled. After initial build is
completed, you need to change `SYSTEMD_CONF_OPTS` at `package/systemd/systemd.mk`
to enable fido2 support for systemd. Change `-Dlibfido2=disabled` to `-Dlibfido2=enabled`
and rebuild systemd and full image. 

    make systemd-dirclean
    make systemd-rebuild
    make

Now you have image which have systemd with FIDO2 token support enabled.

## Create MicroSD card

	sudo dd if=output/images/sdcard.img of=[TARGET_DEVICE] status=progress

After card creation is completed, re-insert card and mount rootfs partition 
so that you could copy your ssh key to `/root/.ssh/authorized_keys`. With
this you are able to SSH as root to unit and take following steps.

# Configure

[TBC]
