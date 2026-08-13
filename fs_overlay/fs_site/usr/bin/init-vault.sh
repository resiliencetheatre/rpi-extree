#!/bin/sh
#
# Initialize freshly flashed vault MicroSD for PiVault + Forgejo.
#
# Model used by this script:
#
#   Unix user running Forgejo: git
#   Unix user receiving SSH:  git
#   Forgejo web users:        independent Forgejo accounts managed in the UI
#
# In this model, the system OpenSSH server accepts git@HOST connections.
# Forgejo manages /opt/data/forgejo/.ssh/authorized_keys with forced commands.
# Do not manually place normal, unrestricted keys into that file.
#
# Functions:
#
# * Sets hostname
# * Sets selected services to initial disabled state
# * Creates syncthing user
# * Creates third partition on /dev/mmcblk0 as /dev/mmcblk0p3
# * Mounts third partition to /opt/data and persists it in /etc/fstab
# * Creates /opt/data/syncthing owned by syncthing:syncthing
# * Creates git user with home /opt/data/forgejo and shell /bin/sh
# * Creates /opt/data/forgejo owned by git:git
# * Creates /etc/forgejo/app.ini for system-sshd Forgejo SSH integration
# * Installs /etc/systemd/system/forgejo.service and enables it on boot
# * Hardens sshd for the git user without using ForceCommand
#
# Example run:
#
#   ./init-vault-forgejo-git-runtime.sh vault
#
# If a second argument is supplied for compatibility with old scripts, it is
# deliberately ignored. Forgejo SSH keys must be added in Forgejo web UI so
# Forgejo can generate forced-command authorized_keys entries.
#
# NOTE: No more TLS in vault. It's mainly attribution help and
#       does not provide real security against adversaries.
#

set -eu

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

warn() {
    echo "WARNING: $*" >&2
}

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

