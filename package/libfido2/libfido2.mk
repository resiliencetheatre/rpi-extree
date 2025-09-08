################################################################################
# libfido2
################################################################################

LIBFIDO2_VERSION = 1.16.0
LIBFIDO2_SITE    = $(call github,Yubico,libfido2,$(LIBFIDO2_VERSION))
LIBFIDO2_SOURCE  = libfido2-$(LIBFIDO2_VERSION).tar.gz

LIBFIDO2_LICENSE       = BSD-2-Clause
LIBFIDO2_LICENSE_FILES = LICENSE

# Needed so systemd can find it via pkg-config
LIBFIDO2_INSTALL_STAGING = YES

# Base deps: libcbor + OpenSSL; hidapi and pcsc-lite are optional
LIBFIDO2_DEPENDENCIES = host-pkgconf libcbor openssl

# --- Optional USB via hidraw (recommended) ---
ifeq ($(BR2_PACKAGE_HIDAPI),y)
LIBFIDO2_DEPENDENCIES += hidapi
LIBFIDO2_CONF_OPTS    += -DUSE_HIDAPI=ON
else
LIBFIDO2_CONF_OPTS    += -DUSE_HIDAPI=OFF
endif

# --- Optional NFC via PC/SC (OFF by default) ---
ifeq ($(BR2_PACKAGE_PCSC_LITE),y)
LIBFIDO2_DEPENDENCIES += pcsc-lite
LIBFIDO2_CONF_OPTS    += -DUSE_PCSC=ON
else
LIBFIDO2_CONF_OPTS    += -DUSE_PCSC=OFF
endif

# Core build options (keep it lean for embedded)
LIBFIDO2_CONF_OPTS += \
	-DUSE_OPENSSL=ON \
	-DBUILD_EXAMPLES=OFF \
	-DBUILD_MANPAGES=OFF \
	-DBUILD_TESTS=OFF

# ---- Fix: avoid -D_FORTIFY_SOURCE=1 vs =2 redefinition ----
# Buildroot passes TARGET_CFLAGS to CMake as CMAKE_C_FLAGS. Filter out any
# existing -D_FORTIFY_SOURCE so libfido2's CMake can add its preferred level.
LIBFIDO2_CONF_OPTS += \
	-DCMAKE_C_FLAGS="$(filter-out -D_FORTIFY_SOURCE=%,$(TARGET_CFLAGS)) -U_FORTIFY_SOURCE" \
	-DCMAKE_CXX_FLAGS="$(filter-out -D_FORTIFY_SOURCE=%,$(TARGET_CXXFLAGS)) -U_FORTIFY_SOURCE"

$(eval $(cmake-package))
