#!/bin/sh
if [ -d "/opt/data/lost+found" ]
then
    echo "/opt/data partition found! Exiting."
    exit
else
    echo "Creating encrypted partition"

    TARGET_DEV=/dev/mmcblk0
    parted --script $TARGET_DEV 'mkpart primary ext4 3180 -1'

    # LUKS format partitions
    # This requires user input
    cryptsetup luksFormat --type luks2 ${TARGET_DEV}p3

    # Enrol FIDO2
    echo "Enrolling FIDO2 token to partitions:"
    echo "${TARGET_DEV}p3"
    echo " "
    echo "Be ready to press FIDO2 token, when LED is flashing..."
    sleep 1
    echo " "
    systemd-cryptenroll --fido2-device=auto --fido2-with-client-pin=false --fido2-with-user-presence=false ${TARGET_DEV}p3

    echo "LUKS open"
    cryptsetup luksOpen ${TARGET_DEV}p3 encrypted_data

    echo "Creating filesystem"
    mkfs.ext4 /dev/mapper/encrypted_data

fi
exit 0

