#!/bin/sh

# Simple directory monitor loop.
# For every regular file found in WATCH_DIR, invoke HANDLER with the filename.
# The handler is responsible for deleting the file after successful processing.

WATCH_DIR="${1:-/tmp/c2out}"
HANDLER="${2:-/opt/c2ptt/handle-file.sh}"
SLEEP_SECS="${3:-2}"

if [ ! -d "$WATCH_DIR" ]; then
    echo "Error: watch directory does not exist: $WATCH_DIR" >&2
    exit 1
fi

if [ ! -x "$HANDLER" ]; then
    echo "Error: handler is not executable: $HANDLER" >&2
    exit 1
fi

echo "Monitoring directory: $WATCH_DIR"
echo "Using handler: $HANDLER"
echo "Loop delay: ${SLEEP_SECS}s"

while true; do
    found_any=0

    for path in "$WATCH_DIR"/*; do
        # Handle empty directory case
        [ -e "$path" ] || continue

        # Only process regular files
        [ -f "$path" ] || continue

        found_any=1
        "$HANDLER" "$path"
    done

    sleep "$SLEEP_SECS"
done
