#!/bin/sh
# BusyBox-compatible. Usage: sh blinkstick-state.sh /path/to/ptt-state
# Run as the same user as ptt_client (the state file is private).
state_file=${1:?Usage: sh blinkstick-state.sh /path/to/ptt-state}

command -v blinkstickctl >/dev/null 2>&1 || {
    echo 'blinkstickctl not found in PATH' >&2
    exit 1
}

trap 'blinkstickctl fade 0 0 0 200' EXIT
trap 'exit 0' INT TERM
previous=

while :; do
    red=0
    # Reopen each time: ptt_client replaces the file atomically.
    # Missing/unreadable files count as idle; never execute file contents.
    if grep -Eq '^(tx|rx)=1$' "$state_file" 2>/dev/null; then
        red=200
    fi
    if [ "$red" != "$previous" ]; then
        # Retry on the next poll if the device command fails.
        if blinkstickctl fade "$red" 0 0 200; then
            previous=$red
        fi
    fi
    sleep 0.1 || exit 1
done
