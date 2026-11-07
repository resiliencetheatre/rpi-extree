#!/bin/sh
set -eu
board_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
# Refresh firmware and compile the Seeed overlay using the existing board hook.
"$board_dir/../reterminal/post-image.sh" "$@"
exec python3 "$board_dir/factory.py"
