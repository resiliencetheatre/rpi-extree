################################################################################
#
# udpcast
#
################################################################################

UDPCAST_VERSION = main
UDPCAST_SITE = https://codeberg.org/resiliencetheatre/udpcast.git
UDPCAST_SITE_METHOD = git

UDPCAST_AUTORECONF = YES
UDPCAST_INSTALL_STAGING = NO

UDPCAST_LICENSE = GPL-2.0-or-later or BSD-2-Clause or MPL-1.1
UDPCAST_LICENSE_FILES = COPYING LICENSE LICENSE.txt

# UDPCAST_DEPENDENCIES = readline ncurses zlib

$(eval $(autotools-package))
