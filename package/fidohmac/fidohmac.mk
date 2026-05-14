################################################################################
#
# fidohmac
#
################################################################################

# Keep this as "main" for convenience during active development.
# For reproducible builds, replace it with a fixed upstream commit hash.
FIDOHMAC_VERSION = ca9beedbe203c03979c0d1c2ac01adc413598d95
FIDOHMAC_SITE = https://codeberg.org/resiliencetheatre/fidohmac.git
FIDOHMAC_SITE_METHOD = git

# If the project links against libraries provided by Buildroot packages,
# add them here, for example:
# FIDOHMAC_DEPENDENCIES = libfido2

# The upstream repository contents could not be inspected from the packaging
# environment that generated this file, so license metadata is intentionally
# left unset rather than guessed. Once confirmed, add for legal-info support:
# FIDOHMAC_LICENSE = <SPDX-ID>
# FIDOHMAC_LICENSE_FILES = LICENSE

define FIDOHMAC_BUILD_CMDS
	$(TARGET_MAKE_ENV) $(MAKE) -C $(@D) \
		CC="$(TARGET_CC)" \
		AR="$(TARGET_AR)" \
		RANLIB="$(TARGET_RANLIB)" \
		STRIP="$(TARGET_STRIP)" \
		CFLAGS="$(TARGET_CFLAGS)" \
		LDFLAGS="$(TARGET_LDFLAGS)"
endef

# Assumes the project builds a binary named "fidohmac" in its top-level
# source directory. If upstream already provides a proper "install" target,
# this block can instead call:
#   $(TARGET_MAKE_ENV) $(MAKE) -C $(@D) DESTDIR=$(TARGET_DIR) PREFIX=/usr install
define FIDOHMAC_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/fido_hmac_enroll \
		$(TARGET_DIR)/usr/bin/fido_hmac_enroll
	$(INSTALL) -D -m 0755 $(@D)/fido_hmac_demo \
		$(TARGET_DIR)/usr/bin/fido_hmac_demo
endef

$(eval $(generic-package))
