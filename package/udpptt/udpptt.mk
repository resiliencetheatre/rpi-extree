################################################################################
#
# udpptt
#
################################################################################

UDPPTT_VERSION = 5beff4f114afb6c530de47b3e3d173af75f15fd9
UDPPTT_SITE = https://codeberg.org/resiliencetheatre/udpptt.git
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
		ptt_client ptt_server

UDPPTT_INSTALL_TARGET_CMDS = \
	$(INSTALL) -D -m 0755 $(@D)/ptt_client $(TARGET_DIR)/usr/bin/ptt_client && \
	$(INSTALL) -D -m 0755 $(@D)/ptt_server $(TARGET_DIR)/usr/bin/ptt_server

$(eval $(generic-package))
