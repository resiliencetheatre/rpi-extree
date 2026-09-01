################################################################################
#
# GWSOCKET
#
################################################################################

GWSOCKET_VERSION = 3ded70360ac66df11b667da2ea42d7c5abbe9dcd
GWSOCKET_SITE = $(call github,allinurl,gwsocket,$(GWSOCKET_VERSION))
GWSOCKET_AUTORECONF = YES
GWSOCKET_LICENSE = GPL-2.0
GWSOCKET_LICENSE_FILES = COPYING
GWSOCKET_CONF_OPTS= --with-openssl

$(eval $(autotools-package))
