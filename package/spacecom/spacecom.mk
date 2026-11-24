################################################################################
#
# spacecom
#
################################################################################

SPACECOM_VERSION = ef353c7e842fc12166a5b23181f1c7c3d16f0b0b
SPACECOM_SITE = https://github.com/resiliencetheatre/spacecom.git
SPACECOM_SITE_METHOD = git

# Set this to the real license once you decide what to expose in the repo
SPACECOM_LICENSE = Proprietary

SPACECOM_DEPENDENCIES = norm openssl sqlite

SPACECOM_MAKE_ENV = $(TARGET_MAKE_ENV)

SPACECOM_MAKE_OPTS = \
	$(TARGET_CONFIGURE_OPTS) \
	PKG_CONFIG="$(PKG_CONFIG_HOST_BINARY)" \
	PREFIX=/usr

define SPACECOM_BUILD_CMDS
	$(SPACECOM_MAKE_ENV) $(MAKE) -C $(@D) $(SPACECOM_MAKE_OPTS)
endef

define SPACECOM_INSTALL_TARGET_CMDS
	$(SPACECOM_MAKE_ENV) $(MAKE) -C $(@D) \
		$(SPACECOM_MAKE_OPTS) \
		DESTDIR="$(TARGET_DIR)" \
		install
	$(INSTALL) -D -m 0755 $(@D)/spacecomd $(TARGET_DIR)/usr/bin/spacecomd
endef

$(eval $(generic-package))
