GSOCKET_VERSION = v1.4.43
GSOCKET_SITE = $(call github,hackerschoice,gsocket,$(GSOCKET_VERSION))
GSOCKET_PREFIX = $(TARGET_DIR)/usr
GSOCKET_INSTALL_STAGING = YES
GSOCKET_AUTORECONF = YES
GSOCKET_CONF_OPTS = --disable-tools --disable-static

$(eval $(autotools-package))

