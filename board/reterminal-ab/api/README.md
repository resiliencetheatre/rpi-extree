# Stage 1: local update service and command-line API tests

Read [the proposed API contract](../API.md) first. This stage implements remote
release checking, explicit download acceptance and explicit installation acceptance.
The stage 2 LVGL client is described below. The service leaves the tested
`reterminal-update status/install` entry point unchanged. The API service is opt-in,
root-only and Unix-socket-only; it never checks or downloads automatically.

## Files and commands

| File | Purpose |
|---|---|
| `../API.md` | Proposed v1 transport, methods, states and signed release envelope |
| `../api_service.py` | Serialized asynchronous service; delegates slot writes to baseline CLI |
| `../api_client.py` | CLI client, installed as `reterminal-update-client` |
| `../remote_release.py` | Metadata/signature, HTTPS, size/hash and version-binding checks |
| `publish.py` | Creates signed channel metadata for an existing signed SWU |
| `fixture.py` | Disposable host-only release server with separate development trust |
| `test_api.py` | Host tests using a simulated installer; never writes target partitions |
| `config.example.json` | Sample target configuration |

Progress bytes refer to downloads. Installation exposes its stage, a log and
optional read-only SWUpdate per-image/step progress; stages without measured
progress do not fabricate a percentage. The authoritative trial/commit/fallback
outcome is always `status.result.device.state`, obtained from the baseline CLI.
No new code edits `/data/ab/state.json` or the selector directly.

## Run host tests first

From the workspace root:

```sh
python3 rpi-extree/board/reterminal-ab/test_ab.py
python3 rpi-extree/board/reterminal-ab/api/test_api.py
```

The baseline suite has 17 tests. The API suite has 11 tests; the operator ran all
17 + 11 successfully on the PC, including real HTTP/Unix socket integration. Ten API tests pass in
the restricted workspace and the real socket integration test is skipped because
the sandbox denies creating sockets. The other tests still use real RSA signatures,
metadata validation and streamed download logic with a substituted HTTP I/O boundary.
On a normal PC, the suite also starts a loopback HTTP server and Unix API socket
and tests actual request/response framing. No test invokes real SWUpdate or reboot.
The lab backend explicitly rejects installation. Do not interpret a skipped socket
test as end-to-end transport validation.

## Try the proposed API on your PC without hardware

Use three terminals. Start the fixture in terminal 1:

```sh
python3 rpi-extree/board/reterminal-ab/api/fixture.py \
  --directory /tmp/reterminal-update-api-lab --port 9080
```

It generates its own key pair and tiny, signed **nonbootable** fixture bundle. The
HTTP server binds only `127.0.0.1`, serves only `www/`, and never serves the private
key in `secrets/`. Do not use a production signing key here or install fixture
bundles on reTerminal. The fixture public key is unrelated to the device trust.

In terminal 2, start the simulated service:

```sh
python3 rpi-extree/board/reterminal-ab/api_service.py --lab \
  --config /tmp/reterminal-update-api-lab/lab-config.json \
  --socket /tmp/reterminal-update-api-lab/run/control.sock
```

`--lab` simulates device status and **refuses every installation**. It does not run
the baseline controller, SWUpdate, block-device tools or reboot. This mode is not
present in the target systemd command line and cannot be enabled through the API.

In terminal 3, use the client (run commands from the workspace root):

```sh
client="$PWD/rpi-extree/board/reterminal-ab/api_client.py"
socket=/tmp/reterminal-update-api-lab/run/control.sock
python3 "$client" --socket "$socket" status
python3 "$client" --socket "$socket" check
python3 "$client" --socket "$socket" wait
```

`check` returns a job ID; `wait` polls until it completes. Inspect
`result.offer`, including version, notes, size, sequence and `offer_id`. Checking
alone downloads no SWU. Copy the actual digest from the response:

```sh
offer_id=PASTE_THE_VERIFIED_OFFER_ID
python3 "$client" --socket "$socket" download --offer "$offer_id" --accept
python3 "$client" --socket "$socket" wait
python3 "$client" --socket "$socket" status
```

Without `--accept`, the request fails. A stale/different offer ID also fails.
A completed download reports `phase: downloaded` and `download_ready: true`.

An installation request in lab mode exercises validation, then ends with
`lab_install_disabled`; it never writes or reboots anything:

```sh
python3 "$client" --socket "$socket" install --offer "$offer_id" --accept
python3 "$client" --socket "$socket" wait
```

