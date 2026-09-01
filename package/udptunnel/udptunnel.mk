UDPTUNNEL_VERSION = d12d6a950b5382f42f1a8ddef7abd04a1ca4f5f4
UDPTUNNEL_SITE = $(call github,resiliencetheatre,udptunnel,$(UDPTUNNEL_VERSION))
UDPTUNNEL_PREFIX = $(TARGET_DIR)/usr

define UDPTUNNEL_BUILD_CMDS
     $(MAKE) $(TARGET_CONFIGURE_OPTS) -C $(@D)
endef

define UDPTUNNEL_INSTALL_TARGET_CMDS
        (cd $(@D); cp client server $(UDPTUNNEL_PREFIX)/bin)
endef

define UDPTUNNEL_CLEAN_CMDS
        $(MAKE) $(UDPTUNNEL_MAKE_OPTS) -C $(@D) clean
endef

$(eval $(generic-package))
