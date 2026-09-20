################################################################################
#
# lvgl-video
#
################################################################################

LVGL_VIDEO_VERSION = 7a9f7257fd6fb7c1babc4401d4e23ca6524c65dc
LVGL_VIDEO_SITE = https://github.com/resiliencetheatre/lvgl-video.git
LVGL_VIDEO_SITE_METHOD = git
LVGL_VIDEO_DEPENDENCIES = host-pkgconf gstreamer1 gst1-plugins-base gst1-plugins-good gst1-plugins-bad libcamera
LVGL_VIDEO_LICENSE = MIT
LVGL_VIDEO_LICENSE_FILES = LICENSE third_party/lvgl/LICENCE.txt

ifeq ($(BR2_PACKAGE_LVGL_VIDEO_WAYLAND),y)
LVGL_VIDEO_DEPENDENCIES += host-wayland wayland wayland-protocols libxkbcommon
LVGL_VIDEO_CONF_OPTS += \
	-DLVGL_VIDEO_BACKEND=wayland \
	-DWAYLAND_SCANNER_EXECUTABLE=$(HOST_DIR)/bin/wayland-scanner \
	-DWAYLAND_PROTOCOLS_DIR=$(STAGING_DIR)/usr/share/wayland-protocols
else
LVGL_VIDEO_CONF_OPTS += -DLVGL_VIDEO_BACKEND=fbdev
endif

$(eval $(cmake-package))
