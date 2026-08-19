################################################################################
#
# situation-map
#
################################################################################

SITUATION_MAP_VERSION = 6977da1beb607e097890862dc646edc8fcc46d42
SITUATION_MAP_SITE = https://github.com/resiliencetheatre/map.git
SITUATION_MAP_SITE_METHOD = git
SITUATION_MAP_LICENSE = GPL-3.0-only
SITUATION_MAP_LICENSE_FILES = LICENSE
SITUATION_MAP_DEPENDENCIES = python3

define SITUATION_MAP_INSTALL_TARGET_CMDS
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/opt/situation
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/opt/situation/maps

	$(INSTALL) -m 0755 $(@D)/python-front.py \
		$(TARGET_DIR)/opt/situation/python-front.py

	cp -a $(@D)/web $(TARGET_DIR)/opt/situation/
	cp -a $(@D)/maplibre-gl-js $(TARGET_DIR)/opt/situation/

	$(INSTALL) -m 0644 $(@D)/LICENSE \
		$(TARGET_DIR)/opt/situation/LICENSE
endef

ifeq ($(BR2_PACKAGE_SITUATION_MAP_TAK),y)
define SITUATION_MAP_INSTALL_TAK
	$(INSTALL) -m 0755 $(@D)/tak-bridge.py \
		$(TARGET_DIR)/opt/situation/tak-bridge.py
endef
SITUATION_MAP_POST_INSTALL_TARGET_HOOKS += SITUATION_MAP_INSTALL_TAK
endif

ifeq ($(BR2_PACKAGE_SITUATION_MAP_MESHTASTIC),y)
SITUATION_MAP_DEPENDENCIES += python-meshtastic
define SITUATION_MAP_INSTALL_MESHTASTIC
	$(INSTALL) -m 0755 $(@D)/meshtastic-plugin.py \
		$(TARGET_DIR)/opt/situation/meshtastic-plugin.py
endef
SITUATION_MAP_POST_INSTALL_TARGET_HOOKS += SITUATION_MAP_INSTALL_MESHTASTIC
endif

define SITUATION_MAP_INSTALL_INIT_SYSTEMD
	$(INSTALL) -D -m 0644 $(SITUATION_MAP_PKGDIR)/situation-map.service \
		$(TARGET_DIR)/usr/lib/systemd/system/situation-map.service

	mkdir -p $(TARGET_DIR)/etc/systemd/system/multi-user.target.wants
	ln -sf ../../../../usr/lib/systemd/system/situation-map.service \
		$(TARGET_DIR)/etc/systemd/system/multi-user.target.wants/situation-map.service

	if test "$(BR2_PACKAGE_SITUATION_MAP_TAK)" = "y"; then \
		$(INSTALL) -D -m 0644 $(SITUATION_MAP_PKGDIR)/situation-map-tak.service \
			$(TARGET_DIR)/usr/lib/systemd/system/situation-map-tak.service; \
	fi

	if test "$(BR2_PACKAGE_SITUATION_MAP_MESHTASTIC)" = "y"; then \
		$(INSTALL) -D -m 0644 $(SITUATION_MAP_PKGDIR)/situation-map-meshtastic.service \
			$(TARGET_DIR)/usr/lib/systemd/system/situation-map-meshtastic.service; \
	fi
endef

$(eval $(generic-package))
