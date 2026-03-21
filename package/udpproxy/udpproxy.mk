UDPPROXY_VERSION = adbef488d5cb8bb22517afc5c65bbd6d09856066
UDPPROXY_SITE = https://codeberg.org/resiliencetheatre/udpproxy.git
UDPPROXY_SITE_METHOD = git
UDPPROXY_PREFIX = $(TARGET_DIR)/usr

define UDPPROXY_BUILD_CMDS
     $(MAKE) $(TARGET_CONFIGURE_OPTS) -C $(@D)
endef

define UDPPROXY_INSTALL_TARGET_CMDS
        (cd $(@D); cp udpproxy $(UDPPROXY_PREFIX)/bin)
endef

define UDPPROXY_CLEAN_CMDS
        $(MAKE) $(UDPPROXY_MAKE_OPTS) -C $(@D) clean
endef

$(eval $(generic-package))
