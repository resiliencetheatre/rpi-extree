C2PTT_VERSION = 53ce5f83936ab827223211ba3c011588d1d2cd8e
C2PTT_SITE = https://codeberg.org/resiliencetheatre/c2ptt.git
C2PTT_SITE_METHOD = git
C2PTT_DEPENDENCIES = gstreamer1 gst1-plugins-base
C2PTT_PREFIX = $(TARGET_DIR)/usr
C2PTT_LICENSE = gplv2

define C2PTT_BUILD_CMDS
     $(MAKE) $(TARGET_CONFIGURE_OPTS) -C $(@D)
endef

define C2PTT_INSTALL_TARGET_CMDS
        (cd $(@D); cp pttkey_rec play_spool $(C2PTT_PREFIX)/bin)
endef

define C2PTT_CLEAN_CMDS
        $(MAKE) $(C2PTT_MAKE_OPTS) -C $(@D) clean
endef

$(eval $(generic-package))

