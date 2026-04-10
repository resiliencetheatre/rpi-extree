################################################################################
#
# knock-daemon
#
################################################################################

KNOCK_DAEMON_VERSION = 32145c0b9a8687b4e28a2620025b6e16fb418fc3
KNOCK_DAEMON_SITE = https://codeberg.org/resiliencetheatre/knock-daemon.git
KNOCK_DAEMON_SITE_METHOD = git

define KNOCK_DAEMON_BUILD_CMDS
	$(TARGET_MAKE_ENV) $(MAKE) -C $(@D) \
		CC="$(TARGET_CC)" \
		CFLAGS="$(TARGET_CFLAGS)" \
		LDFLAGS="$(TARGET_LDFLAGS)"
endef

define KNOCK_DAEMON_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/knock-send \
		$(TARGET_DIR)/usr/bin/knock-send
	$(INSTALL) -D -m 0755 $(@D)/knock-receiver \
		$(TARGET_DIR)/usr/bin/knock-receiver
        $(INSTALL) -D -m 0755 $(@D)/knock_cmd_receive \
                $(TARGET_DIR)/usr/bin/knock_cmd_receive
        $(INSTALL) -D -m 0755 $(@D)/knock_cmd_send \
                $(TARGET_DIR)/usr/bin/knock_cmd_send
endef

$(eval $(generic-package))
