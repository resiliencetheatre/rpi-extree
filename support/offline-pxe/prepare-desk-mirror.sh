#!/bin/bash
# Debian 13 workstation convenience entry point. Never formats or repartitions.
set -euo pipefail
case "${1:-}" in
    --check|--download) mode=$1 ;;
    *) echo "Usage: $0 --check | --download" >&2; exit 2 ;;
esac
[ "$#" -eq 1 ] || exit 2
support=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
base=/mnt/data/offline-pxe
findmnt -rn -M /mnt/data >/dev/null || {
    echo '/mnt/data must be mounted; refusing to put mirror data on the system filesystem.' >&2
    exit 1
}
mkdir -p "$base/staging" "$base/logs"
# Preserve settings (and therefore the generation name) across interrupted runs.
if [ ! -e "$base/settings.json" ]; then
    python3 - "$support/settings.json" "$base/settings.json" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
s=json.loads(Path(sys.argv[1]).read_text())
s['generation']='trixie-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
with open(sys.argv[2], 'x') as f:
    json.dump(s, f, indent=2)
    f.write('\n')
PY
fi
printf 'Settings: %s\n' "$base/settings.json"
df -h /mnt/data
if [ "$mode" = --check ]; then
    exec python3 "$support/host-preflight.py" "$base/settings.json" --online
fi
log="$base/logs/mirror-$(date -u +%Y%m%dT%H%M%SZ).log"
printf 'Log: %s\n' "$log"
python3 -u "$support/prepare-mirror.py" "$base/settings.json" "$base/staging" \
    --allow-download 2>&1 | tee "$log"
