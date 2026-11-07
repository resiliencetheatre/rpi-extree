################################################################################
#
# rpi-tryboot-firmware
#
################################################################################

RPI_TRYBOOT_FIRMWARE_VERSION = ab5c7f86283ceb58b7adb269cae1d16092a31bf6
RPI_TRYBOOT_FIRMWARE_SITE = https://raw.githubusercontent.com/raspberrypi/firmware/$(RPI_TRYBOOT_FIRMWARE_VERSION)/boot
RPI_TRYBOOT_FIRMWARE_SOURCE = start4.elf
RPI_TRYBOOT_FIRMWARE_EXTRA_DOWNLOADS = \
	$(RPI_TRYBOOT_FIRMWARE_SITE)/fixup4.dat \
	$(RPI_TRYBOOT_FIRMWARE_SITE)/LICENCE.broadcom
RPI_TRYBOOT_FIRMWARE_LICENSE = BSD-3-Clause
RPI_TRYBOOT_FIRMWARE_LICENSE_FILES = LICENCE.broadcom
RPI_TRYBOOT_FIRMWARE_INSTALL_TARGET = NO
RPI_TRYBOOT_FIRMWARE_INSTALL_IMAGES = YES
# Prebuilt boot files only: no target compiler or rootfs skeleton is needed.
RPI_TRYBOOT_FIRMWARE_ADD_TOOLCHAIN_DEPENDENCY = NO
RPI_TRYBOOT_FIRMWARE_ADD_SKELETON_DEPENDENCY = NO

define RPI_TRYBOOT_FIRMWARE_EXTRACT_CMDS
	$(foreach f,start4.elf fixup4.dat LICENCE.broadcom, \
		$(INSTALL) -m 0644 $(RPI_TRYBOOT_FIRMWARE_DL_DIR)/$(f) $(@D)/$(f)$(sep))
endef

define RPI_TRYBOOT_FIRMWARE_INSTALL_IMAGES_CMDS
	$(foreach f,start4.elf fixup4.dat LICENCE.broadcom, \
		$(INSTALL) -D -m 0644 $(@D)/$(f) $(BINARIES_DIR)/rpi-tryboot-firmware/$(f)$(sep))
	printf '%s\n' '$(RPI_TRYBOOT_FIRMWARE_VERSION)' > $(BINARIES_DIR)/rpi-tryboot-firmware/revision
endef

$(eval $(generic-package))
