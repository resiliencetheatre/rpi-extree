#!/bin/sh
#
# enable-rpi-ssh-forward.sh
#
# Publish VPS TCP/2222 as SSH to RPi over WireGuard:
#   VPS_PUBLIC_IP:2222  ->  10.0.0.12:22
#
# This script is intentionally idempotent:
# running it multiple times will not create duplicate rules.
#

set -eu

WIREGUARD_IP="${WIREGUARD_IP:-10.0.0.12}"
SERVICE_PORT="${SERVICE_PORT:-2222}"
DESTINATION_PORT="${DESTINATION_PORT:-22}"

IPTABLES="${IPTABLES:-iptables}"

have_rule() {
    table="$1"
    shift
    "$IPTABLES" -t "$table" -C "$@" 2>/dev/null
}

add_rule_once() {
    table="$1"
    shift
    if ! have_rule "$table" "$@"; then
        "$IPTABLES" -t "$table" -A "$@"
    fi
}

insert_filter_rule_once() {
    shift_chain="$1"
    shift
    if ! "$IPTABLES" -C "$shift_chain" "$@" 2>/dev/null; then
        "$IPTABLES" -I "$shift_chain" 1 "$@"
    fi
}

# IPv4 forwarding must be enabled for DNATed traffic to traverse the VPS.
if [ "$(cat /proc/sys/net/ipv4/ip_forward 2>/dev/null || echo 0)" != "1" ]; then
    echo "Enabling runtime IPv4 forwarding: net.ipv4.ip_forward=1"
    sysctl -w net.ipv4.ip_forward=1 >/dev/null
fi

# DNAT: public VPS TCP/2222 -> RPi TCP/22.
add_rule_once nat PREROUTING \
    -p tcp --dport "$SERVICE_PORT" \
    -j DNAT --to-destination "$WIREGUARD_IP:$DESTINATION_PORT"

# SNAT/MASQUERADE: ensure the RPi replies back via the VPS.
add_rule_once nat POSTROUTING \
    -p tcp -d "$WIREGUARD_IP" --dport "$DESTINATION_PORT" \
    -j MASQUERADE

# Permit the routed connection to the RPi.
# Insert at the top so it works even if later FORWARD-chain policy/rules are restrictive.
insert_filter_rule_once FORWARD \
    -p tcp -d "$WIREGUARD_IP" --dport "$DESTINATION_PORT" \
    -m conntrack --ctstate NEW,ESTABLISHED,RELATED \
    -j ACCEPT

# Permit return packets from the RPi.
insert_filter_rule_once FORWARD \
    -p tcp -s "$WIREGUARD_IP" --sport "$DESTINATION_PORT" \
    -m conntrack --ctstate ESTABLISHED,RELATED \
    -j ACCEPT

# Defense-in-depth:
# Do not let TCP/2222 terminate on the VPS itself.
# DNATed traffic has already been rewritten before INPUT, so this does not block forwarding.
insert_filter_rule_once INPUT \
    -p tcp --dport "$SERVICE_PORT" \
    -j DROP

echo "Enabled forwarding:"
echo "  VPS TCP/$SERVICE_PORT -> $WIREGUARD_IP TCP/$DESTINATION_PORT"
echo
echo "Note: do NOT use 'ufw allow $SERVICE_PORT' for this forwarding path."
