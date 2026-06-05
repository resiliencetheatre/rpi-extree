################################################################################
# syncthing
################################################################################

SYNCTHING_VERSION       = v2.1.1
SYNCTHING_SITE          = $(call github,syncthing,syncthing,$(SYNCTHING_VERSION))
SYNCTHING_LICENSE       = MPLv2
SYNCTHING_LICENSE_FILES = LICENSE

SYNCTHING_GOMOD = github.com/syncthing/syncthing

SYNCTHING_DEPENDENCIES += host-go sqlite

SYNCTHING_DL_ENV += \
        GOPROXY=https://proxy.golang.org,direct \
        GOSUMDB=sum.golang.org \
        GOTOOLCHAIN=local

SYNCTHING_GO_ENV += \
        GO111MODULE=on \
        CGO_ENABLED=1 \
        GOPROXY=https://proxy.golang.org,direct \
        GOSUMDB=sum.golang.org \
        GOTOOLCHAIN=local

SYNCTHING_BUILD_TARGETS = ./cmd/syncthing

SYNCTHING_PRE_BUILD_HOOKS += SYNCTHING_GEN_ASSETS
define SYNCTHING_GEN_ASSETS
        cd $(@D) && { \
                export PATH="$(HOST_DIR)/bin:$(HOST_GO_ROOT)/bin:$(BR_PATH)"; \
                export GOROOT="$(HOST_GO_ROOT)"; \
                export GOPATH="$(HOST_GO_GOPATH)"; \
                export GO111MODULE=on; \
                export GOTOOLCHAIN=local; \
                export GOPROXY=https://proxy.golang.org,direct; \
                export GOSUMDB=sum.golang.org; \
                echo "using go: $$(which go)"; go version; \
                go run build.go assets; \
        }
endef

$(eval $(golang-package))
