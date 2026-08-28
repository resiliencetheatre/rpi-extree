################################################################################
#
# secure-audio
#
################################################################################

SECURE_AUDIO_VERSION = 00a7b60a9931d50301e458fc5724ff5b1a03b015
SECURE_AUDIO_SITE = ssh://git@git.resilience-theatre.com/resiliencetheatre/secure-audio.git
SECURE_AUDIO_SITE_METHOD = git
SECURE_AUDIO_LICENSE = Proprietary
SECURE_AUDIO_DEPENDENCIES = libcodec2 liquid-dsp

define SECURE_AUDIO_BUILD_CMDS
	$(TARGET_MAKE_ENV) $(TARGET_CONFIGURE_OPTS) $(MAKE) -C $(@D)
endef

define SECURE_AUDIO_INSTALL_TARGET_CMDS
	$(TARGET_MAKE_ENV) $(TARGET_CONFIGURE_OPTS) $(MAKE) -C $(@D) \
		DESTDIR=$(TARGET_DIR) PREFIX=/usr install
endef

$(eval $(generic-package))
