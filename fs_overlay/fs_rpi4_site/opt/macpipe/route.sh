#!/bin/sh
# route all traffic from macsec0 <-> end0
WIRED_ETH=end0
echo 1 > /proc/sys/net/ipv4/ip_forward
iptables -t nat -A POSTROUTING -o $WIRED_ETH -j MASQUERADE  
iptables -A FORWARD -i $WIRED_ETH -o macsec0@$WIRED_ETH -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i macsec0@$WIRED_ETH -o $WIRED_ETH -j ACCEPT
exit 0
