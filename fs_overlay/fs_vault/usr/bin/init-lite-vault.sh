#!/bin/sh
#
# Initialize freshly flashed vault MicroSD without Forgejo.
# Sets hostname, creates and mounts the data partition at /opt/data,
# and prepares Syncthing and git users with persistent data directories.
#
# Usage: init-lite-vault.sh DNS-NAME
#

set -eu

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

ensure_group() {
    group=$1

    if grep -q "^${group}:" /etc/group 2>/dev/null; then
        return 0
    fi

    addgroup "$group" >/dev/null 2>&1 || fail "Failed to create group: $group"
}

set_passwd_fields() {
    user=$1
    home=$2
    shell=$3

    grep -q "^${user}:" /etc/passwd || fail "User not found in /etc/passwd: $user"

    awk -F: -v OFS=: -v u="$user" -v h="$home" -v s="$shell" '
        $1 == u { $6 = h; $7 = s }
        { print }
    ' /etc/passwd > /etc/passwd.tmp

    cat /etc/passwd.tmp > /etc/passwd
    rm -f /etc/passwd.tmp
}

ensure_user() {
    user=$1
    home=$2
    shell=$3
    group=$4

    ensure_group "$group"

    if id "$user" >/dev/null 2>&1; then
        echo "User $user already exists"
    else
        # BusyBox adduser variants differ between Buildroot configs.
        # Try the forms that work across common BusyBox builds.
        if adduser -D -H -h "$home" -s "$shell" -G "$group" "$user" >/dev/null 2>&1; then
            :
        elif adduser -D -H -h "$home" -G "$group" "$user" >/dev/null 2>&1; then
            :
        elif adduser -D -H -h "$home" "$user" >/dev/null 2>&1; then
            addgroup "$user" "$group" >/dev/null 2>&1 || true
        else
            fail "Failed to create user: $user"
        fi
    fi

    set_passwd_fields "$user" "$home" "$shell"
}

require_data_mounted() {
    mount | grep -q " on ${datadir} " || \
        fail "${datadir} is not mounted; refusing to write persistent data paths"
}

[ "$(id -u)" -eq 0 ] || fail "This script must be run as root"

if [ $# -ne 1 ] || [ -z "${1:-}" ]; then
    echo "Usage: $0 DNS-NAME"
    echo "Example: $0 vault"
    exit 1
fi

DNS_NAME=$1
echo "DNS: $DNS_NAME"

for cmd in rm mkdir chown chmod id adduser addgroup parted awk mkfs.ext4 mount grep sync sleep systemctl passwd touch cat cp; do
    need_cmd "$cmd"
done

[ -x /bin/sh ] || fail "/bin/sh not found"
git_shell=$(command -v git-shell) || fail "git-shell not found"
[ -d /root/git-shell-commands ] || fail "Git shell commands not found"

dev=/dev/mmcblk0
part="${dev}p3"
fslabel="data"
datadir=/opt/data
syncthingdir="${datadir}/syncthing"
gitdir="${datadir}/git"

# Set /etc/hostname.
printf '%s\n' "$DNS_NAME" > /etc/hostname

#
# Syncthing user. This does not write to /opt/data yet.
#
echo "Preparing syncthing user"
mkdir -p /opt/syncthing
ensure_user syncthing /opt/syncthing /bin/sh syncthing
chown -R syncthing:syncthing /opt/syncthing

#
# Create and mount unencrypted third partition for data.
# Nothing under /opt/data is created before the mount is verified.
#
echo "Checking third partition on $dev"

[ -b "$dev" ] || fail "Block device not found: $dev"

if [ -b "$part" ]; then
    echo "It seems that your card already has third partition ($part)!"
    echo "-> Skipping partition create."
else
    echo "Creating third partition without encryption on MicroSD"

    end2=$(parted -m "$dev" unit s print | awk -F: '$1==2 { gsub("s","",$3); print $3 }')

    if [ -z "$end2" ]; then
        fail "Could not find partition 2 on $dev"
    fi

    start3=$(( ((end2 + 1) + 2047) / 2048 * 2048 ))

    echo "Partition 2 ends at sector ${end2}"
    echo "Creating partition 3 from ${start3}s to 100%"

    parted --script "$dev" mkpart primary ext4 "${start3}s" 100% || \
        fail "Failed to create partition 3"

    sync
    partprobe "$dev" 2>/dev/null || true
    sleep 2

    if [ ! -b "$part" ]; then
        fail "Partition device did not appear: $part"
    fi

    echo "Creating filesystem on $part"
    mkfs.ext4 -F -L "$fslabel" "$part" || \
        fail "Failed to create ext4 filesystem on $part"
fi

#
# Prepare persisted mount point.
#
echo "Preparing persistent mount $datadir"
mkdir -p "$datadir"

touch /etc/fstab
if ! grep -qE "^[[:space:]]*LABEL=${fslabel}[[:space:]]+${datadir}[[:space:]]" /etc/fstab; then
    echo "LABEL=${fslabel} ${datadir} ext4 defaults,noatime 0 2" >> /etc/fstab
fi

systemctl daemon-reload

if mount | grep -q " on ${datadir} "; then
    echo "$datadir is already mounted"
else
    echo "Mounting $part to $datadir"
    mount "$datadir" 2>/dev/null || mount "$part" "$datadir" || \
        fail "Failed to mount $part to $datadir"
fi

require_data_mounted

#
# Syncthing data directory on mounted data partition.
#
echo "Preparing Syncthing data directory"
mkdir -p "$syncthingdir"
chown -R syncthing:syncthing "$syncthingdir" || \
    fail "Failed to chown $syncthingdir"

# Prepare the git user and SSH key directory on the mounted data partition.
echo "Preparing git user"
mkdir -p "$gitdir"
ensure_user git "$gitdir" "$git_shell" git

echo "Set password for git user now."
passwd git || fail "Failed to set password for git user"

mkdir -p "$gitdir/.ssh"
touch "$gitdir/.ssh/authorized_keys"
chmod 755 "$gitdir"
chmod 700 "$gitdir/.ssh"
chmod 600 "$gitdir/.ssh/authorized_keys"
mkdir -p "$gitdir/git-shell-commands"
cp /root/git-shell-commands/* "$gitdir/git-shell-commands/"
chmod 755 "$gitdir/git-shell-commands" "$gitdir/git-shell-commands/"*
chown -R git:git "$gitdir"

echo "Data partition is ready at $datadir"
echo "Syncthing data: $syncthingdir"
echo "Git home: $gitdir"
echo "Add Git SSH public keys to $gitdir/.ssh/authorized_keys"
echo "All set, reboot unit."
