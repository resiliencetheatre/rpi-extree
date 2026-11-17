#!/usr/bin/env bash
# Compatibility entry point; the shared release engine owns all behavior.
set -euo pipefail
board=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec "$board/release.sh" --public "$@"
