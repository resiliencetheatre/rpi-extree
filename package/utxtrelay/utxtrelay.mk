################################################################################
#
# utxtrelay
#
################################################################################

UTXTRELAY_VERSION = 6e99ff5e8a0bbf30b911765550e32b36d2748d29
UTXTRELAY_SITE = https://github.com/resiliencetheatre/utxtrelay.git
UTXTRELAY_SITE_METHOD = git
UTXTRELAY_DEPENDENCIES = libsodium
# Upstream currently supplies no license declaration/file.
UTXTRELAY_LICENSE = UNKNOWN

define UTXTRELAY_BUILD_CMDS
	$(TARGET_MAKE_ENV) $(MAKE) -C $(@D) clean
	$(TARGET_MAKE_ENV) $(MAKE) -C $(@D) WITH_CURSES=0 \
		CC="$(TARGET_CC)" \
		CFLAGS="$(TARGET_CFLAGS) -D_DEFAULT_SOURCE -D_POSIX_C_SOURCE=200809L -D_XOPEN_SOURCE=700 -std=c99" \
		LDFLAGS="$(TARGET_LDFLAGS)"
endef

define UTXTRELAY_INSTALL_TARGET_CMDS
	$(TARGET_MAKE_ENV) $(MAKE) -C $(@D) WITH_CURSES=0 \
		DESTDIR="$(TARGET_DIR)" PREFIX=/usr install
endef

$(eval $(generic-package))
