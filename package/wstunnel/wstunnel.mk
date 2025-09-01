################################################################################
#
# wstunnel
#
################################################################################

WSTUNNEL_VERSION = v10.4.4
WSTUNNEL_SITE    = https://github.com/erebe/wstunnel/archive/refs/tags
WSTUNNEL_SOURCE  = $(WSTUNNEL_VERSION).tar.gz

WSTUNNEL_LICENSE       = BSD-3-Clause
WSTUNNEL_LICENSE_FILES = LICENSE

# Build in the CLI crate directory
WSTUNNEL_SUBDIR = wstunnel-cli

# Let cargo-package add --path ./; we only specify the bin name
WSTUNNEL_CARGO_INSTALL_OPTS = --bin wstunnel

$(eval $(cargo-package))
