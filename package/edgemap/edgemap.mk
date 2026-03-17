################################################################################
#
# edgemap
#
################################################################################

EDGEMAP_SITE = https://codeberg.org/resiliencetheatre/edgeui.git
EDGEMAP_VERSION = 12cb991a8a414be5f29ee4fb2484888cfd40778a
EDGEMAP_SITE_METHOD = git

EDGEMAP_LICENSE = Custom
EDGEMAP_LICENSE_FILES =

define EDGEMAP_INSTALL_TARGET_CMDS
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/opt/edgemap/edgeui
	cp -r -a $(@D)/* $(TARGET_DIR)/opt/edgemap/edgeui
endef

$(eval $(generic-package))
