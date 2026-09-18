#!/bin/sh

# BusyBox-compatible UxPlay recording-status watcher.
# Usage: uxplay-recording-status.sh /path/to/uxplay.log

LOG_FILE=${1:-}
STATUS_FILE=/tmp/status.txt

if [ -z "$LOG_FILE" ]; then
    echo "Usage: $0 LOG_FILE" >&2
    exit 2
fi

if [ ! -f "$LOG_FILE" ]; then
    echo "Log file not found: $LOG_FILE" >&2
    exit 1
fi

# Do not leave an old recording indication behind when starting.
: > "$STATUS_FILE"

# Read only lines appended after this watcher starts.
tail -n 0 -f "$LOG_FILE" | while IFS= read -r line; do
    case "$line" in
        *"Started recording to:"*)
            printf '%s\n' 'SCREEN REC' > "$STATUS_FILE"
            ;;
        *"Stopped recording"*)
            : > "$STATUS_FILE"
            ;;
    esac
done
