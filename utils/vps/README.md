# Forward scripts

Utility scripts to configure forward from VPS to wireguard connected
node, like Raspberry Pi. 

For example: If you have RPi connected with 10.0.0.20 wireguard IP to VPS,
you can forward vps incoming 22 and 443 ports to RPi with:

```
WIREGUARD_IP=10.0.0.20 SERVICE_PORT=22 DESTINATION_PORT=22 ./enable-rpi-ssh-forward.sh
WIREGUARD_IP=10.0.0.20 SERVICE_PORT=443 DESTINATION_PORT=443 ./enable-rpi-ssh-forward.sh
```

These are currently used when you need to expose service to public IP (VPS).
