################################################################################
#
# forgejo
#
################################################################################

FORGEJO_VERSION = v16.0.2
FORGEJO_VERSION_SEMVER = $(patsubst v%,%,$(FORGEJO_VERSION))
FORGEJO_SITE = https://codeberg.org/forgejo/forgejo.git
FORGEJO_SITE_METHOD = git
FORGEJO_LICENSE = MIT
FORGEJO_LICENSE_FILES = LICENSE

# Required by Buildroot's Go package infrastructure.
# This makes Buildroot vendor Go modules during the download/post-process step,
# before the actual offline build where GOPROXY=off is used.
FORGEJO_GOMOD = codeberg.org/forgejo/forgejo

# host-go is added automatically by golang-package, but keeping it explicit is
# harmless. host-nodejs is needed for frontend asset generation.
#
# Runtime dependencies:
# - git: required for repository operations
# - openssh: useful/expected for SSH git access
FORGEJO_DEPENDENCIES = host-go host-nodejs git openssh

FORGEJO_TAGS = bindata timetzdata sqlite sqlite_unlock_notify

FORGEJO_MAKE_ENV = \
	$(TARGET_MAKE_ENV) \
	$(HOST_GO_TARGET_ENV) \
	GOTOOLCHAIN=local \
	CGO_ENABLED=1 \
	TAGS="$(FORGEJO_TAGS)" \
	SHARP_IGNORE_GLOBAL_LIBVIPS=true \
	ENABLE_SOURCEMAP=false

define FORGEJO_USERS
	forgejo -1 forgejo -1 * /var/lib/forgejo /bin/false - Forgejo user
endef

define FORGEJO_WRITE_VERSION
	echo "$(FORGEJO_VERSION_SEMVER)" > $(@D)/VERSION
endef

FORGEJO_POST_PATCH_HOOKS += FORGEJO_WRITE_VERSION

define FORGEJO_BUILD_CMDS
	cd $(@D) && \
	$(FORGEJO_MAKE_ENV) \
	GOFLAGS="-mod=vendor -buildvcs=false" \
	$(MAKE1) build \
		GOFLAGS="-mod=vendor -buildvcs=false"
endef

define FORGEJO_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/gitea $(TARGET_DIR)/usr/bin/forgejo

	$(INSTALL) -d -m 0755 $(TARGET_DIR)/etc/forgejo
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/var/lib/forgejo
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/var/lib/forgejo/custom
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/var/lib/forgejo/data
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/var/lib/forgejo/log
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/var/lib/forgejo/repositories
endef

$(eval $(golang-package))
