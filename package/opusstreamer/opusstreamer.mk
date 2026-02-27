OPUSSTREAMER_VERSION = 60c9717350da61a2dfff05d890bcf9f936c4de37
OPUSSTREAMER_SITE = https://codeberg.org/resiliencetheatre/opusstreamer.git
OPUSSTREAMER_SITE_METHOD = git
OPUSSTREAMER_DEPENDENCIES = gstreamer1 gst1-plugins-base
OPUSSTREAMER_PREFIX = $(TARGET_DIR)/usr
OPUSSTREAMER_LICENSE = gplv2

define OPUSSTREAMER_BUILD_CMDS
     $(MAKE) $(TARGET_CONFIGURE_OPTS) -C $(@D)
endef

define OPUSSTREAMER_INSTALL_TARGET_CMDS
        (cd $(@D); cp audiostreamer $(OPUSSTREAMER_PREFIX)/bin)
        (cd $(@D); cp audioreceiver $(OPUSSTREAMER_PREFIX)/bin)
endef

define OPUSSTREAMER_CLEAN_CMDS
        $(MAKE) $(OPUSSTREAMER_MAKE_OPTS) -C $(@D) clean
endef

$(eval $(generic-package))
