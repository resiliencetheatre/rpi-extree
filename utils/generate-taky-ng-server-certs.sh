#!/bin/sh
set -eu

OUTPUT_DIR=${1:-./taky-pki}
SERVER_IP=${2:-192.168.50.1}
SERVER_NAME=${3:-zero}
VALID_DAYS=${VALID_DAYS:-3650}

if ! command -v openssl >/dev/null 2>&1; then
    echo "error: openssl is required on the host" >&2
    exit 1
fi

if [ -e "$OUTPUT_DIR" ]; then
    echo "error: output path already exists: $OUTPUT_DIR" >&2
    echo "Choose a new directory so existing private keys are not overwritten." >&2
    exit 1
fi

mkdir -m 700 "$OUTPUT_DIR"
EXT_FILE="$OUTPUT_DIR/server-ext.cnf"

cleanup() {
    rm -f "$EXT_FILE"
}
trap cleanup EXIT HUP INT TERM

openssl genpkey \
    -algorithm RSA \
    -pkeyopt rsa_keygen_bits:3072 \
    -out "$OUTPUT_DIR/ca.key"

openssl req \
    -x509 \
    -new \
    -sha256 \
    -key "$OUTPUT_DIR/ca.key" \
    -days "$VALID_DAYS" \
    -subj "/CN=taky-ng local CA" \
    -out "$OUTPUT_DIR/ca.crt"

openssl genpkey \
    -algorithm RSA \
    -pkeyopt rsa_keygen_bits:2048 \
    -out "$OUTPUT_DIR/server.key"

openssl req \
    -new \
    -sha256 \
    -key "$OUTPUT_DIR/server.key" \
    -subj "/CN=$SERVER_NAME" \
    -out "$OUTPUT_DIR/server.csr"

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
    -in "$OUTPUT_DIR/server.csr" \
    -CA "$OUTPUT_DIR/ca.crt" \
    -CAkey "$OUTPUT_DIR/ca.key" \
    -CAcreateserial \
    -days "$VALID_DAYS" \
    -extfile "$EXT_FILE" \
    -out "$OUTPUT_DIR/server.crt"

rm -f "$OUTPUT_DIR/server.csr" "$OUTPUT_DIR/ca.srl"
chmod 600 "$OUTPUT_DIR/ca.key" "$OUTPUT_DIR/server.key"
chmod 644 "$OUTPUT_DIR/ca.crt" "$OUTPUT_DIR/server.crt"

openssl verify -CAfile "$OUTPUT_DIR/ca.crt" "$OUTPUT_DIR/server.crt"

echo
echo "Created taky-ng server certificates in $OUTPUT_DIR"
echo "Copy only these files to the Raspberry Pi under /etc/taky/ssl/:"
echo "  ca.crt"
echo "  server.crt"
echo "  server.key"
echo "Keep ca.key on the host; it is the CA private key."
