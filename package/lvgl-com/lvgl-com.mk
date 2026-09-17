LVGL_COM_VERSION = 03205ae19b71effc005daae61f8592955adbb110
LVGL_COM_SITE = https://github.com/resiliencetheatre/lvgl-com.git
LVGL_COM_SITE_METHOD = git
LVGL_COM_DEPENDENCIES = libpng zlib
LVGL_COM_LICENSE = MIT, BSD-2-Clause
LVGL_COM_LICENSE_FILES = LICENSE third_party/lvgl/LICENCE.txt src/mini.c src/log.c

ifeq ($(BR2_PACKAGE_LVGL_COM_WAYLAND),y)
LVGL_COM_DEPENDENCIES += host-pkgconf host-wayland wayland wayland-protocols libxkbcommon
LVGL_COM_CONF_OPTS += \
	-DLVGL_COM_BACKEND=wayland \
	-DWAYLAND_SCANNER_EXECUTABLE=$(HOST_DIR)/bin/wayland-scanner \
	-DWAYLAND_PROTOCOLS_DIR=$(STAGING_DIR)/usr/share/wayland-protocols
else
LVGL_COM_CONF_OPTS += -DLVGL_COM_BACKEND=fbdev
endif

$(eval $(cmake-package))
