# Edgemap

This is work in progress documentation to next gen edgemap build.

## Building

	cd [PATH]
	git clone https://gitlab.com/buildroot.org/buildroot.git
	git clone https://codeberg.org/resiliencetheatre/rpi-extree.git
	export BR2_EXTERNAL=[PATH]/rpi-extree
	cd [PATH]/buildroot/
	# Use defconfig and patch kernel hash to buildtree
	make raspberrypi4_edgemap_lite_defconfig
	git apply ../rpi-extree/patches/buildroot/0003-linux.patch
	# Start make, this could takes few hours
	make 
	# After make completes, create MicroSD card
	sudo dd if=output/images/sdcard.img of=/dev/[DEVICE] status=progress

## Configuration

	# init-edgemap.sh [CA-NAME] [HOSTNAME]
	# reboot

## Copy map data

You need to copy `planet.pmtiles` under `/opt/data` and do symbolic link to `/opt/edgemap/edgeui`

	ln -s /opt/data/planet.pmtiles /opt/edgemap/edgeui

You can also copy `terrarium-z12.pmtiles` under `/opt/data` and do symbolic link to `/opt/edgemap/edgeui`

	ln -s /opt/data/terrarium-z12.pmtiles /opt/edgemap/edgeui/terrarium_z9.pmtiles

