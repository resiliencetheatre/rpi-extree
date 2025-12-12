################################################################################
#
# edgemap
#
################################################################################

EDGEMAP_SITE = https://codeberg.org/resiliencetheatre/edgeui.git
EDGEMAP_VERSION = 8707f7939a2d58c452837bff3f7bd8a605626cb4
EDGEMAP_SITE_METHOD = git

EDGEMAP_LICENSE = Custom
EDGEMAP_LICENSE_FILES =

define EDGEMAP_INSTALL_TARGET_CMDS
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/opt/edgemap/edgeui
	cp -r -a $(@D)/* $(TARGET_DIR)/opt/edgemap/edgeui
endef

$(eval $(generic-package))
