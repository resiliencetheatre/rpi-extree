################################################################################
#
# python-adafruit-circuitpython-rgb-display
#
# /
# 
################################################################################
PYTHON_ADAFRUIT_CIRCUITPYTHON_RGB_DISPLAY_VERSION = 3.14.6
PYTHON_ADAFRUIT_CIRCUITPYTHON_RGB_DISPLAY_SOURCE = adafruit_circuitpython_rgb_display-$(PYTHON_ADAFRUIT_CIRCUITPYTHON_RGB_DISPLAY_VERSION).tar.gz
PYTHON_ADAFRUIT_CIRCUITPYTHON_RGB_DISPLAY_SITE = https://files.pythonhosted.org/packages/f1/e6/21acb8f0a88bd2f31091a5278ee63bf37093548267277527e20ef1264b4e
PYTHON_ADAFRUIT_CIRCUITPYTHON_RGB_DISPLAY_LICENSE = MIT
PYTHON_ADAFRUIT_CIRCUITPYTHON_RGB_DISPLAY_LICENSE_FILES = LICENSE-PSF LICENSE
PYTHON_ADAFRUIT_CIRCUITPYTHON_RGB_DISPLAY_SETUP_TYPE = setuptools
# This is a runtime dependency, but we don't have the concept of
# runtime dependencies for host packages.

$(eval $(python-package))
