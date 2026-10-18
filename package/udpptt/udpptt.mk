################################################################################
#
# udpptt
#
################################################################################

UDPPTT_VERSION = 325404790e50bcb69542ff0fc7edd6ea55a5e187
UDPPTT_SITE = https://github.com/resiliencetheatre/udpptt.git
UDPPTT_SITE_METHOD = git
UDPPTT_LICENSE = GPL-3.0-or-later
UDPPTT_LICENSE_FILES =

UDPPTT_DEPENDENCIES = gstreamer1 gst1-plugins-base gst1-plugins-good libsodium

UDPPTT_BUILD_CMDS = \
	$(TARGET_MAKE_ENV) $(MAKE) -C $(@D) \
		CC="$(TARGET_CC)" \
		CFLAGS="$(TARGET_CFLAGS)" \
		LDFLAGS="$(TARGET_LDFLAGS)" \
		PKG_CONFIG="$(PKG_CONFIG_HOST_BINARY)" \
		ptt_client ptt_server ptt_helper ptt_dpi_keygen

UDPPTT_INSTALL_TARGET_CMDS = \
	$(INSTALL) -D -m 0755 $(@D)/ptt_client $(TARGET_DIR)/usr/bin/ptt_client && \
	$(INSTALL) -D -m 0755 $(@D)/ptt_server $(TARGET_DIR)/usr/bin/ptt_server && \
	$(INSTALL) -D -m 0755 $(@D)/ptt_helper $(TARGET_DIR)/usr/bin/ptt_helper && \
	$(INSTALL) -D -m 0755 $(@D)/ptt_dpi_keygen $(TARGET_DIR)/usr/bin/ptt_dpi_keygen

$(eval $(generic-package))
