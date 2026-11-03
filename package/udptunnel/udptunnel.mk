UDPTUNNEL_VERSION = a8da61c1e8d23caf79af74898697c4ac7b75dad3
UDPTUNNEL_SITE = $(call github,resiliencetheatre,udptunnel,$(UDPTUNNEL_VERSION))
UDPTUNNEL_PREFIX = $(TARGET_DIR)/usr

define UDPTUNNEL_BUILD_CMDS
     $(MAKE) $(TARGET_CONFIGURE_OPTS) -C $(@D)
endef

define UDPTUNNEL_INSTALL_TARGET_CMDS
        $(INSTALL) -D -m 0755 $(@D)/utun-node $(UDPTUNNEL_PREFIX)/bin/utun-node
        $(INSTALL) -D -m 0755 $(@D)/client $(UDPTUNNEL_PREFIX)/bin/client
        $(INSTALL) -D -m 0755 $(@D)/server $(UDPTUNNEL_PREFIX)/bin/server
endef

define UDPTUNNEL_CLEAN_CMDS
        $(MAKE) $(UDPTUNNEL_MAKE_OPTS) -C $(@D) clean
endef

$(eval $(generic-package))
