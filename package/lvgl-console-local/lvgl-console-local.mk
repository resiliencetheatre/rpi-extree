################################################################################
#
# lvgl-console-local
#
################################################################################

LVGL_CONSOLE_LOCAL_VERSION = local
LVGL_CONSOLE_LOCAL_SITE = $(abspath $(BR2_EXTERNAL_rpi_PATH)/../lvgl-console)
LVGL_CONSOLE_LOCAL_SITE_METHOD = local
LVGL_CONSOLE_LOCAL_DEPENDENCIES = libpng alsa-lib
LVGL_CONSOLE_LOCAL_LICENSE = MIT
LVGL_CONSOLE_LOCAL_LICENSE_FILES = LICENSE third_party/lvgl/LICENCE.txt

$(eval $(cmake-package))
