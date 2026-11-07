################################################################################
#
# vcgencmd
#
################################################################################

VCGENCMD_VERSION = 20261106
VCGENCMD_SITE = $(BR2_EXTERNAL_rpi_PATH)/package/vcgencmd/src
VCGENCMD_SITE_METHOD = local
VCGENCMD_LICENSE = BSD-3-Clause
VCGENCMD_LICENSE_FILES = vcgencmd.c

define VCGENCMD_BUILD_CMDS
	$(TARGET_MAKE_ENV) $(TARGET_CC) $(TARGET_CFLAGS) $(TARGET_LDFLAGS) \
		-o $(@D)/vcgencmd $(@D)/vcgencmd.c
endef

define VCGENCMD_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/vcgencmd $(TARGET_DIR)/usr/bin/vcgencmd
endef

$(eval $(generic-package))