The client exits nonzero for the expected failed lab installation. To test
cancellation on a real download, issue `cancel` while the job is running. Very small
fixture jobs can complete before cancellation arrives. Installation is not
cancellable. Cancellation is cooperative; a blocked network read can take up to
the network timeout to return.

Stop fixture and lab service with Ctrl-C. A restarted service never automatically
installs a cached download. Partial downloads are discarded; metadata sequence
history and completed download state are retained in its configured data directory.

## Prepare a real release server

Build and sign a real `.swu` with the existing workflow in the board README. Do not
change its profile/layout or replace the key trusted by deployed devices. Then
publish a signed channel head. This example does not build, deploy or upload anything:

```sh
python3 rpi-extree/board/reterminal-ab/api/publish.py \
  --bundle releases/dev-12/dev-12.swu \
  --key "$PWD/ab-development-private.pem" \
  --url https://updates.example.com/reterminal-cm4-lvgl-v1/dev-12.swu \
  --sequence 12 --expires-in-days 7 \
  --notes 'Clean Buildroot release test' \
  --output releases/dev-12/latest.json
```

The tool validates the bundle's inner signatures, payload hashes, canonical
manifest and version binding, then signs remote metadata with the same key. It
also needs temporary disk space for payload verification. The release version is
read from the bundle; it is not a separately editable publisher argument.

Serve these two files on the **same HTTPS origin**:

```text
https://updates.example.com/reterminal-cm4-lvgl-v1/latest.json
https://updates.example.com/reterminal-cm4-lvgl-v1/dev-12.swu
```

Upload the immutable versioned bundle first, then replace `latest.json` atomically.
Do not serve the private signing key. No redirects or cross-origin CDN URLs are
accepted by this initial API. HTTPS uses the system CA store, optionally a custom
`ca_file` set by the operator. Do not turn off certificate verification.

Use strictly increasing channel sequences. A sequence already observed with a
different signed payload is rejected, including changes to notes, URL or expiry;
issue a new sequence when refreshing metadata. Repeating identical signed metadata
is allowed. The device clock must be correct and metadata must not be expired.
The first metadata sequence does not establish the installed version's place in
an ordering; version strings remain opaque and the independent CLI's downgrade
behavior is unchanged. A check reports a different offered version, not a semantic
version comparison. Keep the server channel pointed at the intended release.

## Build/install the optional API on target

No build or signing is performed by these test tools automatically. The A/B profile
now selects Python SSL support and CA certificates. For an existing output, preserve
local configuration changes, reload the updated defconfig and rebuild Python from a fresh package directory:

```sh
make -C buildroot O="$PWD/output-reterminal-ab" \
  BR2_EXTERNAL="$PWD/rpi-extree" raspberrypi4_reterminal_ab_defconfig
make -C buildroot O="$PWD/output-reterminal-ab" python3-dirclean
```

Then build/sign a new release using the normal commands and your chosen new release
version. A fresh clean output needs no Python clean step. An observed reused output
retained `_ssl=n/a` after reconfiguration, so `python3-dirclean` is the conservative
upgrade path when adding TLS. The A/B post-build hook now rejects a rootfs missing
the `_ssl` shared extension. Deploy that bundle
using the existing local `reterminal-update install` baseline first, confirm commit,
and ordinary-reboot before testing this new service.

On reTerminal, create the operator configuration explicitly:

```sh
test -e /etc/default/reterminal-updates.json || \
  cp /usr/share/reterminal-update-api/config.example.json /etc/default/reterminal-updates.json
vi /etc/default/reterminal-updates.json
```

Set `manifest_url` to your HTTPS endpoint. Retain the embedded public key path,
`/data/update-api`, and `allow_http_loopback: false`. `/etc/default` is persistent;
new builds do not overwrite existing operator configuration. Then start the service
for this session (do not enable at boot until tests pass):

```sh
systemctl start reterminal-update-api
journalctl -u reterminal-update-api -b
reterminal-update-client status
reterminal-update-client check
reterminal-update-client wait
```

Status responses wrap baseline status in `result.device`. Verify its slot,
`trial: false`, installed version and no pending transaction, then inspect the offer.
After explicit user acceptance of that exact release:

```sh
offer_id=PASTE_THE_VERIFIED_OFFER_ID
reterminal-update-client download --offer "$offer_id" --accept
reterminal-update-client wait
reterminal-update-client status
```

Downloading does not install or reboot. Once it is ready, a **separate** accepted
install request invokes the unchanged baseline installer and will reboot on success:

```sh
reterminal-update-client install --offer "$offer_id" --accept
```

