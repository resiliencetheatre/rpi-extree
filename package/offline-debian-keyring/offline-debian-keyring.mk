################################################################################
# Debian archive public keyring, authenticated against Debian trixie Packages
################################################################################
OFFLINE_DEBIAN_KEYRING_VERSION = 2025.1
OFFLINE_DEBIAN_KEYRING_SOURCE = debian-archive-keyring_$(OFFLINE_DEBIAN_KEYRING_VERSION)_all.deb
OFFLINE_DEBIAN_KEYRING_SITE = https://deb.debian.org/debian/pool/main/d/debian-archive-keyring
OFFLINE_DEBIAN_KEYRING_LICENSE = GPL-2.0+
OFFLINE_DEBIAN_KEYRING_LICENSE_FILES = usr/share/doc/debian-archive-keyring/copyright

define OFFLINE_DEBIAN_KEYRING_EXTRACT_CMDS
	cd $(@D) && $(HOSTAR) p $(OFFLINE_DEBIAN_KEYRING_DL_DIR)/$(OFFLINE_DEBIAN_KEYRING_SOURCE) data.tar.xz | $(TAR) -xJf -
endef

define OFFLINE_DEBIAN_KEYRING_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 644 $(@D)/usr/share/keyrings/debian-archive-keyring.pgp $(TARGET_DIR)/usr/share/keyrings/debian-archive-keyring.gpg
endef

$(eval $(generic-package))
