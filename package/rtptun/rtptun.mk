RTPTUN_VERSION = v0.5
RTPTUN_SITE = https://github.com/me-asri/rtptun.git
RTPTUN_SITE_METHOD = git
RTPTUN_PREFIX = $(TARGET_DIR)/usr


define RTPTUN_BUILD_CMDS
     $(MAKE) $(TARGET_CONFIGURE_OPTS) -C $(@D)
endef

define RTPTUN_INSTALL_TARGET_CMDS
        (cd $(@D); cp bin/rel/rtptun $(RTPTUN_PREFIX)/bin)
endef

define RTPTUN_CLEAN_CMDS
        $(MAKE) $(RTPTUN_MAKE_OPTS) -C $(@D) clean
endef

$(eval $(generic-package))
