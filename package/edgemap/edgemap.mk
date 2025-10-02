################################################################################
#
# edgemap
#
################################################################################

EDGEMAP_SITE = https://codeberg.org/resiliencetheatre/edgeui.git
EDGEMAP_VERSION = 87578947210c0b8e1ca9039113637e554812ef34
EDGEMAP_SITE_METHOD = git

EDGEMAP_LICENSE = Custom
EDGEMAP_LICENSE_FILES =

define EDGEMAP_INSTALL_TARGET_CMDS
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/opt/edgemap
	cp -a $(@D)/* $(TARGET_DIR)/opt/edgemap/
endef

$(eval $(generic-package))
