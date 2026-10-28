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
# Package accounts are added during filesystem image generation, not in
# output/target. Preserve the device's account databases as a consistent set.
# Deploy a generated filesystem image when adding new package accounts.
RSYNC_EXCLUDE =   --exclude="/etc/hostname" --exclude="/etc/passwd" --exclude='etc/dropbear' \
--exclude='/etc/group' --exclude='/etc/gshadow' \
--exclude='/etc/shadow' --exclude='/tmp/*' --exclude='/dev/*' --exclude='*~' \
--exclude='/etc/hosts' --exclude='/etc/default/udpptt.usb-hf' --exclude='/etc/default/udpptt.usb-monofone' --exclude='/etc/default/udpptt' --exclude='/root/.config/udpptt/*'

TARGET_IP ?= rpi4
SSHPORT = 22
WG_INIT_DIR ?= $(HOME)/laboratory/initialization-run/wg-init

all: rpi4

rpi4: 
	cd $(BUILDROOT_DIR) && make

rpi4_defconfig:
	cd $(BUILDROOT_DIR) && make $(CONFIG_FILE)

update_rootfs:
	$(info -------------------------------------------------------------------------------)
	$(info Updating current rootfs)
	$(info -------------------------------------------------------------------------------)
	# Install missing device profiles without replacing configured profiles.
	@if test -f $(BUILDROOT_DIR)/output/target/etc/default/udpptt.usb-hf && test -f $(BUILDROOT_DIR)/output/target/etc/default/udpptt.usb-monofone; then \
	    rsync -e "ssh -p $(SSHPORT) -l root" -rclvxW --ignore-existing --super \
	        $(BUILDROOT_DIR)/output/target/etc/default/udpptt.usb-hf \
	        $(BUILDROOT_DIR)/output/target/etc/default/udpptt.usb-monofone $(TARGET_IP)::root/etc/default/; \
	fi
	rsync -e "ssh  -p $(SSHPORT) -l root" $(RSYNC_EXCLUDE) -rclvxW --ignore-times --super $(BUILDROOT_DIR)/output/target/ $(TARGET_IP)::root

# Run on the provisioning machine:
# make provision_wg IP=10.0.0.15 TARGET_IP=rpi4
# Override WG_INIT_DIR if the provisioning files live elsewhere.
# Requires root SSH access and wstunnel/systemd-networkd on the target.
.PHONY: provision_wg
provision_wg:
	@test -n "$(IP)" || { echo 'Usage: make provision_wg IP=10.0.0.15 TARGET_IP=rpi4' >&2; exit 1; }
	@for file in "$(WG_INIT_DIR)/$(IP)/wg0.netdev" "$(WG_INIT_DIR)/$(IP)/wg0.network" "$(WG_INIT_DIR)/client-systemd/wstunnel.service"; do \
	    test -f "$$file" && test -r "$$file" || { echo "Missing or unreadable provisioning file: $$file" >&2; exit 1; }; \
	done
	ssh -p $(SSHPORT) root@$(TARGET_IP) 'mkdir -p /etc/systemd/network /etc/systemd/system'
	scp -P $(SSHPORT) "$(WG_INIT_DIR)/$(IP)/wg0.netdev" "$(WG_INIT_DIR)/$(IP)/wg0.network" root@$(TARGET_IP):/etc/systemd/network/
	scp -P $(SSHPORT) "$(WG_INIT_DIR)/client-systemd/wstunnel.service" root@$(TARGET_IP):/etc/systemd/system/
	ssh -p $(SSHPORT) root@$(TARGET_IP) 'chown root:systemd-network /etc/systemd/network/wg0.netdev /etc/systemd/network/wg0.network && \
	    chmod 640 /etc/systemd/network/wg0.netdev /etc/systemd/network/wg0.network && \
	    chown root:root /etc/systemd/system/wstunnel.service && \
	    chmod 644 /etc/systemd/system/wstunnel.service && \
	    systemctl daemon-reload && \
	    systemctl enable --now wstunnel && \
	    systemctl enable systemd-networkd && \
	    systemctl restart systemd-networkd'

update_kernel:
	$(info -------------------------------------------------------------------------------)
	$(info Updating kernel)
	$(info -------------------------------------------------------------------------------)
	ssh root@$(TARGET_IP) "mount /dev/mmcblk0p1 /boot/"
	scp $(BUILDROOT_DIR)/output/images/Image root@$(TARGET_IP):/boot/Image
	ssh root@$(TARGET_IP) "umount /boot"

clean:
	cd $(BUILDROOT_DIR) && make clean

# Run with the PocketTerm defconfig already selected. Rebuild before deployment
# so CMake-installed files and the board overlay both reach output/target.
.PHONY: update_pocketterm
update_pocketterm:
	$(MAKE) -C $(BUILDROOT_DIR) utxtrelay-rebuild
	$(MAKE) -C $(BUILDROOT_DIR) lvgl-console-local-rebuild
	$(MAKE) -C $(BUILDROOT_DIR)
	test -x $(BUILDROOT_DIR)/output/target/usr/libexec/udpptt-audio-select
	test -f $(BUILDROOT_DIR)/output/target/etc/default/udpptt.usb-hf
	test -f $(BUILDROOT_DIR)/output/target/etc/default/udpptt.usb-monofone
	grep -Fq 'UDPPTT_PREAMBLE_ENABLED' $(BUILDROOT_DIR)/output/target/usr/libexec/udpptt-prepare
	grep -Fq '$$UDPPTT_PREAMBLE_ARGS' $(BUILDROOT_DIR)/output/target/etc/systemd/system/udpptt.service
	grep -Fq '$$UDPPTT_DEVICE_ARGS' $(BUILDROOT_DIR)/output/target/etc/systemd/system/udpptt.service
	$(MAKE) update_rootfs
	ssh -p $(SSHPORT) root@$(TARGET_IP) 'systemctl daemon-reload && systemctl restart utxtrelay-console-client.service udpptt.service lvgl-console.service'
