################################################################################
#
# rclone
#
################################################################################

RCLONE_VERSION = 1.75.0
RCLONE_SITE = $(call github,rclone,rclone,v$(RCLONE_VERSION))
RCLONE_LICENSE = MIT
RCLONE_LICENSE_FILES = COPYING

# Rclone publishes an official vendor archive because some dependencies
# cannot reliably be fetched by "go mod vendor".
RCLONE_VENDOR_SOURCE = rclone-v$(RCLONE_VERSION)-vendor.tar.gz
RCLONE_EXTRA_DOWNLOADS = \
	https://github.com/rclone/rclone/releases/download/v$(RCLONE_VERSION)/$(RCLONE_VENDOR_SOURCE)

RCLONE_DEPENDENCIES = host-go

define RCLONE_EXTRACT_VENDOR
	$(TAR) -xzf \
		$(RCLONE_DL_DIR)/$(RCLONE_VENDOR_SOURCE) \
		-C $(@D)
endef

RCLONE_POST_EXTRACT_HOOKS += RCLONE_EXTRACT_VENDOR

define RCLONE_BUILD_CMDS
	cd $(@D) && \
		$(HOST_GO_TARGET_ENV) \
		GOFLAGS="-mod=vendor" \
		$(HOST_DIR)/bin/go build \
			-v \
			-trimpath \
			-buildvcs=false \
			-ldflags "-X github.com/rclone/rclone/fs.Version=v$(RCLONE_VERSION)" \
			-o $(@D)/rclone \
			.
endef

define RCLONE_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 \
		$(@D)/rclone \
		$(TARGET_DIR)/usr/bin/rclone
endef

$(eval $(generic-package))
