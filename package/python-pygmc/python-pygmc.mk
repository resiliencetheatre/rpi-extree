################################################################################
#
# python-pygmc
# 
################################################################################

PYTHON_PYGMC_VERSION = 0.14.2
PYTHON_PYGMC_SOURCE = pygmc-$(PYTHON_PYGMC_VERSION).tar.gz
PYTHON_PYGMC_SITE = https://files.pythonhosted.org/packages/7f/02/a77eff51a9b67395897bbf237df089056d647c6327e08e68065dd106b646
PYTHON_PYGMC_LICENSE = MIT
PYTHON_PYGMC_LICENSE_FILES = LICENSE-PSF LICENSE
PYTHON_PYGMC_SETUP_TYPE = setuptools

$(eval $(python-package))
