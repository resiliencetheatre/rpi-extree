################################################################################
#
# edgemap
#
################################################################################

EDGEMAP_SITE = https://codeberg.org/resiliencetheatre/edgeui.git
EDGEMAP_VERSION = 790216fb7d3aab3e1f61d3fa1eaefa7251b19b37
EDGEMAP_SITE_METHOD = git

EDGEMAP_LICENSE = Custom
EDGEMAP_LICENSE_FILES =

define EDGEMAP_INSTALL_TARGET_CMDS
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/opt/edgemap/edgeui
	cp -r -a $(@D)/* $(TARGET_DIR)/opt/edgemap/edgeui
endef

$(eval $(generic-package))
