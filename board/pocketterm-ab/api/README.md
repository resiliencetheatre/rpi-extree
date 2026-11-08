# PocketTerm HTTPS hosting and device API

For the complete local development, kernel refresh, public SWU and factory-image
workflow, read [Development and release lifecycle](../DEVELOPMENT.md) first.

The PC host serves immutable SWUs and signed offers; the target API listens only
on a root-only Unix socket. No automatic check, download or installation occurs.
First validate the local CLI on spare hardware. Never reuse reTerminal metadata.
Keep a separate PocketTerm host directory and monotonically increasing sequence.

From the workspace root, initialize a fresh host once (substitute the actual PC
IPv4 address), then keep the server running in a separate terminal:

```sh
python3 rpi-extree/board/pocketterm-ab/api/https_host.py init \
  --directory "$PWD/pocketterm-update-host" --address <PC_IPV4> --port 9443
python3 rpi-extree/board/pocketterm-ab/api/https_host.py serve \
  --directory "$PWD/pocketterm-update-host"
```

Initialization refuses existing trust. TLS private keys stay outside `www/`.
Check routing/listener/firewall yourself; no script changes the firewall.
Verify `/health.json` with the generated CA, never disable TLS verification.

## First-time device trust and API configuration

These steps are required before Settings → System update can contact the API.
The HTTPS host initializer does not create `device-config.json`; create the target
configuration explicitly below. Repeat for each newly provisioned device, not for
every release. Do not regenerate host TLS trust for a routine release.

On **PocketTerm**, create the persistent public CA directory:

```sh
mkdir -p /data/update-api/trust
```

On the **PC**, from the workspace root, replace `<POCKETTERM_IP>` with the
device address and copy only the public CA certificate:

```sh
scp pocketterm-update-host/tls/ca.pem \
  root@<POCKETTERM_IP>:/data/update-api/trust/host-ca.pem
```

Never copy `ca-key.pem`, `server-key.pem` or the release signing private key to
the device. The HTTPS CA and the SWUpdate release verification key serve different
purposes; the latter is already provisioned at `/etc/pocketterm-ab/public.pem`.

On **PocketTerm**, create the configuration if absent. This example uses the lab
PC address `192.168.178.41`; replace it with your actual host address, matching
its certificate. Review an existing configuration before deliberately editing it;
the command below preserves it.

```sh
test -f /etc/default/pocketterm-updates.json || cat > /etc/default/pocketterm-updates.json <<'EOF'
{
  "manifest_url": "https://192.168.178.41:9443/latest.json",
  "public_key": "/etc/pocketterm-ab/public.pem",
  "data_dir": "/data/update-api",
  "ca_file": "/data/update-api/trust/host-ca.pem",
  "allow_http_loopback": false
}
EOF

chmod 600 /etc/default/pocketterm-updates.json
date -u
python3 -c 'import ssl; print(ssl.OPENSSL_VERSION)'
systemctl restart pocketterm-update-api
pocketterm-update-client status
```

The device clock must be correct for TLS certificates and signed offer expiry.
Both the CA under `/data` and configuration under persistent `/etc/default`
survive slot updates. After configuration, reopen **Settings → System update**
and select **Check for updates**. Checking does not download or install.

If Settings reports **Installed: unavailable** or **update service unavailable**,
the UI cannot reach the local API. Inspect:

```sh
systemctl status pocketterm-update-api --no-pager -l
journalctl -b -u pocketterm-update-api --no-pager -n 80
```

The API unit is conditional on `/etc/default/pocketterm-updates.json` existing.
LVGL Wants the service; explicitly restarting it after configuration starts it
without restarting LVGL. The UI uses the inherited `RETERMINAL_UPDATE_SOCKET`
environment variable with `/run/pocketterm-update-api/control.sock`; there is no
ordering cycle through health. For connection/offer errors after the API starts,
check the host is running, device routing, CA path, certificate address and clock;
do not disable TLS verification.

After the initial factory build and host initialization, build/sign/verify/publish
an unused dev-N release with the one-command wrapper:

```sh
RELEASE_BASE_URL=https://<PC_IPV4>:9443 \
AB_SIGN_KEY=/absolute/path/private.pem AB_VERIFY_KEY=/absolute/path/public.pem \
  rpi-extree/board/pocketterm-ab/release.sh dev-2
```

Defaults: `output-pocketterm-ab`, `pocketterm-update-host`, `pocketterm-releases`.
Override `RELEASE_WORKSPACE`, `RELEASE_OUTPUT`, `RELEASE_HOST` using absolute paths.
The wrapper refreshes local LVGL, builds, signs and verifies through publisher
before publishing the immutable bundle then atomically replacing latest.json.
It serializes wrapper runs but does not coordinate manual builds. Other changed
dependencies need their own refresh. On failure inspect partial release artifacts;
choose a new version rather than overwriting. Previous metadata stays in place
until publication; a failure between bundle and metadata publication may leave an
unadvertised immutable bundle. Do not reinitialize keys/configuration to recover.

