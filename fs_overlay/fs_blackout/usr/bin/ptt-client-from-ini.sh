#!/bin/sh
set -eu

INI="/opt/lvgl-com/lvgl.ini"
KEY="$(sed -n 's/^ptt_word_of_day=//p' "$INI" | tail -n1)"

[ -n "$KEY" ] || {
    echo "ptt_word_of_day missing from $INI" >&2
    exit 1
}

exec /bin/ptt_client 91.98.237.100 \
--altgr-ptt-delay-ms 2000 --txid link \
--encrypt --key "$KEY" \
--ptt-socket /tmp/udpptt.sock
