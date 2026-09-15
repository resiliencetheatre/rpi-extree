################################################################################
#
# hsmproxy
#
################################################################################

HSMPROXY_VERSION = d35e33af6171b2d58d5b804aca05f4a07942d517
HSMPROXY_SITE = $(call github,resiliencetheatre,hsmproxy,$(HSMPROXY_VERSION))
# Upstream does not declare a license or ship a license file.
HSMPROXY_LICENSE = UNKNOWN
HSMPROXY_DEPENDENCIES = host-pkgconf openssl pcsc-lite p11-kit opensc ccid

define HSMPROXY_BUILD_CMDS
	$(TARGET_MAKE_ENV) $(TARGET_CONFIGURE_OPTS) \
		CFLAGS="$(TARGET_CFLAGS) -Wno-error=unused-result" \
		$(MAKE) -C $(@D)
endef

define HSMPROXY_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/hsmproxy $(TARGET_DIR)/usr/bin/hsmproxy
endef

$(eval $(generic-package))
