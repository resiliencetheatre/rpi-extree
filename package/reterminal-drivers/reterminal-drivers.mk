################################################################################
#
# reterminal-drivers
#
################################################################################

RETERMINAL_DRIVERS_VERSION = 1
RETERMINAL_DRIVERS_SITE = $(BR2_EXTERNAL_rpi_PATH)/package/reterminal-drivers/src
RETERMINAL_DRIVERS_SITE_METHOD = local
RETERMINAL_DRIVERS_LICENSE = GPL-2.0
RETERMINAL_DRIVERS_LICENSE_FILES = COPYING

$(eval $(kernel-module))
$(eval $(generic-package))
