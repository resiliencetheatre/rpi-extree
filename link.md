# Link

Link is open source resilience demonstration for communication with confidence. 

## Features

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
