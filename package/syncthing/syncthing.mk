################################################################################
# syncthing
################################################################################

SYNCTHING_VERSION = v2.0.1
SYNCTHING_SITE = $(call github,syncthing,syncthing,$(SYNCTHING_VERSION))
SYNCTHING_LICENSE = MPLv2
SYNCTHING_LICENSE_FILES = LICENSE

# Build settings for the target build performed by golang-package:
SYNCTHING_GO_ENV = GO111MODULE=on CGO_ENABLED=0
SYNCTHING_BUILD_TARGETS = ./cmd/syncthing
SYNCTHING_INSTALL_BINS = syncthing

# Generate embedded assets (defines auto.Assets) using the host Go before the target build.
SYNCTHING_PRE_BUILD_HOOKS += SYNCTHING_GEN_ASSETS
define SYNCTHING_GEN_ASSETS
	cd $(@D) && \
	PATH="$(BR_PATH)" GOROOT="$(HOST_GO_ROOT)" GOPATH="$(HOST_GO_GOPATH)" \
	GO111MODULE=on go run build.go assets
endef

$(eval $(golang-package))
