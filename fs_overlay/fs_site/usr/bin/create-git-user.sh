#!/bin/sh
if [ -z "${PUBKEY:-}" ]; then
    echo "Error: PUBKEY environment variable is not set." >&2
    exit 1
fi
adduser -D -h /opt/data/git -s /bin/sh git
mkdir -p /opt/data/git/.ssh
chown -R git:git /opt/data/git
chmod 755 /opt/data/git
chmod 700 /opt/data/git/.ssh
echo $PUBKEY > /opt/data/git/.ssh/authorized_keys
chmod 600 /opt/data/git/.ssh/authorized_keys
chmod go-w /opt /opt/data
chown -R git:git /opt/data/git
passwd -u git
cp -r /root/git-shell-commands /opt/data/git/
chown -R git:git /opt/data/git
# change git user shell
/usr/bin/change-git-shell.sh
