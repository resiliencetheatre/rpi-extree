#!/bin/sh
set -eu

if [ $# -ne 1 ]; then
    echo "Usage: $0 COMMON_NAME"
    echo "Example: $0 forgejo.vault.local"
    exit 1
fi

CN="$1"
CA_DIR="${CA_DIR:-$HOME/forgejo-ca}"
FORGEJO_CERT_DIR="${FORGEJO_CERT_DIR:-/opt/data/forgejo/certs}"
FORGEJO_USER="${FORGEJO_USER:-git}"
FORGEJO_GROUP="${FORGEJO_GROUP:-git}"

SRC_CERT="$CA_DIR/issued/$CN/$CN.fullchain.pem"
SRC_KEY="$CA_DIR/issued/$CN/private/$CN.key.pem"

[ -f "$SRC_CERT" ] || { echo "Missing cert: $SRC_CERT" >&2; exit 1; }
[ -f "$SRC_KEY" ] || { echo "Missing key: $SRC_KEY" >&2; exit 1; }

mkdir -p "$FORGEJO_CERT_DIR"
cp "$SRC_CERT" "$FORGEJO_CERT_DIR/forgejo.crt"
cp "$SRC_KEY" "$FORGEJO_CERT_DIR/forgejo.key"

chown -R "$FORGEJO_USER:$FORGEJO_GROUP" "$FORGEJO_CERT_DIR"
chmod 644 "$FORGEJO_CERT_DIR/forgejo.crt"
chmod 640 "$FORGEJO_CERT_DIR/forgejo.key"

echo "Installed Forgejo TLS files:"
echo "  $FORGEJO_CERT_DIR/forgejo.crt"
echo "  $FORGEJO_CERT_DIR/forgejo.key"
