################################################################################
# libcbor
################################################################################

LIBCBOR_VERSION       = 0.13.0
LIBCBOR_SITE          = $(call github,PJK,libcbor,v$(LIBCBOR_VERSION))
LIBCBOR_SOURCE        = libcbor-v$(LIBCBOR_VERSION).tar.gz
LIBCBOR_LICENSE       = MIT
LIBCBOR_LICENSE_FILES = LICENSE
LIBCBOR_INSTALL_STAGING = YES
LIBCBOR_CONF_OPTS     = -DWITH_TESTS=OFF -DWITH_EXAMPLES=OFF

$(eval $(cmake-package))

