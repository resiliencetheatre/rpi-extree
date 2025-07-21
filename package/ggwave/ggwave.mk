################################################################################
#
# GGWAVE
#
################################################################################

GGWAVE_VERSION = bef9afbf0c924160695ef3c84264f5e98c2a0fdf
GGWAVE_SITE = https://github.com/ggerganov/ggwave.git
GGWAVE_SITE_METHOD = git
GGWAVE_CONF_OPTS = -DGGWAVE_SUPPORT_SDL2=OFF -DGGWAVE_SUPPORT_SWIFT=OFF -DGGWAVE_SUPPORT_PYTHON=OFF
GGWAVE_INSTALL_STAGING = YES
GGWAVE_INSTALL_TARGET = YES
GGWAVE_GIT_SUBMODULES = YES
$(eval $(cmake-package))
