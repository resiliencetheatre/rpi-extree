#!/bin/sh
# fix-git-shell.sh (BusyBox compatible, any position)
# Ensure git user's shell is /bin/git-shell

set -eu

PASSWD_FILE="/etc/passwd"
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP="/etc/passwd.bak.${TS}"
TMP="/tmp/passwd.$$"

cleanup() {
    rm -f "$TMP"
}
trap cleanup EXIT

if [ ! -f "$PASSWD_FILE" ]; then
    echo "Error: $PASSWD_FILE not found." >&2
    exit 1
fi

# extract current git line (if any)
git_line="$(grep '^git:' "$PASSWD_FILE" || true)"

if [ -z "$git_line" ]; then
    echo "No git user entry in $PASSWD_FILE" >&2
    exit 1
fi

# check current shell
case "$git_line" in
    *:/bin/git-shell)
        echo "Already using /bin/git-shell, nothing to do."
        exit 0
        ;;
    *:/bin/sh)
        new_git_line="$(echo "$git_line" | sed 's#/bin/sh$#/bin/git-shell#')"
        ;;
    *)
        echo "Git user has unexpected shell, refusing." >&2
        echo "Line: $git_line" >&2
        exit 1
        ;;
esac

cp "$PASSWD_FILE" "$BACKUP"
echo "Backup saved to $BACKUP"

# replace the git line in place
sed "s#^git:.*#${new_git_line}#" "$PASSWD_FILE" > "$TMP"

mv "$TMP" "$PASSWD_FILE"

echo "git user shell updated to /bin/git-shell"

