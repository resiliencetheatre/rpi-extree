#!/bin/sh
#
# This script will initialize freshly flashed vault microsd for you.
#
# Functions
#
# * Sets hostname to various places (hostapd, dnsmasq, cryptpad)
# * Sets services to initial state
# * Creates cryptpad and thelounge users
# * Creates third partition to microsd for data
#
# * DNS name is equipped as wifi AP name to /etc/hostapd.conf
# * DNS name is equipped to /etc/dnsmasq.conf and /etc/dnsmasq.hosts
# * DNS name is used as /etc/hostname
#
# Example run:
#
# ./init-vault.sh [HOSTNAME]
#
#
# NOTE: No more TLS in vault. It's mainly attribution help and 
#		does not provide real security against adversaries.
#
#


DNS_NAME=$1

if [ -z "$DNS_NAME" ]
then
echo "Usage: init-vault.sh [DNS-NAME]"
exit
else
echo "DNS: $DNS_NAME"
fi


#
# Set wifi AP name
#
sed -i "s/^ssid=.*/ssid=${DNS_NAME}/" /etc/hostapd.conf

#
# Set /etc/dnsmasq.hosts and /etc/hostname
#
echo "10.1.1.1 $DNS_NAME" > /etc/dnsmasq.hosts
echo $DNS_NAME > /etc/hostname

#
# Set /etc/dnsmasq.conf
#
sed -i "s/^local=.*/local=\/${DNS_NAME}\//" /etc/dnsmasq.conf

#
# /opt/ircpipe/ircpipe.ini 
#

sed -i -E "s/^[[:space:]]*user[[:space:]]*=[[:space:]]*.*/user = ${DNS_NAME}/" /opt/ircpipe/ircpipe.ini
sed -i -E "s/^[[:space:]]*nick[[:space:]]*=[[:space:]]*.*/nick = ${DNS_NAME}/" /opt/ircpipe/ircpipe.ini
sed -i -E "s/^[[:space:]]*channel[[:space:]]*=[[:space:]]*.*/channel = #edgemap/" /opt/ircpipe/ircpipe.ini

echo "Configured: /opt/ircpipe/ircpipe.ini"

#
# cryptpad
#
cp /opt/cryptpad/config/config.example.js /opt/cryptpad/config/config.js
sed -i -E "s|^[[:space:]]*httpUnsafeOrigin:[[:space:]]*.*|httpUnsafeOrigin: 'http://${DNS_NAME}:3000',|" /opt/cryptpad/config/config.js
sed -i -E "s|^[[:space:]]*//[[:space:]]*httpAddress:[[:space:]]*'[^']*',?|httpAddress: '0.0.0.0',|" /opt/cryptpad/config/config.js

echo "Configured: /opt/cryptpad/config/config.js"
echo "NOTE: Cryptpad is work in progress"

#
# Configure services as you like
#
rm /etc/systemd/system/multi-user.target.wants/i2pd.service
rm /etc/systemd/system/multi-user.target.wants/smcroute.service
rm /etc/systemd/system/multi-user.target.wants/motion.service
rm /etc/systemd/system/multi-user.target.wants/gpsd.service


echo "Services configured!"
echo " "
echo "Adding cryptpad and thelounge users"

#
# Cryptpad user
#
adduser -H -h /opt/cryptpad/ -D cryptpad cryptpad
chown -R cryptpad:cryptpad /opt/cryptpad

#
# The lounge user
#
adduser -H -h /opt/thelounge/ -D thelounge thelounge
chown -R thelounge:thelounge /opt/thelounge

#
# Link 'thelounge' command
#
ln -s /usr/lib/thelounge/node_modules/thelounge/index.js /usr/bin/thelounge

#
# Create unencrypted third partition (taken from create-partition-noenc.sh)
# NOTE: Disabled

#if [ -b /dev/mmcblk0p3 ]; then
#    echo "It seems that your card has already third partition (/dev/mmcblk0p3)!"
#    echo "-> Skipping partition create."
#else
#    echo "Creating third partition (without encryption) to MicroSD"
#    TARGET_DEV=/dev/mmcblk0
#    parted --script $TARGET_DEV 'mkpart primary ext4 3500 -1'
#    # Creating filesystems
#    echo "Creating filesystem to $TARGET_DEVp3"
#    mkfs.ext4 -F -L data ${TARGET_DEV}p3
#fi

#
# Instruct cryptpad first run to finalize setup
#
echo " "
echo "== CRYPTPAD =="
echo " "
echo "To finalize cryptpad setup, you need manually do following:"
echo "(or you can ignore this, if you plan not to use cryptpad)"
echo " "
echo "systemctl stop cryptpad "
echo "su cryptpad"
echo "cd"
echo "node server.js"
echo " "
echo " -> Visit indicated setup URL and create admin user & password"
echo " -> After you are good, you can enable service:"
echo " "
echo "systemctl enable cryptpad.service"
echo " "
echo "You can do this now or after reboot"
echo " "
echo "== The Lounge (browser based IRC client) =="
echo " "
echo "Before using Thelounge, configure it via  /opt/thelounge/config.js"
echo " "
echo " IMPORTANT: You need to change port to 'port: 9001,' at line 32"
echo " "
echo " NOTE: You need to start thelounge once for config.js to be created"
echo "       run it with 'thelounge start' (as root) or start service:"
echo "       systemctl start thelounge"
echo " "
echo " After initial run, you can edit config.js and add users (as 'thelounge' user) "
echo " "
echo "Remember you need to be 'thelounge' user to use 'thelounge' command:"
echo " "
echo "su thelounge"
echo "cd"
echo "thelounge help"
echo " "
echo "All set, reboot unit."
echo " "
