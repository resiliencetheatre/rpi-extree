################################################################################
#
# python-pygmc
# 
################################################################################

PYTHON_PYGMC_VERSION = 0.14.1
PYTHON_PYGMC_SOURCE = pygmc-$(PYTHON_PYGMC_VERSION).tar.gz
PYTHON_PYGMC_SITE = https://files.pythonhosted.org/packages/83/ca/1f72750aaaa96f9c36917b4ddd8a5279b55b88ddf29e61be5c11d0258eb9
PYTHON_PYGMC_LICENSE = MIT
PYTHON_PYGMC_LICENSE_FILES = LICENSE-PSF LICENSE
PYTHON_PYGMC_SETUP_TYPE = setuptools

$(eval $(python-package))
