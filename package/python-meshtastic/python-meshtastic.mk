################################################################################
#
# python-meshtastic
#
################################################################################

PYTHON_MESHTASTIC_VERSION = 2.7.8
PYTHON_MESHTASTIC_SITE = https://github.com/meshtastic/python.git
PYTHON_MESHTASTIC_SITE_METHOD = git

PYTHON_MESHTASTIC_LICENSE = GNU General Public License v3 (GPLv3)
PYTHON_MESHTASTIC_LICENSE_FILES = LICENSE-PSF LICENSE

PYTHON_MESHTASTIC_SETUP_TYPE = poetry

$(eval $(python-package))
