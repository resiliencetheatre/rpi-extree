# Local HTTPS release host: desk, TCP 9443

This is a read-only lab artifact server, not the deferred browser updater. It
serves release metadata and SWUs for the stage-1 device API. It never installs
updates, signs releases, changes UFW or starts automatically.

Prepared LAN address: **192.168.178.41**, TCP **9443**. This port was absent from the
operator's provided UFW rule list; that list does not prove no process is listening.
Check before starting. No netlink/socket availability check succeeded in the
restricted workspace. All commands below run on the PC from the workspace root
unless explicitly labeled reTerminal.

## Prepared files and trust

```text
update-host/
  host.json                 address/port
  device-config.json        proposed target API configuration
  tls/ca.pem                public test CA: copy only this certificate to device
  tls/ca-key.pem             private CA key: never serve/copy to device
  tls/server.pem            server certificate for desk's IPv4 address
  tls/server-key.pem         private TLS server key: never serve/copy to device
  www/health.json           public reachability check
  www/latest.json           signed metadata, published later by operator
  www/<release>.swu         real signed bundle, copied later by operator
```

The test CA is separate from the SWUpdate release signing key. Leaf TLS certificate
validity is 30 days; CA validity is 365 days. Certificates include the desk IP SAN,
127.0.0.1 and localhost. If the desk IP changes, prepare an appropriate new server
certificate before using the new URL. The initializer refuses to overwrite an
existing trust directory; preserve it and use a fresh directory when deliberately
creating new trust. A new CA requires copying its public certificate to the device.

The server binds only the configured IPv4 address, permits GET/HEAD for
`health.json`, `latest.json` and versioned `.swu` names, and denies directory
listings, TLS-key paths and symlinks. `update-host/` is outside the source repos;
its local `.gitignore` excludes generated material. Do not publish the parent
workspace with a generic HTTP server. Only `www/` is the document root.

To reproduce initialization on another PC (only for a fresh directory):

```sh
python3 rpi-extree/board/reterminal-ab/api/https_host.py init \
  --directory "$PWD/update-host" --address 192.168.178.41 --port 9443
```

The existing workspace's TLS material and `device-config.json` are already
prepared. Do not rerun initialization for every release.

## Check port, open the chosen UFW rule, and start

```sh
ss -ltnp '( sport = :9443 )'
```

If another service is listening, resolve that conflict first. No firewall changes
have been applied by these tools. For an operator-approved LAN rule, **assuming
192.168.178.0/24 is your trusted LAN**, run:

```sh
sudo ufw allow proto tcp from 192.168.178.0/24 to 192.168.178.41 port 9443 comment 'reTerminal update HTTPS'
sudo ufw status
```

For a narrower rule, replace the source subnet with the reTerminal's exact IPv4
address. Do not add both rules unnecessarily. Only IPv4 TCP is needed: the server
binds the supplied IPv4 address and sends no UDP traffic.

Start the server in a dedicated terminal, without sudo:

```sh
cd /home/tech/laboratory/rpireterm
python3 rpi-extree/board/reterminal-ab/api/https_host.py serve \
  --directory "$PWD/update-host"
```

From another PC terminal, verify the certificate and health endpoint:

```sh
cd /home/tech/laboratory/rpireterm
curl --fail --cacert update-host/tls/ca.pem \
  https://192.168.178.41:9443/health.json
```

Expect `{"service":"reterminal-update-test-host","https":true}` (spacing can
vary). Do not use `curl -k`; it would skip the trust check being tested.
`latest.json` returns 404 until you publish a real signed release.

## Configure target trust persistently

The target must first run a release containing the optional API service, Python
SSL and CA support. Bootstrap that release through the tested local CLI, commit
it, then ordinary-reboot. Check on reTerminal:

```sh
cat /etc/reterminal-ab/version
command -v reterminal-update-client
python3 -c 'import ssl; print(ssl.OPENSSL_VERSION)'
reterminal-update status
```

No fixture bundle belongs on hardware. The real target must use its embedded
release-verification public key, not the lab fixture public key.

On reTerminal, prepare a persistent CA location:

```sh
mkdir -p /data/update-api/trust
```

On the PC, replace `<RETERM_IP>` with the target's real IPv4 address:

```sh
scp update-host/tls/ca.pem root@<RETERM_IP>:/data/update-api/trust/desk-ca.pem
scp update-host/device-config.json root@<RETERM_IP>:/etc/default/reterminal-updates.json
```

Review/back up an existing target API configuration before replacing it. Its
intended contents are:

```json
{
  "manifest_url": "https://192.168.178.41:9443/latest.json",
  "public_key": "/etc/reterminal-ab/public.pem",
  "data_dir": "/data/update-api",
  "ca_file": "/data/update-api/trust/desk-ca.pem",
  "allow_http_loopback": false
}
```

