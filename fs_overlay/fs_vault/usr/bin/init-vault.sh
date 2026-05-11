#!/bin/sh
#
# This script will initialize freshly flashed vault microsd for you.
#
# Functions
#
# * Sets hostname 
# * Sets services to initial state
# * Creates syncthing user
# * Creates third partition to microsd for data
# * Mounts third partition to /opt/data
# * Creates /opt/data/syncthing owned by syncthing:syncthing
#
# * DNS name is used as /etc/hostname
#
# Example run:
#
# ./init-vault.sh [HOSTNAME]
#
# NOTE: No more TLS in vault. It's mainly attribution help and
#       does not provide real security against adversaries.
#

set -eu

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

[ "$(id -u)" -eq 0 ] || fail "This script must be run as root"

if [ $# -lt 1 ] || [ -z "${1:-}" ]; then
    echo "Usage: init-vault.sh [DNS-NAME]"
    exit 1
fi

DNS_NAME=$1

echo "DNS: $DNS_NAME"

need_cmd sed
need_cmd rm
need_cmd mkdir
need_cmd chown
need_cmd id
need_cmd adduser
need_cmd parted
need_cmd awk
need_cmd mkfs.ext4
need_cmd mount
need_cmd grep
need_cmd sync
need_cmd sleep


#
# Set /etc/hostname
#
echo "$DNS_NAME" > /etc/hostname

#
# Configure services as you like
#
rm -f /etc/systemd/system/multi-user.target.wants/i2pd.service
rm -f /etc/systemd/system/multi-user.target.wants/smcroute.service
rm -f /etc/systemd/system/multi-user.target.wants/motion.service
rm -f /etc/systemd/system/multi-user.target.wants/gpsd.service

echo "Services configured!"
echo " "
echo "Adding syncthing user"

#
# Syncthing user
#
mkdir -p /opt/syncthing

if id syncthing >/dev/null 2>&1; then
    echo "User syncthing already exists"
else
    adduser -H -h /opt/syncthing/ -D syncthing syncthing
fi

chown -R syncthing:syncthing /opt/syncthing

# Git user
mkdir -p /home/git

if id git >/dev/null 2>&1; then
    echo "User git already exists"
else
    adduser -H -h /home/git/ -D git git
fi

echo "Set 'git' user password manually after this scrip is completed:"
echo " "
echo "passwd git"
echo " "
echo "This enables git user. Note that you need still set ssh key for git user"
echo " "


#
# Create and mount unencrypted third partition for data
#
dev=/dev/mmcblk0
part="${dev}p3"
fslabel="data"
datadir=/opt/data
syncthingdir="${datadir}/syncthing"

echo "Checking third partition on $dev"

[ -b "$dev" ] || fail "Block device not found: $dev"

if [ -b "$part" ]; then
    echo "It seems that your card already has third partition ($part)!"
    echo "-> Skipping partition create."
else
    echo "Creating third partition without encryption on MicroSD"

    end2=$(parted -m "$dev" unit s print | awk -F: '$1==2 { gsub("s","",$3); print $3 }')

    if [ -z "$end2" ]; then
        fail "Could not find partition 2 on $dev"
    fi

    start3=$(( ((end2 + 1) + 2047) / 2048 * 2048 ))

    echo "Partition 2 ends at sector ${end2}"
    echo "Creating partition 3 from ${start3}s to 100%"

    parted --script "$dev" mkpart primary ext4 "${start3}s" 100% || \
        fail "Failed to create partition 3"

    sync
    partprobe "$dev" 2>/dev/null || true
    sleep 2

    if [ ! -b "$part" ]; then
        fail "Partition device did not appear: $part"
    fi

    echo "Creating filesystem on $part"
    mkfs.ext4 -F -L "$fslabel" "$part" || \
        fail "Failed to create ext4 filesystem on $part"
fi

#
# Prepare mount point
#
systemctl daemon-reload

echo "Preparing $datadir"
mkdir -p "$datadir"

if mount | grep -q " on ${datadir} "; then
    echo "$datadir is already mounted"
else
    echo "Mounting $part to $datadir"
    mount "$part" "$datadir" || fail "Failed to mount $part to $datadir"
fi

if ! mount | grep -q " on ${datadir} "; then
    fail "$datadir is not mounted"
fi


#
# Syncthing data directory on mounted data partition
#
echo "Preparing Syncthing data directory"
mkdir -p "$syncthingdir"
chown -R syncthing:syncthing "$syncthingdir" || \
    fail "Failed to chown $syncthingdir"

echo "Data partition is ready at $datadir"
echo " "
echo "All set, reboot unit."
echo " "
