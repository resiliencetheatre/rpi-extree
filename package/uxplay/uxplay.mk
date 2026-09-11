################################################################################
#
# uxplay
#
################################################################################

UXPLAY_VERSION = 9f3c2bbc658645533fa1057e76c29ec8c947fa0f
UXPLAY_SITE = $(call github,FDH2,UxPlay,$(UXPLAY_VERSION))
UXPLAY_LICENSE = GPL-3.0
UXPLAY_LICENSE_FILES = LICENSE

UXPLAY_DEPENDENCIES = \
	host-pkgconf \
	openssl \
	libplist \
	gstreamer1 \
	gst1-plugins-base \
	gst1-plugins-good \
	gst1-plugins-bad \
	gst1-libav \
	avahi

UXPLAY_CONF_OPTS = \
	-DNO_MARCH_NATIVE=ON \
	-DNO_X11_DEPS=ON \
	-DUSE_DNS_SD=ON

define UXPLAY_INSTALL_INIT_SYSTEMD
	$(INSTALL) -D -m 0644 \
		$(UXPLAY_PKGDIR)/uxplay.service \
		$(TARGET_DIR)/usr/lib/systemd/system/uxplay.service
endef

$(eval $(cmake-package))
