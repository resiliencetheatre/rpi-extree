################################################################################
#
# python-pypubsub
#
################################################################################

PYTHON_PYPUBSUB_VERSION = v4.0.7
PYTHON_PYPUBSUB_SITE = https://github.com/schollii/pypubsub.git
PYTHON_PYPUBSUB_SITE_METHOD = git
PYTHON_PYPUBSUB_SETUP_TYPE = setuptools
PYTHON_PYPUBSUB_ENV = \
	SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PYPUBSUB=$(patsubst v%,%,$(PYTHON_PYPUBSUB_VERSION))
PYTHON_PYPUBSUB_LICENSE = BSD-2-Clause
PYTHON_PYPUBSUB_LICENSE_FILES = LICENSE_BSD_Simple.txt

define PYTHON_PYPUBSUB_RELAX_SETUPTOOLS_VERSION
	$(SED) 's/setuptools>=68,<77/setuptools>=68/' $(@D)/pyproject.toml
	$(SED) '/where = \["src"\]/a exclude = ["contrib*"]' $(@D)/pyproject.toml
endef
PYTHON_PYPUBSUB_POST_PATCH_HOOKS += PYTHON_PYPUBSUB_RELAX_SETUPTOOLS_VERSION

define PYTHON_PYPUBSUB_REMOVE_LEGACY_CONTRIB
	$(RM) $(TARGET_DIR)/usr/lib/python$(PYTHON3_VERSION_MAJOR)/site-packages/contrib/netpubsub.py
	$(RM) $(TARGET_DIR)/usr/lib/python$(PYTHON3_VERSION_MAJOR)/site-packages/contrib/wx_monitor.py
endef
PYTHON_PYPUBSUB_POST_INSTALL_TARGET_HOOKS += PYTHON_PYPUBSUB_REMOVE_LEGACY_CONTRIB

$(eval $(python-package))
