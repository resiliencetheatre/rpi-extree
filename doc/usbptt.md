# usbptt

Delete LUKS2 partition signature (if there is one) and write image to MicroSD:

```sh
LUKS_PARTITION=/dev/[CHANGE]
DEVICE=/dev/[CHANGE]
sudo dd if=/dev/zero of=/dev/$LUKS_PARTITION bs=1M count=16 conv=fsync status=progress; \
sudo dd if=output/images/sdcard.img of=/dev/$DEVICE status=progress; \
sync
```

## First boot

```sh
# Delete template dpi.*
buildroot:~# rm .config/udpptt/dpi.*
# Create new secret and public key
buildroot:~# ptt_dpi_keygen \
--secret "$HOME/.config/udpptt/dpi.secret" \
--public "$HOME/.config/udpptt/dpi.public"

Created signing seed /root/.config/udpptt/dpi.secret and observer public key /root/.config/udpptt/dpi.public
buildroot:~# 
```

Configure `/etc/systemd/system/udpptt.service` with server IP, identity and encryption key.


