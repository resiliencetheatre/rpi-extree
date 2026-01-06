################################################################################
#
# edgemap
#
################################################################################

EDGEMAP_SITE = https://codeberg.org/resiliencetheatre/edgeui.git
EDGEMAP_VERSION = 1863d79d58f647108c3483aff7e41829c0e2e64a
EDGEMAP_SITE_METHOD = git

EDGEMAP_LICENSE = Custom
EDGEMAP_LICENSE_FILES =

define EDGEMAP_INSTALL_TARGET_CMDS
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/opt/edgemap/edgeui
	cp -r -a $(@D)/* $(TARGET_DIR)/opt/edgemap/edgeui
endef

$(eval $(generic-package))
