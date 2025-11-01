export TARGET=192.168.1.192
dd if=/dev/urandom of=/mnt/usb/in.key bs=64M count=16 iflag=fullblock
dd if=/dev/urandom of=/mnt/usb/out.key bs=64M count=16 iflag=fullblock
echo 1 > /mnt/usb/in.count
echo 1 > /mnt/usb/out.count
scp /mnt/usb/in.count $TARGET:/mnt/usb/
scp /mnt/usb/out.count $TARGET:/mnt/usb/
scp /mnt/usb/in.key $TARGET:/mnt/usb/out.key
scp /mnt/usb/out.key $TARGET:/mnt/usb/in.key
