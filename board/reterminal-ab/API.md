# Proposed update API v1 — service/CLI prototype

Implementation stages:

1. This stage: a local service, CLI client, signed remote release format, publishing
   tool and host fixture/tests. Existing `reterminal-update status/install` remains
   the independent baseline. The new service is installed but not enabled by default.
2. After API review and device tests: connect LVGL settings to this API.
3. Separately: implement a browser gateway. No network API listener or browser UI
   is included in stage 1.

## Transport and authorization

One JSON request and response per Unix stream connection, each terminated by LF.
Maximum request length: 16 KiB. Default socket:
`/run/reterminal-update-api/control.sock`, directory 0700, socket 0600. Stage 1
clients must run as root. No TCP listener. Future LVGL/browser access needs an
explicit local authorization design; do not make this socket world-writable.

Request envelope: `{"api":1,"id":"client-request-id","method":"status","params":{}}`.
Response: `{"api":1,"id":"client-request-id","ok":true,"result":{...}}` or
`{"api":1,"id":"client-request-id","ok":false,"error":{"code":"busy","message":"..."}}`.
IDs correlate responses; they are not idempotency keys. Unknown methods/fields and
wrong types are rejected. Clients poll `status` for asynchronous job progress.

| Method | Params | Behavior |
|---|---|---|
| `status` | `{}` | Device baseline status, service job, verified offer, download readiness |
| `check` | `{}` | Starts metadata fetch/verification only; never downloads a bundle or installs |
| `download` | `{"offer_id":"<digest>","accept":true}` | Explicit acceptance of this exact offer; starts bundle download |
| `install` | `{"offer_id":"<digest>","accept":true}` | Separate explicit acceptance; verifies the downloaded file and invokes the baseline installer |
| `cancel` | `{}` | Requests cancellation of check/download; installation cannot be cancelled |

Mutations return `job_id`; duplicate operations while a job runs return `busy`.
There is one service job at a time. Installing always uses the existing baseline
CLI, including its cross-process lock, signature/manifest checks, inactive-slot
selection, payload readback and tryboot reboot. A competing direct CLI operation
cannot bypass that lock. CLI remains usable with this optional service stopped.

Status/job fields include `phase`, `operation`, `job_id`, `bytes_received`,
`bytes_total`, `error`, and `offer_id`. Phases include `idle`, `checking`,
`available`, `no_update`, `downloading`, `downloaded`, `installing`, `installed`,
`cancelled`, `failed`, and `interrupted`. Baseline `device.state` is authoritative
for pending/trial/committed/fallback outcomes after reboot; transfer job state never
writes `/data/ab/state.json`. An interrupted download is discarded and restarted,
not automatically resumed or installed. A new install acceptance is always required.

## Remote release envelope

Serve one JSON object over HTTPS:

```
{"signed":{...},"signature":"<base64 RSA-PKCS1-SHA256 signature>"}
```

The signature covers UTF-8 JSON of `signed`, sorted keys, compact separators,
ASCII escapes, no NaN/Infinity. Unknown/duplicate keys are rejected. Signed fields:

```
{
  "schema": 1,
  "profile": "reterminal-cm4-lvgl-v1",
  "layout": 1,
  "version": "dev-9",
  "sequence": 9,
  "expires": 1800000000,
  "notes": "Release notes",
  "bundle": {"url":"https://updates.example/dev-9.swu","size":805309296,"sha256":"..."}
}
```

HTTPS certificate verification is mandatory. Redirects, userinfo and cross-origin
bundle URLs are rejected. Metadata is limited to 64 KiB; bundles to 1100 MiB and
the exact signed size/hash. The device clock must be correct for TLS and expiry.
A persistent highest-seen sequence/digest rejects older metadata and a different
offer reusing a sequence. The same signed offer can be checked again. This does
not add global anti-downgrade policy to the independent CLI; opaque release versions
are not semantically ordered, and a first check cannot infer the installed release's
sequence. Publish only the intended channel head; keep sequences increasing.
`offer_id` is SHA-256 of the canonical signed object. A download/install request
must name it, preventing acceptance from silently moving to a different offer.

The download goes into a private service directory on Data, using a temporary file,
size/hash verification, fsync and atomic rename. Installation rechecks metadata,
file hash and bundle release binding, and delegates the signed SWU to the baseline.
A rejected/truncated/cancelled download is never passed to the installer. No arbitrary
URLs, filesystem paths, shell commands, slot choices or key changes are accepted
from API clients.

## Configuration and test tools

See `api/README.md` for exact host fixture, service, client, publication and target
commands. Configuration is root-owned `/etc/default/reterminal-updates.json`.
The sample is installed at `/usr/share/reterminal-update-api/config.example.json`;
existing persistent defaults are not overwritten. The service is opt-in and never
checks, downloads or installs automatically at startup.

For local tests only, `allow_http_loopback: true` permits HTTP to literal loopback
addresses; it never permits plain HTTP to a LAN/Internet address. The lab daemon
uses an explicit simulated device backend which refuses all installation. Production
service configuration cannot enable a simulated installation backend.


## Stage-1 validation status (2026-11-07)

The operator ran all 17 baseline and 11 API host tests successfully, including
real HTTP/Unix socket integration. The manual lab flow verified offer identity,
explicit download consent and intentional installation refusal. The real device
then used HTTPS with a separately trusted test CA to update dev-10 on A to dev-11
on B. Separate accepted download/install requests, baseline trial commit, normal
reboot (`trial: false`), Data sentinel and expanded capacity were verified.

The contract remains proposed for review before UI integration. Installation-phase
status is coarse; download bytes do not describe slot-write progress, and baseline
state remains authoritative after reboot. Existing CLI commands remain unchanged.
LVGL is next; browser authentication/gateway/network exposure remain a later stage.
On-target rejection/failure and power-cut tests are still pending; successful host
negative tests are not substitutes. Detailed results and commands are in
[the API guide](api/README.md#recorded-stage-1-results-2026-11-07).
