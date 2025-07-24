################################################################################
#
# python-irc
# https://files.pythonhosted.org/packages/0d/c0/5b875df761bfbf51482bab7ddb4b9f9968327bc08801f5ac9599ab451824/irc-20.5.0.tar.gz
#
################################################################################

PYTHON_IRC_VERSION = 20.5.0
PYTHON_IRC_SOURCE = irc-$(PYTHON_IRC_VERSION).tar.gz
PYTHON_IRC_SITE = https://files.pythonhosted.org/packages/0d/c0/5b875df761bfbf51482bab7ddb4b9f9968327bc08801f5ac9599ab451824
PYTHON_IRC_LICENSE = MIT
PYTHON_IRC_LICENSE_FILES = LICENSE-PSF LICENSE
PYTHON_IRC_SETUP_TYPE = setuptools
# This is a runtime dependency, but we don't have the concept of
# runtime dependencies for host packages.

$(eval $(python-package))
