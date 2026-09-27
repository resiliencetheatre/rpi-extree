################################################################################
#
# dokuwiki
#
################################################################################

DOKUWIKI_VERSION = 2026-07-14c
DOKUWIKI_SOURCE = dokuwiki-$(DOKUWIKI_VERSION).tgz
DOKUWIKI_SITE = https://download.dokuwiki.org/src/dokuwiki
DOKUWIKI_LICENSE = GPL-2.0
DOKUWIKI_LICENSE_FILES = COPYING
DOKUWIKI_DEPENDENCIES = apache php

define DOKUWIKI_INSTALL_TARGET_CMDS
	mkdir -p $(TARGET_DIR)/usr/share/dokuwiki
	cp -a $(@D)/. $(TARGET_DIR)/usr/share/dokuwiki/
	$(INSTALL) -D -m 0644 $(DOKUWIKI_PKGDIR)/apache.conf \
		$(TARGET_DIR)/etc/apache2/extra/dokuwiki.conf
endef

# Apache in the webserver overlay runs as www-data. Keep application code
# read-only, but allow configuration, pages and extension installation.
define DOKUWIKI_PERMISSIONS
	/usr/share/dokuwiki/conf d 0755 www-data www-data - - -
	/usr/share/dokuwiki/conf r -1 www-data www-data - - -
	/usr/share/dokuwiki/data d 0755 www-data www-data - - -
	/usr/share/dokuwiki/data r -1 www-data www-data - - -
	/usr/share/dokuwiki/lib/plugins d 0755 www-data www-data - - -
	/usr/share/dokuwiki/lib/plugins r -1 www-data www-data - - -
	/usr/share/dokuwiki/lib/tpl d 0755 www-data www-data - - -
	/usr/share/dokuwiki/lib/tpl r -1 www-data www-data - - -
endef

$(eval $(generic-package))
