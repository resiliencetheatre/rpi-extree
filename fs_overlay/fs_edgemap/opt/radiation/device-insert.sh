#!/bin/sh

# Log
logger -t radsensor "Attached on $DEV (symlink /dev/radsensor)"

# Measure as insert demo
/bin/python3 /opt/radiation/gmc.py
