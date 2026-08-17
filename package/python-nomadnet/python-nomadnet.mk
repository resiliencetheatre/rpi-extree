################################################################################
#
# python-nomadnet
#
################################################################################

PYTHON_NOMADNET_VERSION = 1.2.0
PYTHON_NOMADNET_SITE = $(call github,markqvist,NomadNet,$(PYTHON_NOMADNET_VERSION))
PYTHON_NOMADNET_SETUP_TYPE = setuptools

PYTHON_NOMADNET_LICENSE = GPL-3.0
PYTHON_NOMADNET_LICENSE_FILES = LICENSE

PYTHON_NOMADNET_DEPENDENCIES = \
	python-rns \
	python-lxmf \
	python-urwid \
	python-qrcode

$(eval $(python-package))