Do not stop the service or interrupt power during installation. Cancellation is
rejected for install jobs. A baseline installer already started by an accepted
request is not killed when its API service is stopped. Its own lock prevents a
second installation. If a direct baseline command is in progress, API requests can
report `device_unavailable`; it does not bypass that lock.

After reboot, use the baseline commands for acceptance:

```sh
reterminal-update status
cat /etc/reterminal-ab/version
cat /data/ab-test-sentinel
df -h /data
systemctl --failed
```

Require the new slot/version and `phase: committed`, perform an ordinary reboot,
then require the same slot/version with `trial: false`. Check persisted API state
and the baseline outcome before retrying a request interrupted by reboot. The
optional API service is not enabled by default, so start it again if needed.

Service diagnostics:

```sh
cat /data/update-api/service.json
cat /data/update-api/install.log
journalctl -u reterminal-update-api -b
```

`install.log` is created only for baseline invocation; `service.json` tracks API
jobs/offers and is separate from `/data/ab/state.json`. Do not edit either to bypass
an error. Normal service restart marks a running transfer job interrupted and does
not auto-resume it. A fresh explicit install acceptance is required after restart.

## Recorded stage-1 results (2026-11-07)

The operator completed the following, separately from sandbox-only test results:

| Check | Observed result |
|---|---|
| PC baseline/API suites | All 17 + 11 tests passed; no socket skip on PC |
| Lab check | Valid signed lab-1 offer; no bundle downloaded |
| Lab accepted download | Exactly 2808 bytes, downloaded/ready |
| Lab accepted install | Expected `lab_install_disabled`, no SWUpdate or reboot |
| Device bootstrap | dev-9 included the client but lacked `_ssl`; corrected with Python clean rebuild in dev-10 |
| Device TLS | `OpenSSL 3.6.5 29 Sep 2026`, correct UTC clock, successful CA/IP-verified HTTPS health request |
| Real check | Sequence 11, dev-11 offer while normal dev-10 ran on A; download readiness false |
| Accepted download | 805309300 bytes, completed verification/flush, download readiness true |
| Accepted installation | Delegated to existing installer; automatic trial boot into B |
| Trial health/commit | dev-11, B, trial true, phase committed |
| Ordinary reboot | dev-11, B, trial false, phase committed |
| Persistence | Sentinel `expanded-data-survives` unchanged; Data filesystem remains 27.4G |

The actual signed bundle digest was
`ce429877753b226a3c363b82b2570c3720b0a7acebdeb2e0cc877dce7f14b00a`;
its immutable offer ID was
`6fd6b73fd5f14b8b2a31ec8f959980d7cc50506de79c9536ebb8cb1a7b62d35a`.
These identify the recorded test, not a fresh deployment instruction. For a new
release, choose a new version/sequence and use the returned offer ID; do not reuse
these values or edit old metadata in place.

Three operator lessons from this test:

- Set `client="$PWD/.../api_client.py"` only after entering the workspace. Changing
  directories later does not change the absolute path already stored in `$client`.
- Explicitly assign the current `offer_id` from the response. An empty/stale shell
  variable returns `offer_changed`; download must finish before install.
- `wait` is quiet while a job is active. Poll `status` from another console. Full
  byte count can appear before the final fsync/rename completes; wait for both
  `phase: downloaded` and `download_ready: true`. During install, bytes reset to
  zero and are not write progress. Pre-install signature/payload verification
  precedes creation of `install.log`; its temporary absence is expected. Keep
  power connected and do not submit another install or restart the service.

This validates the happy path, not on-device rejection, fallback, cancellation
under adverse networking, or power-cut behavior. The LVGL integration below uses
this same API and awaits hardware validation; the browser gateway remains a later stage.

## Review and acceptance before LVGL

- Review the v1 contract: two separate consent actions, offer identity, sequence and
  expiry policy, error codes, root-only socket access and download progress fields.
- Completed: real-socket PC suite and manual lab fixture/client workflow.
- Completed: target Python TLS/CA and HTTPS endpoint trust. Measure transfer/write
  timings more systematically for UI progress expectations.
- Confirm a check alone does not download; download alone does not install/reboot.
- Confirm bad signatures, expired/wrong-profile metadata, changed offers, wrong
  sizes/hashes, redirects, insufficient space, interrupted transfers and active
  trials are rejected without invoking the installer.
- Completed: accepted real dev-11 API installation, commit and ordinary reboot
  verified through baseline commands. Reverse-direction remote/API testing remains.
- Keep the original local CLI available throughout. Power-cut/fallback acceptance
  gates in the board README still apply independently of this API.

