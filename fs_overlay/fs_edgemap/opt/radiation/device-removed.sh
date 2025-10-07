#!/bin/sh
logger -t radsensor "Removed $DEV (symlink /dev/radsensor will disappear automatically)"
systemctl stop radiation.service
