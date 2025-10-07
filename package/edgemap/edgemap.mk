################################################################################
#
# edgemap
#
################################################################################

EDGEMAP_SITE = https://codeberg.org/resiliencetheatre/edgeui.git
EDGEMAP_VERSION = 5c4b9eda8a64d8345ad2f3df10d991f5ad8b4d0a
EDGEMAP_SITE_METHOD = git

EDGEMAP_LICENSE = Custom
EDGEMAP_LICENSE_FILES =

define EDGEMAP_INSTALL_TARGET_CMDS
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/opt/edgemap
	cp -a $(@D)/* $(TARGET_DIR)/opt/edgemap/
endef

$(eval $(generic-package))
