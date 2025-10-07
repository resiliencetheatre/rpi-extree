#!/bin/sh

# Log
logger -t radsensor "Attached on $DEV (symlink /dev/radsensor)"

systemctl start radiation.service
