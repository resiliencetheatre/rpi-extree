#!/bin/sh
set -eu
ACTION="${1:-event}"
TTY="${2:-unknown}"
MSG="uilog,Radiation sensor ${ACTION} (/dev/${TTY})"
FIFO=/tmp/statusin

# Try coreutils/busybox timeout if available; else use a watchdog-kill fallback.
send_msg() {
  if command -v timeout >/dev/null 2>&1; then
    timeout 0.3s sh -c 'printf "%s\n" "$1" > "$2"' sh "$MSG" "$FIFO" || true
  else
    # Start writer in background (may block); kill it after ~0.3s if still stuck
    ( printf '%s\n' "$MSG" > "$FIFO" ) &
    wp=$!
    ( sleep 0.3; kill -0 "$wp" 2>/dev/null && kill "$wp" 2>/dev/null ) &
    wait "$wp" 2>/dev/null || true
  fi
}

if [ -p "$FIFO" ]; then
  send_msg
fi

logger -t radsensor "$MSG"
exit 0

