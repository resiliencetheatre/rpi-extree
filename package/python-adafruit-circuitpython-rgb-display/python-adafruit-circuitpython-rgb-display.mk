################################################################################
#
# python-adafruit-circuitpython-rgb-display
#
# /
# 
################################################################################
PYTHON_ADAFRUIT_CIRCUITPYTHON_RGB_DISPLAY_VERSION = 3.14.3
PYTHON_ADAFRUIT_CIRCUITPYTHON_RGB_DISPLAY_SOURCE = adafruit_circuitpython_rgb_display-$(PYTHON_ADAFRUIT_CIRCUITPYTHON_RGB_DISPLAYC_VERSION).tar.gz
PYTHON_ADAFRUIT_CIRCUITPYTHON_RGB_DISPLAY_SITE = https://files.pythonhosted.org/packages/5e/c7/0bfdbfb1ec7e5e2cf5a1f8cb02c16b95c1791e5ed627ca2dfc66eadb5bfa
PYTHON_ADAFRUIT_CIRCUITPYTHON_RGB_DISPLAY_LICENSE = MIT
PYTHON_ADAFRUIT_CIRCUITPYTHON_RGB_DISPLAY_LICENSE_FILES = LICENSE-PSF LICENSE
PYTHON_ADAFRUIT_CIRCUITPYTHON_RGB_DISPLAY_SETUP_TYPE = setuptools
# This is a runtime dependency, but we don't have the concept of
# runtime dependencies for host packages.

$(eval $(python-package))