The LVGL controls below are implemented as a separate step, pending device testing.
Browser gateway design, authentication and network exposure remain another step;
this service intentionally opens no HTTP port.

## Local HTTPS host on desk

A separate [HTTPS hosting guide](HTTPS-HOST.md) prepares `192.168.178.41:9443`,
certificate trust, an operator-run UFW rule, and real release publication. This
read-only artifact server is not the deferred browser updater. It uses separate
TLS keys and keeps them outside the public document root.

## Stage 2 implementation: LVGL Settings client

The new LVGL System update panel uses this same Unix API. It has Check for updates
and Update controls; Update first asks for download consent, then becomes Install
update and asks for separate install/restart consent. It pins the reviewed offer
ID and disables update actions during active jobs and trial boots. Background RPC
and local status polling do not run on the LVGL event thread. Opening Settings
never automatically checks the remote server.

New A/B builds add a LVGL `Wants=reterminal-update-api.service` drop-in. The API
still requires its operator-created config and performs no automatic remote work.
It is not explicitly enabled globally. No `After=API` ordering is added to LVGL:
that would cycle through health confirmation, which requires LVGL readiness.

The API now adds `job.stage` (`verifying_bundle`, `installing_slots`) and optional
`job.swupdate` (`status`, `image`, `handler`, `step`, `steps`, `percent`, `info`).
This is a read-only observer of `/run/reterminal-ab/progress`, using the pinned
SWUpdate 2026.05.1 packed little-endian progress ABI v2.0. Unknown ABI or a missing
stream produces no percentage and never changes installation/activation policy.
Success from the SWUpdate stream is not trial success: readback/activation and
subsequent health/commit remain the baseline controller's responsibility.

For a configured dev-11 device, build a new release (for example dev-12) with both
API and UI changes. The operator performs these commands from the workspace root:

```sh
make -C buildroot O="$PWD/output-reterminal-ab" \
  BR2_EXTERNAL="$PWD/rpi-extree" raspberrypi4_reterminal_ab_defconfig
make -C buildroot O="$PWD/output-reterminal-ab" lvgl-console-local-dirclean
AB_RELEASE_VERSION=dev-12 AB_VERIFY_KEY="$PWD/ab-development-public.pem" \
  make -C buildroot O="$PWD/output-reterminal-ab" -j4
mkdir -p releases/dev-12
python3 rpi-extree/board/reterminal-ab/package.py \
  --images output-reterminal-ab/images --version dev-12 \
  --key "$PWD/ab-development-private.pem" --output releases/dev-12/dev-12.swu
```

Preserve local configuration customizations before reloading. Existing TLS and
Data-growth dependencies must already be configured as above; a fresh output builds
them directly. Deploy this first UI-enabled release using the existing tested CLI
or API and confirm it plus an ordinary reboot. Then publish a subsequent release
(e.g. dev-13/sequence 13) on the existing HTTPS host and exercise the Settings panel.
Keep the local CLI available for diagnosis. Do not install lab fixture bundles.

Run the new progress decoder tests without hardware:

```sh
python3 rpi-extree/board/reterminal-ab/api/test_swupdate_progress.py
```

For native LVGL tests, install json-c development support and follow the app's
CMake/CTest instructions. Test no-offer, offer, consent cancel, stale offer,
network failure, downloading, completed-download, verification, SWUpdate writing,
readback/reboot, trial blocking and normal reboot on the spare card. No browser
UI or network-facing update API was added. The operator has since reported the LVGL happy path working; see the
[board validation record](../README.md#lvgl-update-operation-and-validation-record).
Failure-path and power-cut validation remain separate requirements.


### Finish update and preflight contention fix

A committed trial now offers Finish update in Settings, with Restart and Later.
Restart calls the additive `finish` API method and requests a normal reboot;
Later dismisses the prompt without enabling another installation. See
[the API contract](../API.md#finish-a-committed-trial-settings).

API baseline status polling and worker preflight are serialized within the
engine. Previously they could race for the CLI lock and reject an installation
before writes with `device_unavailable`. Retained downloads can now be retried
from Settings after a failed job when fresh baseline status allows installation.
The independent CLI installation path remains unchanged.

Build and publish subsequent versions with `../release.sh dev-N` (from this
folder), or `rpi-extree/board/reterminal-ab/release.sh dev-N` from the workspace.
Keep the HTTPS host running; no server restart is needed for new metadata.
The operator reports the revised flow working. The 13-test API suite includes a
regression proving worker status and UI polling cannot enter baseline status
concurrently; one real-socket test remains skipped in the restricted workspace.
