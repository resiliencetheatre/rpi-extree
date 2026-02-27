C2STREAM_VERSION = aa87efef72eeaf79a2472001645e2600ee4898a1
C2STREAM_SITE = https://codeberg.org/resiliencetheatre/c2stream.git
C2STREAM_SITE_METHOD = git
C2STREAM_DEPENDENCIES = gstreamer1 gst1-plugins-base
C2STREAM_PREFIX = $(TARGET_DIR)/usr
C2STREAM_LICENSE = gplv2

define C2STREAM_BUILD_CMDS
     $(MAKE) $(TARGET_CONFIGURE_OPTS) -C $(@D)
endef

define C2STREAM_INSTALL_TARGET_CMDS
        (cd $(@D); cp c2receiver c2streamer $(C2STREAM_PREFIX)/bin)
endef

define C2STREAM_CLEAN_CMDS
        $(MAKE) $(C2STREAM_MAKE_OPTS) -C $(@D) clean
endef

$(eval $(generic-package))

