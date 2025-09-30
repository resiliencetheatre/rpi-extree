# Link

These are work in progress notes on Link image build and configuration.

# Building

Tested with buildroot commit ID: `5acd66ed0b91f3766ad8e43bdbb1635b39c9ad7c`

Build 'Link' image:

	export BR2_EXTERNAL=[PATH]/rpi-extree
	make clean
	make raspberrypi4_64_com_hyperpixel_defconfig
	git apply ${BR2_EXTERNAL}/patches/buildroot/0003-linux.patch
	make

Create MicroSD card

	sudo dd if=output/images/sdcard.img of=[TARGET_DEVICE] status=progress

