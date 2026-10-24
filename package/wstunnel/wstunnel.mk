################################################################################
#
# wstunnel
#
################################################################################

WSTUNNEL_VERSION = v11.1.0
WSTUNNEL_SITE    = https://github.com/erebe/wstunnel/archive/refs/tags
WSTUNNEL_SOURCE  = $(WSTUNNEL_VERSION).tar.gz

WSTUNNEL_LICENSE       = BSD-3-Clause
WSTUNNEL_LICENSE_FILES = LICENSE

# Build in the CLI crate directory
WSTUNNEL_SUBDIR = wstunnel-cli

# Let cargo-package add --path ./; we only specify the bin name
WSTUNNEL_CARGO_INSTALL_OPTS = --bin wstunnel

$(eval $(cargo-package))

# The v11.1.0 release forgot to bump its two workspace entries in Cargo.lock.
# Repair them at download time: normal package patches run after vendoring.
# dl-wrapper resolves post-process scripts relative to support/download.
WSTUNNEL_DOWNLOAD_POST_PROCESS = $(shell realpath --relative-to=$(TOPDIR)/support/download $(WSTUNNEL_PKGDIR)/cargo)
WSTUNNEL_DL_ENV += WSTUNNEL_DOWNLOAD_SUPPORT=$(TOPDIR)/support/download
