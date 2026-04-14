# Link

Link is open source resilience demonstration for communication with confidence. 

# Build

Build 'Link' image:

	export BR2_EXTERNAL=[PATH]/rpi-extree
	make clean
	make raspberrypi4_64_com_hyperpixel_defconfig
	make

This first step build image with libfido2 enabled. After initial build is
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
