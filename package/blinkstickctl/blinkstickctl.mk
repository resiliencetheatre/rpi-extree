################################################################################
#
# blinkstickctl
#
################################################################################

# For reproducible Buildroot builds, replace "main" with a fixed commit hash
# or a release tag once you decide which repository revision to pin.
BLINKSTICKCTL_VERSION = da12584016ea097eec057b1dc2302173a4034b51
BLINKSTICKCTL_SITE = https://codeberg.org/resiliencetheatre/blinkstickctl.git
BLINKSTICKCTL_SITE_METHOD = git

BLINKSTICKCTL_DEPENDENCIES = libusb

define BLINKSTICKCTL_BUILD_CMDS
	$(TARGET_MAKE_ENV) $(MAKE) $(TARGET_CONFIGURE_OPTS) \
		-C $(@D) \
		blinkstickctl \
		LIBUSB_CFLAGS="-I$(STAGING_DIR)/usr/include/libusb-1.0" \
		LIBUSB_LIBS="-lusb-1.0"
endef

define BLINKSTICKCTL_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/blinkstickctl \
		$(TARGET_DIR)/usr/bin/blinkstickctl
endef

$(eval $(generic-package))
