#!/bin/sh
set -eu

git_shell=$(command -v git-shell) || { echo "Error: git-shell not found." >&2; exit 1; }
if [ -z "${PUBKEY:-}" ]; then
    echo "Error: PUBKEY environment variable is not set." >&2
    exit 1
fi
adduser -D -h /opt/data/git -s "$git_shell" git
mkdir -p /opt/data/git/.ssh
chown -R git:git /opt/data/git
chmod 755 /opt/data/git
chmod 700 /opt/data/git/.ssh
printf '%s\n' "$PUBKEY" > /opt/data/git/.ssh/authorized_keys
chmod 600 /opt/data/git/.ssh/authorized_keys
chmod go-w /opt /opt/data
chown -R git:git /opt/data/git
passwd -u git
cp -r /root/git-shell-commands /opt/data/git/
chmod 755 /opt/data/git/git-shell-commands /opt/data/git/git-shell-commands/*
chown -R git:git /opt/data/git
