################################################################################
#
# lvgl-video
#
################################################################################

LVGL_VIDEO_VERSION = bbbc1c53559ac45fe5fc85058170c16bfcc5ba8a
LVGL_VIDEO_SITE = https://github.com/resiliencetheatre/lvgl-video.git
LVGL_VIDEO_SITE_METHOD = git
LVGL_VIDEO_DEPENDENCIES = host-pkgconf gstreamer1 gst1-plugins-base libcamera
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
