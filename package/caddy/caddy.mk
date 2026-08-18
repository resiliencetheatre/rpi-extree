################################################################################
#
# caddy
#
################################################################################

CADDY_VERSION = 2.11.4
CADDY_SITE = $(call github,caddyserver,caddy,v$(CADDY_VERSION))
CADDY_LICENSE = Apache-2.0
CADDY_LICENSE_FILES = LICENSE

CADDY_GOMOD = github.com/caddyserver/caddy/v2

CADDY_BUILD_TARGETS = cmd/caddy
CADDY_LDFLAGS = -s -w

define CADDY_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/bin/caddy \
		$(TARGET_DIR)/usr/bin/caddy

	$(INSTALL) -D -m 0644 $(CADDY_PKGDIR)/Caddyfile \
		$(TARGET_DIR)/etc/caddy/Caddyfile
endef

define CADDY_INSTALL_INIT_SYSTEMD
	$(INSTALL) -D -m 0644 $(CADDY_PKGDIR)/caddy.service \
		$(TARGET_DIR)/usr/lib/systemd/system/caddy.service

	mkdir -p $(TARGET_DIR)/etc/systemd/system/multi-user.target.wants
	ln -sf ../../../../usr/lib/systemd/system/caddy.service \
		$(TARGET_DIR)/etc/systemd/system/multi-user.target.wants/caddy.service
endef

define CADDY_USERS
	caddy -1 caddy -1 * /var/lib/caddy /bin/false - Caddy
endef

$(eval $(golang-package))
