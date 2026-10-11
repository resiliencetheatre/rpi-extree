#!/bin/sh
# Small, explicit online test only; does not populate a mirror or change networking.
set -eu
urls=${1:-/etc/offline-pxe/upstream-urls}
bundle=/etc/ssl/certs/ca-certificates.crt
[ -s "$bundle" ] || { echo "Missing CA bundle: $bundle" >&2; exit 1; }
curl --version
curl --version | grep '^Protocols:.* https' >/dev/null || {
    echo 'curl lacks HTTPS support' >&2; exit 1;
}
while IFS= read -r url; do
    case "$url" in https://*) ;; *) echo 'Only HTTPS upstream URLs allowed' >&2; exit 1;; esac
    echo "Testing TLS and HTTP: $url"
    # -q must be first: do not load a ~/.curlrc that could disable verification.
    curl -q --fail --silent --show-error --location --proto '=https' \
        --proto-redir '=https' --connect-timeout 15 --max-time 60 \
        --cacert "$bundle" --output /dev/null "$url"
done < "$urls"
echo 'HTTPS certificate/hostname checks passed. Archive signatures require host verification.'
