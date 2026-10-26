################################################################################
#
# lvgl-console
#
################################################################################

LVGL_CONSOLE_VERSION = 171abb4383d12278eecb3d3167e7f4f6d8a2d86b
LVGL_CONSOLE_SITE = https://github.com/resiliencetheatre/lvgl-console.git
LVGL_CONSOLE_SITE_METHOD = git
LVGL_CONSOLE_DEPENDENCIES = libpng alsa-lib
LVGL_CONSOLE_LICENSE = MIT
LVGL_CONSOLE_LICENSE_FILES = LICENSE third_party/lvgl/LICENCE.txt

$(eval $(cmake-package))
