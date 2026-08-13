#!/bin/sh
# keep it dead simple for udev
echo "inserted $(date -Is)" >> /root/insert.log
logger -t nitrokey "Nitrokey 3 inserted"
