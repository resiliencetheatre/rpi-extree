#!/bin/sh
set -eu
board_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
"$board_dir/../rpi4-pocketterm/post-image.sh" "$@"
exec python3 "$board_dir/factory.py"
