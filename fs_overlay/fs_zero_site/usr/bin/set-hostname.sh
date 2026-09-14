#!/bin/sh

# Usage: set-hostname.sh site-d

NEW_HOSTNAME="$1"

if [ -z "$NEW_HOSTNAME" ]; then
    echo "Usage: $0 <hostname>" >&2
    exit 1
fi

# Allow a simple Linux/DNS hostname.
case "$NEW_HOSTNAME" in
    *[!A-Za-z0-9-]* | -* | *-)
        echo "Invalid hostname: $NEW_HOSTNAME" >&2
        exit 1
        ;;
esac

OLD_HOSTNAME="$(cat /etc/hostname 2>/dev/null)"
NEW_DOMAIN="${NEW_HOSTNAME}.lan"

# Set persistent and current runtime hostname.
printf '%s\n' "$NEW_HOSTNAME" > /etc/hostname
hostname "$NEW_HOSTNAME"

# Replace the old hostname in /etc/hosts.
if [ -n "$OLD_HOSTNAME" ] && [ -f /etc/hosts ]; then
    sed -i "s/${OLD_HOSTNAME}/${NEW_HOSTNAME}/g" /etc/hosts
fi

# Update the local dnsmasq domain.
sed -i \
    -e "s|^domain=.*|domain=${NEW_DOMAIN}|" \
    -e "s|^local=/[^/]*/|local=/${NEW_DOMAIN}/|" \
    -e "s|^address=/[^/]*/192\.168\.50\.1|address=/${NEW_DOMAIN}/192.168.50.1|" \
    /etc/dnsmasq.conf

echo "Hostname set to: $NEW_HOSTNAME"
echo "Local domain set to: $NEW_DOMAIN"