On target use Settings → System update, or:

```sh
pocketterm-update-client status
pocketterm-update-client check
pocketterm-update-client wait
pocketterm-update-client status
pocketterm-update-client download --offer <VERIFIED_OFFER_ID> --accept
pocketterm-update-client wait
pocketterm-update-client install --offer <VERIFIED_OFFER_ID> --accept
```

Download and install require separate acceptance of the verified offer ID.
Installation reboots; require committed status, then Finish update/Restart or a
normal reboot. Later only dismisses the prompt; installation remains blocked in
trial mode. Progress is observational, pinned SWUpdate packed little-endian ABI
v2.0; unavailable/unknown progress degrades to stages and cannot authorize commit.
Check actual display dimensions and layout, scrolling, fixed confirmation footer and input on
hardware; no PocketTerm UI hardware result is claimed.

## Public releases with rclone

`release-public.sh` builds and publishes to the tested destination
`hetzner-web:public_html/pocketterm` and public URL
`https://resilience-theatre.eu/pocketterm`. Keep rclone credentials in the existing
operator rclone configuration, outside the repository. No Python server is needed
on the public host. Only a versioned SWU, `<version>.SHA256SUMS` and signed
`latest.json` are uploaded; signing/TLS keys and device configuration are excluded.

From the workspace root, choose an unused dev-N higher than any offer sequence
already accepted by the devices (including local lab offers):

```sh
rpi-extree/board/pocketterm-ab/release-public.sh dev-4
```

This is a real build and publication command. It refreshes local LVGL first.
Use `--help` for absolute workspace/output/key paths, `RELEASE_REMOTE`,
`RELEASE_BASE_URL`, notes, jobs and expiry overrides. It shares the local wrapper's
process lock; do not run manual builds or other publishers concurrently.

Preflight requires an accessible existing remote directory and server-side Move
support. Existing bundles/checksums are never overwritten. The previous offer is
signature/profile checked (even if expired), and its sequence must be lower.
The wrapper builds/signs/verifies locally, uploads the immutable SWU and versioned
checksum, reads back the entire SWU over public certificate-verified HTTPS, then
uploads metadata to a temporary name and moves it to `latest.json`. Configure the
hosting backend to support atomic rename-over-existing for that final move;
rclone's Move capability alone cannot guarantee backend atomicity. No concurrent
publisher is supported; the local lock does not coordinate other PCs.

HTTPS must serve exact file bytes without redirects, login challenges or content
rewriting. Disable caching/revalidate `latest.json`; immutable SWUs can be cached.
Public metadata and bundle must share the same HTTPS origin. Public readback costs
one full SWU download on the build PC. A failed pre-publication check leaves the
old offer alone but may leave a local release directory or unadvertised remote
bundle/checksum/temp file. Inspect these artifacts and choose a fresh version;
there is no automatic cleanup or retry that overwrites a version. A failure after
the metadata move may mean the new offer is already live: inspect public
`latest.json` and caches before retrying. Never regenerate keys to recover.

On each PocketTerm, review/edit `/etc/default/pocketterm-updates.json` to use:

```json
{
  "manifest_url": "https://resilience-theatre.eu/pocketterm/latest.json",
  "public_key": "/etc/pocketterm-ab/public.pem",
  "data_dir": "/data/update-api",
  "allow_http_loopback": false
}
```

Omit the local `ca_file` when using the host's publicly trusted certificate, so the
system CA store is used. Keep the existing release verification key. Restart
`pocketterm-update-api`, check status, then explicitly Check for updates. Download
and installation still require separate acceptance. Signed offer expiry defaults
to seven days; refreshing expiry/notes/URL requires a fresh increasing sequence.

### Installer startup lock contention

If `install.log` ends at `fcntl.flock` with `BlockingIOError`, the controller
failed to acquire its lock before inspecting or writing slots. API polling used
to be able to race delegated installer startup even though status/preflight calls
were mutually serialized. The API now drains in-flight status calls and serves
cached pre-install device status during delegated installation, while keeping
progress polling responsive. Fresh device status resumes after installer exit;
the independent CLI/process lock and all install validation remain enforced.

For an affected device still running a normal boot with empty transaction state,
bootstrap the API fix by copying `api_service.py` to
`/usr/lib/pocketterm-ab/api_service.py` and restarting `pocketterm-update-api`.
The retained download is revalidated on fresh explicit install acceptance. Do not
delete the lock file or update state. Incorporate the fix in the next SWU/factory
build; the bootstrap edit alone is slot-local and replaced by system updates.
