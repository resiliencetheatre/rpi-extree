#!/bin/sh
set -eu

OUTPUT_DIR=${1:-/etc/taky/ssl}
SERVER_IP=${2:-192.168.50.1}
SERVER_NAME=${3:-zero}
VALID_DAYS=${VALID_DAYS:-3650}

mkdir -p "$OUTPUT_DIR"
chmod 700 "$OUTPUT_DIR"

if [ -s "$OUTPUT_DIR/ca.crt" ] && \
   [ -s "$OUTPUT_DIR/server.crt" ] && \
   [ -s "$OUTPUT_DIR/server.key" ]; then
    echo "taky-ng server certificates already exist; nothing to do: $OUTPUT_DIR"
    exit 0
fi

for cert_file in ca.crt server.crt server.key; do
    if [ -e "$OUTPUT_DIR/$cert_file" ]; then
        echo "error: incomplete certificate set in $OUTPUT_DIR; refusing to overwrite existing files" >&2
        exit 1
    fi
done

if ! command -v openssl >/dev/null 2>&1; then
    echo "error: openssl is required on the host" >&2
    exit 1
fi

PARENT_DIR=$(dirname "$OUTPUT_DIR")
WORK_DIR=$(mktemp -d "$PARENT_DIR/.taky-pki.XXXXXX")
EXT_FILE="$WORK_DIR/server-ext.cnf"

cleanup() {
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT HUP INT TERM

openssl genpkey \
    -algorithm RSA \
    -pkeyopt rsa_keygen_bits:3072 \
    -out "$WORK_DIR/ca.key"

openssl req \
    -x509 \
    -new \
    -sha256 \
    -key "$WORK_DIR/ca.key" \
    -days "$VALID_DAYS" \
    -subj "/CN=taky-ng local CA" \
    -out "$WORK_DIR/ca.crt"

openssl genpkey \
    -algorithm RSA \
    -pkeyopt rsa_keygen_bits:2048 \
    -out "$WORK_DIR/server.key"

openssl req \
    -new \
    -sha256 \
    -key "$WORK_DIR/server.key" \
    -subj "/CN=$SERVER_NAME" \
    -out "$WORK_DIR/server.csr"

{
    echo "basicConstraints=critical,CA:FALSE"
    echo "keyUsage=critical,digitalSignature,keyEncipherment"
    echo "extendedKeyUsage=serverAuth"
    echo "subjectAltName=DNS:$SERVER_NAME,IP:$SERVER_IP"
    echo "subjectKeyIdentifier=hash"
    echo "authorityKeyIdentifier=keyid,issuer"
} >"$EXT_FILE"

openssl x509 \
    -req \
    -sha256 \
    -in "$WORK_DIR/server.csr" \
    -CA "$WORK_DIR/ca.crt" \
    -CAkey "$WORK_DIR/ca.key" \
    -CAcreateserial \
    -days "$VALID_DAYS" \
    -extfile "$EXT_FILE" \
    -out "$WORK_DIR/server.crt"

openssl verify -CAfile "$WORK_DIR/ca.crt" "$WORK_DIR/server.crt"

install -m 644 "$WORK_DIR/ca.crt" "$OUTPUT_DIR/ca.crt"
install -m 644 "$WORK_DIR/server.crt" "$OUTPUT_DIR/server.crt"
install -m 600 "$WORK_DIR/server.key" "$OUTPUT_DIR/server.key"

echo
echo "Created taky-ng server certificates in $OUTPUT_DIR"
echo "The temporary CA private key was removed after signing the server certificate."
