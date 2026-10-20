################################################################################
#
# lvgl-console
#
################################################################################

LVGL_CONSOLE_VERSION = 5a93a4f477384120834537156967863a7019b29d
LVGL_CONSOLE_SITE = https://github.com/resiliencetheatre/lvgl-console.git
LVGL_CONSOLE_SITE_METHOD = git
LVGL_CONSOLE_DEPENDENCIES = libpng
LVGL_CONSOLE_LICENSE = MIT
LVGL_CONSOLE_LICENSE_FILES = LICENSE third_party/lvgl/LICENCE.txt

$(eval $(cmake-package))
