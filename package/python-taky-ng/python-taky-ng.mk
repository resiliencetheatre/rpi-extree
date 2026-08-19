################################################################################
#
# python-taky-ng
#
################################################################################

PYTHON_TAKY_NG_VERSION = 0.0.3
PYTHON_TAKY_NG_SOURCE = taky_ng-$(PYTHON_TAKY_NG_VERSION).tar.gz
PYTHON_TAKY_NG_SITE = https://files.pythonhosted.org/packages/23/be/180adc0983439f50adeb5248b2b5f5604ed120f5fe717aaa3d402645183f
PYTHON_TAKY_NG_SETUP_TYPE = setuptools

PYTHON_TAKY_NG_LICENSE = MIT
PYTHON_TAKY_NG_LICENSE_FILES = LICENSE

PYTHON_TAKY_NG_DEPENDENCIES = \
	python-lxml \
	python-cryptography \
	python-dateutil \
	python-flask \
	python-gunicorn \
	python-redis

$(eval $(python-package))
