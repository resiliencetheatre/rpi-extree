################################################################################
#
# uucp
#
################################################################################

UUCP_VERSION = 1.07
UUCP_SOURCE = uucp_$(UUCP_VERSION).orig.tar.gz
UUCP_SITE = https://deb.debian.org/debian/pool/main/u/uucp
UUCP_LICENSE = GPL-2.0+
UUCP_LICENSE_FILES = COPYING

UUCP_CONF_ENV = \
	CFLAGS="$(TARGET_CFLAGS) -Wno-error=implicit-int -Wno-error=implicit-function-declaration -Wno-error=incompatible-pointer-types"

UUCP_CONF_OPTS = \
	--with-user=uucp \
	--with-newconfigdir=/etc/uucp \
	--with-oldconfigdir=/etc/uucp \
	--disable-build-warnings

# Taylor UUCP 1.07 predates current GCC/glibc interfaces.  Do these small,
# deterministic substitutions after the normal patch phase instead of carrying
# one fragile multi-file unified diff.
define UUCP_FIX_MODERN_COMPILERS
	$(SED) 's/char ab\[23\]/char ab[128]/' $(@D)/unix/lock.c
	$(SED) 's/char ab\[12\]/char ab[128]/' $(@D)/unix/lock.c
	$(SED) 's/char abtime\[sizeof "1991-12-31 12:00:00"\]/char abtime[128]/' $(@D)/unix/lock.c
	$(SED) 's/char ab\[10\]/char ab[128]/' $(@D)/unix/lock.c
	$(SED) 's/const char \*\*pzprog;/char **pzprog;/' $(@D)/unix/pipe.c
	$(SED) 's/pzprog = (const char \*\*) qconn->qport->uuconf_u\.uuconf_spipe\.uuconf_pzcmd;/pzprog = qconn->qport->uuconf_u.uuconf_spipe.uuconf_pzcmd;/' $(@D)/unix/pipe.c
	$(SED) 's/q->ipid = ixsspawn (pzprog,/q->ipid = ixsspawn ((const char **) pzprog,/' $(@D)/unix/pipe.c
	$(SED) 's/size_t clen;/socklen_t clen;/' $(@D)/unix/portnm.c
	$(SED) 's/size_t clen;/socklen_t clen;/' $(@D)/unix/tcp.c
	$(SED) '/extern int strcmp (), strcasecmp ();/d' $(@D)/uuconf/cmdarg.c

	$(SED) '/extern off_t lseek ();/d' $(@D)/unix/filnam.c
	$(SED) '/^int statfs ();/d' $(@D)/unix/fsusg.c
	$(SED) '/^int statvfs ();/d' $(@D)/unix/fsusg.c
	$(SED) '/extern char \*getcwd ();/d' $(@D)/unix/init.c
	$(SED) '/extern long sysconf ();/d' $(@D)/unix/init.c
	$(SED) '/extern struct tm \*localtime ();/d' $(@D)/unix/loctim.c
	$(SED) '/extern struct tm \*localtime ();/d' $(@D)/unix/lock.c
	$(SED) '/extern char \*ctime ();/d' $(@D)/unix/mail.c
	$(SED) '/extern time_t time ();/d' $(@D)/unix/opensr.c
	$(SED) '/extern char \*ttyname ();/d' $(@D)/unix/portnm.c
	$(SED) '/extern time_t time ();/d' $(@D)/unix/proctm.c
	$(SED) '/extern long sysconf ();/d' $(@D)/unix/proctm.c
	$(SED) '/extern time_t time ();/d' $(@D)/unix/time.c
	$(SED) '/extern off_t lseek ();/d' $(@D)/unix/trunc.c
	$(SED) '/extern time_t time ();/d' $(@D)/time.c
	$(SED) '/extern struct tm \*localtime ();/d' $(@D)/time.c
endef
UUCP_POST_PATCH_HOOKS += UUCP_FIX_MODERN_COMPILERS

define UUCP_USERS
	uucp 170 uucp 170 * /var/spool/uucp - - UUCP daemon
endef

define UUCP_INSTALL_TARGET_CMDS
	$(TARGET_MAKE_ENV) $(MAKE) -C $(@D) install \
		prefix=$(TARGET_DIR)/usr \
		exec_prefix=$(TARGET_DIR)/usr \
		bindir=$(TARGET_DIR)/usr/bin \
		sbindir=$(TARGET_DIR)/usr/sbin \
		libexecdir=$(TARGET_DIR)/usr/lib/uucp \
		infodir=$(TARGET_DIR)/usr/share/info \
		mandir=$(TARGET_DIR)/usr/share/man \
		newconfigdir=$(TARGET_DIR)/etc/uucp \
		oldconfigdir=$(TARGET_DIR)/etc/uucp

	$(INSTALL) -d -m 0755 $(TARGET_DIR)/etc/uucp
	$(INSTALL) -m 0644 $(UUCP_PKGDIR)/config $(TARGET_DIR)/etc/uucp/config
	$(INSTALL) -m 0600 $(UUCP_PKGDIR)/call $(TARGET_DIR)/etc/uucp/call
	$(INSTALL) -m 0600 $(UUCP_PKGDIR)/passwd $(TARGET_DIR)/etc/uucp/passwd
	$(INSTALL) -m 0644 $(UUCP_PKGDIR)/port $(TARGET_DIR)/etc/uucp/port
	$(INSTALL) -m 0644 $(UUCP_PKGDIR)/sys $(TARGET_DIR)/etc/uucp/sys
endef

UUCP_PERMISSIONS = $(UUCP_PKGDIR)/uucp.permissions

$(eval $(autotools-package))
