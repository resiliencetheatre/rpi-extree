################################################################################
#
# inn2
#
################################################################################

INN2_VERSION = 2.7.4
INN2_SOURCE = inn-$(INN2_VERSION).tar.gz
INN2_SITE = https://github.com/InterNetNews/inn/releases/download/$(INN2_VERSION)

INN2_LICENSE = ISC, GPL-2.0-or-later, BSD-2-Clause, BSD-3-Clause, other
INN2_LICENSE_FILES = LICENSE doc/GPL

# INN requires Perl and yacc/bison while building even when embedded
# Perl support is disabled.
INN2_DEPENDENCIES = host-perl host-bison

INN2_CONF_OPTS = \
	--prefix=/usr/lib/news \
	--sysconfdir=/etc/news \
	--with-db-dir=/var/lib/news \
	--with-log-dir=/var/log/news \
	--with-run-dir=/run/news \
	--with-spool-dir=/var/spool/news \
	--with-tmp-dir=/var/spool/news/tmp \
	--with-news-user=news \
	--with-news-group=news \
	--with-news-master=news \
	--enable-reduced-depends \
	--without-bdb \
	--without-blocklist \
	--without-canlock \
	--without-krb5 \
	--without-perl \
	--without-python \
	--without-sasl

ifeq ($(BR2_PACKAGE_INN2_ZLIB),y)
INN2_DEPENDENCIES += zlib
INN2_CONF_OPTS += --with-zlib=$(STAGING_DIR)/usr
else
INN2_CONF_OPTS += --without-zlib
endif

ifeq ($(BR2_PACKAGE_INN2_OPENSSL),y)
INN2_DEPENDENCIES += openssl
INN2_CONF_OPTS += --with-openssl=$(STAGING_DIR)/usr
else
INN2_CONF_OPTS += --without-openssl
endif

ifeq ($(BR2_PACKAGE_INN2_SQLITE),y)
INN2_DEPENDENCIES += sqlite
INN2_CONF_OPTS += --with-sqlite3=$(STAGING_DIR)/usr
else
INN2_CONF_OPTS += --without-sqlite3
endif

# Configure needs a working build-host Perl.  Some generated installed
# scripts may inherit the build-host interpreter path, so normalize those
# shebangs after installation.
INN2_CONF_ENV = \
	PERL=$(HOST_DIR)/bin/perl \
	inn_cv_func_msync_args=3 \
	inn_cv_func_mmap=yes \
	inn_cv_func_mmap_need_msync=no \
	inn_cv_func_mmap_sees_writes=yes


define INN2_INSTALL_TARGET_CMDS
	$(TARGET_MAKE_ENV) $(MAKE) -C $(@D) \
		DESTDIR=$(TARGET_DIR) \
		CHOWNPROG=set \
		CHGRPPROG=set \
		install

	$(SED) '1s|^#!$(HOST_DIR)/bin/perl|#!/usr/bin/perl|' \
		$(TARGET_DIR)/usr/lib/news/bin/* 2>/dev/null || true

	mkdir -p \
		$(TARGET_DIR)/etc/news \
		$(TARGET_DIR)/var/lib/news \
		$(TARGET_DIR)/var/log/news \
		$(TARGET_DIR)/var/spool/news \
		$(TARGET_DIR)/var/spool/news/tmp \
		$(TARGET_DIR)/run/news
endef

# The normal INN install wants to chown files to news:news. Buildroot
# performs target filesystem ownership handling separately, so installation
# is told not to chown/chgrp while staging.
#
# A news user/group is created in the final target filesystem.
INN2_USERS = news -1 news -1 * /var/lib/news /bin/false - INN news server

$(eval $(autotools-package))
