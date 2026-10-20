# Waveshare PocketTerm 3.5

These are development notes, work in progress.


Mask console 

```
systemctl mask --now getty@tty1.service
systemctl start lvgl-com.service
```

To restore console login later:

```
systemctl stop lvgl-com.service
systemctl unmask getty@tty1.service
systemctl start getty@tty1.service
```
