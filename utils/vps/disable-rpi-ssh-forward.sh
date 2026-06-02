#!/bin/sh
#
# disable-rpi-ssh-forward.sh
#
# Remove the forwarding path:
#   VPS_PUBLIC_IP:2222  ->  10.0.0.12:22
#
# This script is safe to run even if the rules are already absent.
#

set -eu

WIREGUARD_IP="${WIREGUARD_IP:-10.0.0.12}"
SERVICE_PORT="${SERVICE_PORT:-2222}"
DESTINATION_PORT="${DESTINATION_PORT:-22}"

IPTABLES="${IPTABLES:-iptables}"

delete_nat_rule_all() {
    chain="$1"
    shift
    while "$IPTABLES" -t nat -C "$chain" "$@" 2>/dev/null; do
        "$IPTABLES" -t nat -D "$chain" "$@"
    done
}

delete_filter_rule_all() {
    chain="$1"
    shift
    while "$IPTABLES" -C "$chain" "$@" 2>/dev/null; do
        "$IPTABLES" -D "$chain" "$@"
    done
}

# Remove DNAT rule.
delete_nat_rule_all PREROUTING \
    -p tcp --dport "$SERVICE_PORT" \
    -j DNAT --to-destination "$WIREGUARD_IP:$DESTINATION_PORT"

# Remove MASQUERADE rule.
delete_nat_rule_all POSTROUTING \
    -p tcp -d "$WIREGUARD_IP" --dport "$DESTINATION_PORT" \
    -j MASQUERADE

# Remove forward-path allows.
delete_filter_rule_all FORWARD \
    -p tcp -d "$WIREGUARD_IP" --dport "$DESTINATION_PORT" \
    -m conntrack --ctstate NEW,ESTABLISHED,RELATED \
    -j ACCEPT

delete_filter_rule_all FORWARD \
    -p tcp -s "$WIREGUARD_IP" --sport "$DESTINATION_PORT" \
    -m conntrack --ctstate ESTABLISHED,RELATED \
    -j ACCEPT

# Remove the local INPUT DROP that the enable script added.
delete_filter_rule_all INPUT \
    -p tcp --dport "$SERVICE_PORT" \
    -j DROP

echo "Disabled forwarding:"
echo "  VPS TCP/$SERVICE_PORT -X-> $WIREGUARD_IP TCP/$DESTINATION_PORT"
echo
echo "Runtime net.ipv4.ip_forward was left unchanged intentionally."
