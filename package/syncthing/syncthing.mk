################################################################################
# syncthing
################################################################################

SYNCTHING_VERSION       = v2.0.9
SYNCTHING_SITE          = $(call github,syncthing,syncthing,$(SYNCTHING_VERSION))
SYNCTHING_LICENSE       = MPLv2
SYNCTHING_LICENSE_FILES = LICENSE

# Ensure the proper host Go is available first.
SYNCTHING_DEPENDENCIES += host-go

# Target build via golang-package
SYNCTHING_GO_ENV        = GO111MODULE=on CGO_ENABLED=0 GOTOOLCHAIN=local
SYNCTHING_BUILD_TARGETS = ./cmd/syncthing

# Generate embedded assets (defines auto.Assets) using host Go before target build.
SYNCTHING_PRE_BUILD_HOOKS += SYNCTHING_GEN_ASSETS
define SYNCTHING_GEN_ASSETS
	cd $(@D) && { \
		export PATH="$(HOST_DIR)/bin:$(HOST_GO_ROOT)/bin:$(BR_PATH)"; \
		export GOROOT="$(HOST_GO_ROOT)"; \
		export GOPATH="$(HOST_GO_GOPATH)"; \
		export GO111MODULE=on GOTOOLCHAIN=local; \
		echo "using go: $$(which go)"; go version; \
		go run build.go assets; \
	}
endef

$(eval $(golang-package))