append_unique_line() {
    file=$1
    line=$2

    mkdir -p "$(dirname "$file")"
    touch "$file"

    if ! grep -Fxq "$line" "$file" 2>/dev/null; then
        printf '%s\n' "$line" >> "$file"
    fi
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

append_sshd_git_match() {
    sshd_config=/etc/ssh/sshd_config
    marker="PiVault Forgejo git user block"

    if [ ! -f "$sshd_config" ]; then
        warn "$sshd_config not found; skipping sshd git-user hardening block"
        return 0
    fi

    if grep -q "$marker" "$sshd_config" 2>/dev/null; then
        echo "sshd git-user hardening block already present"
        return 0
    fi

    cat >> "$sshd_config" <<'EOFSSHD'

# PiVault Forgejo git user block
# Forgejo writes forced-command entries to the git user's authorized_keys.
# Do not add ForceCommand here, because Forgejo supplies the forced command.
Match User git
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    PermitTTY no
    AllowTcpForwarding no
    X11Forwarding no
    PermitTunnel no
EOFSSHD
}

[ "$(id -u)" -eq 0 ] || fail "This script must be run as root"

if [ $# -lt 1 ] || [ -z "${1:-}" ]; then
    echo "Usage: $0 [DNS-NAME]"
    echo " "
    echo "Example:"
    echo "  $0 vault"
    echo " "
    echo "Add SSH keys later from the Forgejo web UI."
    exit 1
fi

DNS_NAME=$1

if [ $# -ge 2 ]; then
    warn "Second argument ignored. Add SSH keys in Forgejo web UI, not manually to authorized_keys."
fi

echo "DNS: $DNS_NAME"

need_cmd sed
need_cmd rm
need_cmd mkdir
need_cmd chown
need_cmd chmod
need_cmd id
need_cmd adduser
need_cmd addgroup
need_cmd parted
need_cmd awk
need_cmd mkfs.ext4
need_cmd mount
need_cmd grep
need_cmd sync
need_cmd sleep
need_cmd systemctl
need_cmd passwd
need_cmd touch
need_cmd cat
need_cmd dirname
need_cmd cp

# Prefer /sbin/nologin if present for informational checks, but git must use
# /bin/sh because OpenSSH must be able to execute Forgejo's forced command.
[ -x /bin/sh ] || fail "/bin/sh not found"

# Core persistent paths.
dev=/dev/mmcblk0
part="${dev}p3"
fslabel="data"
datadir=/opt/data
syncthingdir="${datadir}/syncthing"
forgejodir="${datadir}/forgejo"
forgejoconfigdir=/etc/forgejo
forgejoappini="${forgejoconfigdir}/app.ini"

forgejo_custom="${forgejodir}/custom"
forgejo_data="${forgejodir}/data"
forgejo_log="${forgejodir}/log"
forgejo_repos="${forgejodir}/repositories"
forgejo_ssh="${forgejodir}/.ssh"

#
# Set /etc/hostname
#
echo "$DNS_NAME" > /etc/hostname

#
# Configure services as you like
#
rm -f /etc/systemd/system/multi-user.target.wants/i2pd.service
rm -f /etc/systemd/system/multi-user.target.wants/smcroute.service
rm -f /etc/systemd/system/multi-user.target.wants/motion.service
rm -f /etc/systemd/system/multi-user.target.wants/gpsd.service
rm -f /etc/systemd/system/multi-user.target.wants/cryptpad.service
echo "Services configured!"
echo " "

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

#
# Git user is both Forgejo runtime user and OpenSSH Git transport user.
#
echo "Preparing git user for Forgejo runtime and SSH transport"
mkdir -p "$forgejodir"
ensure_user git "$forgejodir" /bin/sh git

# Enable the account interactively for sshd account checks. Password login for
# git is disabled later via sshd Match User git.
echo "Set password for git user now. Password SSH login for git will be disabled in sshd_config."
passwd git || fail "Failed to set password for git user"

mkdir -p \
    "$forgejo_custom" \
    "$forgejo_data" \
    "$forgejo_log" \
    "$forgejo_repos" \
    "$forgejo_ssh"

touch "$forgejo_ssh/authorized_keys"
chmod 755 "$forgejodir"
chmod 700 "$forgejo_ssh"
chmod 600 "$forgejo_ssh/authorized_keys"
chown -R git:git "$forgejodir"

# Do not install a raw public key here. Forgejo must write forced-command
# entries after keys are added from the web UI.

#
# Forgejo config and systemd service.
#
mkdir -p "$forgejoconfigdir"

if [ -f "$forgejoappini" ]; then
    cp "$forgejoappini" "${forgejoappini}.bak"
fi

cat > "$forgejoappini" <<EOFAPP
APP_NAME = ${DNS_NAME} Forgejo
RUN_USER = git
WORK_PATH = ${forgejodir}

[server]
APP_DATA_PATH = ${forgejo_data}
DOMAIN = ${DNS_NAME}
HTTP_ADDR = 0.0.0.0
HTTP_PORT = 3000
ROOT_URL = http://${DNS_NAME}:3000/

; System OpenSSH handles SSH on port 22.
; Forgejo manages ${forgejo_ssh}/authorized_keys with forced commands.
DISABLE_SSH = false
START_SSH_SERVER = false
SSH_DOMAIN = ${DNS_NAME}
SSH_PORT = 22
SSH_LISTEN_PORT = 22
SSH_USER = git
SSH_ROOT_PATH = ${forgejo_ssh}
SSH_CREATE_AUTHORIZED_KEYS_FILE = true
SSH_AUTHORIZED_KEYS_BACKUP = false

[database]
DB_TYPE = sqlite3
PATH = ${forgejo_data}/forgejo.db
SQLITE_TIMEOUT = 500

[repository]
ROOT = ${forgejo_repos}

[log]
MODE = console
LEVEL = Info
ROOT_PATH = ${forgejo_log}

[security]
INSTALL_LOCK = false
EOFAPP

chown -R git:git "$forgejoconfigdir"
chmod 750 "$forgejoconfigdir"
chmod 640 "$forgejoappini"

cat > /etc/systemd/system/forgejo.service <<EOFSERVICE
[Unit]
Description=Forgejo
After=network-online.target opt-data.mount
Wants=network-online.target
RequiresMountsFor=${forgejodir}

[Service]
Type=simple
User=git
Group=git
WorkingDirectory=${forgejodir}
Environment=USER=git
Environment=HOME=${forgejodir}
Environment=GITEA_WORK_DIR=${forgejodir}
ExecStart=/usr/bin/forgejo web --config ${forgejoappini}
Restart=always
RestartSec=2s

[Install]
WantedBy=multi-user.target
EOFSERVICE

chmod 644 /etc/systemd/system/forgejo.service

append_sshd_git_match

systemctl daemon-reload
systemctl enable forgejo.service

# Try to reload sshd if it is already running. Ignore failures during image bring-up.
systemctl reload sshd.service 2>/dev/null || systemctl reload ssh.service 2>/dev/null || true

echo "Forgejo configured:"
echo "  Config: ${forgejoappini}"
echo "  Data:   ${forgejodir}"
echo "  HTTP:   http://${DNS_NAME}:3000/"
echo " "
echo "Forgejo SSH model:"
echo "  Unix runtime user: git"
echo "  Unix SSH user:     git"
echo "  Web users:         independent Forgejo accounts created in the web UI"
echo " "
echo "Add user SSH keys in Forgejo web UI, not manually in authorized_keys."
echo "Forgejo will manage:"
echo "  ${forgejo_ssh}/authorized_keys"
echo " "
echo "Typical clone URL after adding a key in Forgejo:"
echo "  git clone git@${DNS_NAME}:USER/REPO.git"
echo " "
echo "Start/test:"
echo "  systemctl start forgejo"
echo "  journalctl -u forgejo -f"
echo " "
echo "Data partition is ready at $datadir"
echo "All set, reboot unit."
echo " "
