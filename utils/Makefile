#
# Top level Makefile
#
# ~/buildirectory
# |
# |--Makefile <-- Create this make file
# |--buildroot
# |--rpi4ext
#
#
# This Makefile allows you to iterate faster with cross compiling and
# updating target device with rsync.
#
# To use this Makefile, place /etc/rsyncd.conf to target device:
#
# pid file = /tmp/rsyncd.pid
# log file = /tmp/rsync
# [root]
# vpath = /
# vuid = 0
# vgid = 0
# read only = false
#
# And start: rsync --daemon on target
#
# Now you can update your rootfs with: make update_rootfs
#
# Generate ssh keys for target and place rpi4 to /etc/hosts or
# use ip address at: TARGET_IP ?= rpi4
#
#
COD_DIR=.
BUILDROOT_DIR = $(COD_DIR)/buildroot
CONFIG_FILE ?= raspberrypi4_64_defconfig
RSYNC_EXCLUDE =   --exclude="/etc/hostname" --exclude="/etc/passwd" --exclude='etc/dropbear' \
--exclude='/etc/shadow' --exclude='/tmp/*' --exclude='/dev/*' --exclude='*~' \
--exclude='/etc/hosts' 

TARGET_IP ?= rpi4
SSHPORT = 22

all: rpi4

rpi4: 
	cd $(BUILDROOT_DIR) && make

rpi4_defconfig:
	cd $(BUILDROOT_DIR) && make $(CONFIG_FILE)

update_rootfs:
	$(info -------------------------------------------------------------------------------)
	$(info Updating current rootfs)
	$(info -------------------------------------------------------------------------------)
	rsync -e "ssh  -p $(SSHPORT) -l root" $(RSYNC_EXCLUDE) -rclvxW --ignore-times --super $(BUILDROOT_DIR)/output/target/ $(TARGET_IP)::root

update_kernel:
	$(info -------------------------------------------------------------------------------)
	$(info Updating kernel)
	$(info -------------------------------------------------------------------------------)
	ssh root@$(TARGET_IP) "mount /dev/mmcblk0p1 /boot/"
	scp $(BUILDROOT_DIR)/output/images/Image root@$(TARGET_IP):/boot/Image
	ssh root@$(TARGET_IP) "umount /boot"

clean:
	cd $(BUILDROOT_DIR) && make clean
