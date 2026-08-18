################################################################################
#
# python-pypubsub
#
################################################################################

PYTHON_PYPUBSUB_VERSION = v4.0.3
PYTHON_PYPUBSUB_SITE = https://github.com/schollii/pypubsub.git
PYTHON_PYPUBSUB_SITE_METHOD = git
PYTHON_PYPUBSUB_SETUP_TYPE = setuptools
PYTHON_PYPUBSUB_LICENSE = BSD-2-Clause
PYTHON_PYPUBSUB_LICENSE_FILES = LICENSE_BSD_Simple.txt

$(eval $(python-package))
