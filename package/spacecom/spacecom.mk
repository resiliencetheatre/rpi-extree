################################################################################
#
# spacecom
#
################################################################################

SPACECOM_VERSION = ba8823505b4038d45ad27b9d282091169c552e13
SPACECOM_SITE = https://codeberg.org/resiliencetheatre/spacecom.git
SPACECOM_SITE_METHOD = git

# Set this to the real license once you decide what to expose in the repo
SPACECOM_LICENSE = Proprietary

SPACECOM_DEPENDENCIES = norm

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
endef

$(eval $(generic-package))