Both the CA under Data and config under `/etc/default` survive slot updates.
Putting the operator-installed CA only in slot-local `/etc/reterminal-ab` would
lose it on the next release. Check the target clock before TLS/expiry tests:

```sh
date -u
python3 - <<'PY'
import json, ssl, urllib.request
context = ssl.create_default_context(cafile='/data/update-api/trust/desk-ca.pem')
with urllib.request.urlopen('https://192.168.178.41:9443/health.json', context=context, timeout=10) as response:
    print(json.load(response))
PY
```

This verifies target-to-PC routing, UFW and CA/IP validation without requesting an
update. A timeout suggests routing/firewall/listener issues; certificate errors
require checking trust, SAN and clocks, not disabling TLS verification.

## Publish a real release and check availability

The following example assumes a real `dev-12.swu` has already been built/signed
with the key trusted by the target, and that this release differs from the target's
installed release. Choose an unused version and monotonically increasing sequence
appropriate to your actual test. These are commands for the operator; no release
build or signing is performed by server initialization.

```sh
cp --reflink=auto releases/dev-12/dev-12.swu update-host/www/dev-12.swu
python3 rpi-extree/board/reterminal-ab/api/publish.py \
  --bundle update-host/www/dev-12.swu \
  --key "$PWD/ab-development-private.pem" \
  --url https://192.168.178.41:9443/dev-12.swu \
  --sequence 12 --expires-in-days 7 \
  --notes 'Local HTTPS update test' \
  --output update-host/www/latest.json.new
mv update-host/www/latest.json.new update-host/www/latest.json
```

The server does not expose `.new` files. Copy the immutable bundle first, then
atomically publish metadata. Reusing a sequence for different metadata, including
a changed expiry or URL, is rejected by the API; increase the sequence when changing
any signed field. Never serve the release signing private key or TLS private keys.

On reTerminal:

```sh
systemctl restart reterminal-update-api
reterminal-update-client status
reterminal-update-client check
reterminal-update-client wait
```

Expect a verified offer, no offer error, and `download_ready: false`. Checking must
not download the bundle. Read version, size and notes, then explicitly accept the
actual returned offer ID for download. Installation requires a separate acceptance:

```sh
offer_id=PASTE_THE_ACTUAL_VERIFIED_OFFER_ID
reterminal-update-client download --offer "$offer_id" --accept
reterminal-update-client wait
reterminal-update-client status
# Only after reviewing and accepting the downloaded release:
reterminal-update-client install --offer "$offer_id" --accept
```

A real accepted installation reboots. Use the baseline status/version/sentinel/Data
checks, require `committed`, ordinary-reboot, then require `trial: false`. See the
[stage-1 API guide](README.md) and [board operator guide](../README.md).

## Stop and validation

Ctrl-C stops the PC host. To remove the subnet rule above when no longer needed:

```sh
sudo ufw delete allow proto tcp from 192.168.178.0/24 to 192.168.178.41 port 9443
```

For an exact-device rule, delete the corresponding exact-device rule instead.
No UFW reset, global allow rule or router port-forwarding is needed.

Run on the PC:

```sh
python3 rpi-extree/board/reterminal-ab/api/test_https_host.py
```

The restricted workspace passed four tests using real TLS handshakes over memory
BIOs: trusted IP succeeds; wrong IP/untrusted CA fail; private paths/listings and
symlinks are denied; initialization preserves existing trust. One real HTTPS socket
test is skipped because the sandbox denies socket creation. Run the same command
on the PC to include that fifth automated test; its full execution has not been
reported. Separately, the operator started this server and successfully fetched
`health.json` from both the PC and reTerminal using the CA and IP verification.
The subsequent real dev-11 bundle/metadata transfer and installation passed. These
manual LAN/TLS results are independent of the skipped sandbox socket test. No card
or EEPROM is changed by the host tools.


## Recorded HTTPS/API deployment

On 2026-11-07 the operator verified the running server at
`https://192.168.178.41:9443/health.json` from reTerminal with
`ssl.create_default_context(cafile='/data/update-api/trust/desk-ca.pem')`.
The UTC device clock was correct. The API then fetched signed dev-11 metadata
(sequence 11), downloaded the complete 805309300-byte bundle only after explicit
acceptance, and installed only after a separate accepted request. The existing
installer trial-booted B, committed dev-11, and a normal reboot retained B with
`trial: false`. The sentinel and 27.4G Data filesystem survived.

The example publication commands above now use the next illustrative version,
dev-12/sequence 12. Do not republish changed dev-11 metadata with sequence 11: a
changed expiry, URL or note requires a new sequence. TLS server keys and the SWU
signing private key remain separate and outside the served document root.

This completes the first real remote API happy-path test. Browser UI was not
implemented; this server remains an artifact host only. LVGL integration is now implemented and the operator reports its happy path
working; see the board validation record. Failure/rejection, rollback and power-cut gates in
the board guide remain in force.
