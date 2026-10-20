################################################################################
#
# lvgl-console
#
################################################################################

LVGL_CONSOLE_VERSION = 4008d60b5c4d906d4ef5720c409f2961d0334375
LVGL_CONSOLE_SITE = https://github.com/resiliencetheatre/lvgl-console.git
LVGL_CONSOLE_SITE_METHOD = git
LVGL_CONSOLE_DEPENDENCIES = libpng
LVGL_CONSOLE_LICENSE = MIT
LVGL_CONSOLE_LICENSE_FILES = LICENSE third_party/lvgl/LICENCE.txt

$(eval $(cmake-package))
