#!/usr/bin/env python3
"""Interactive serial/SSH updater using the controlled root-only API."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import sys
import time
from api_client import call
from common import PROFILE, LAYOUT

SOCKET = '/run/edgemap-update-api/control.sock'
PENDING = Path('/data/ab/wrapper-reboot.json')
ACTIVE = {'checking', 'downloading', 'installing'}


def say(message):
    print(message, flush=True)


def rpc(method, params=None, startup=False):
    deadline = time.monotonic() + (90 if startup else 0)
    waiting = False
    while True:
        try:
            response = call(SOCKET, method, params or {})
            break
        except (FileNotFoundError, ConnectionRefusedError):
            if time.monotonic() >= deadline:
                raise RuntimeError('Update API socket unavailable; inspect systemctl status edgemap-update-api')
            if not waiting:
                say('Waiting for update API readiness...')
                waiting = True
            time.sleep(1)
    if not response.get('ok'):
        error = response.get('error', {})
        raise RuntimeError(f"{error.get('code', 'api_error')}: {error.get('message', 'Request failed')}")
    return response['result']


def device(value):
    if value.get('device_error') or not value.get('device'):
        raise RuntimeError(f"Device unavailable: {value.get('device_error')}")
    return value['device']


def summary(value):
    current = device(value)
    say(f"Current: {current['version']} | slot {current['slot'].upper()} | trial={current['trial']}")
    say(f"State: {current['state'].get('phase', 'factory')} | job: {value['job']['phase']}")
    say(f"Source: {value.get('source') or 'configured'} | {value.get('manifest_url', '')}")
    offer = value.get('offer')
    if offer:
        say(f"Offered: {offer['version']} | sequence {offer['sequence']}")
    if value.get('offer_error'):
        say(f"Offer error: {value['offer_error']}")


def progress(value):
    job = value['job']
    text = f"{job['phase']}: {job.get('stage') or job.get('operation') or ''}"
    if job.get('operation') == 'download':
        done, total = job.get('bytes_received', 0), job.get('bytes_total')
        text += f" | {done / 1024**2:.1f} MiB"
        if total:
            text += f" / {total / 1024**2:.1f} MiB ({100 * done / total:.0f}%)"
    write = job.get('swupdate')
    if write and write.get('status') in ('success', 'done'):
        text += ' | SWUpdate finished; controller flush/readback checks may still be running'
    elif write:
        text += f" | {write.get('image') or 'SWUpdate'} {write.get('percent', 0)}% (image {write.get('step', 0)}/{write.get('steps', 0)})"
    return text


def wait_job(job_id, operation, timeout=7200):
    deadline = time.monotonic() + timeout
    last, printed = None, 0
    while True:
        value = rpc('status')
        job = value['job']
        if job.get('job_id') != job_id or job.get('operation') != operation:
            raise RuntimeError('Update job changed; inspect update.sh --status')
        text = progress(value)
        now = time.monotonic()
        if text != last or now - printed >= 10:
            say(text)
            last, printed = text, now
        if job['phase'] not in ACTIVE:
            if job['phase'] in ('failed', 'interrupted', 'cancelled'):
                raise RuntimeError(f"{operation} {job['phase']}: {job.get('error')}")
            return value
        if now >= deadline:
            raise RuntimeError('Monitoring timed out; accepted work continues. Use update.sh --status')
        time.sleep(2)


def save_pending(value):
    PENDING.parent.mkdir(parents=True, exist_ok=True)
    stage = PENDING.with_name(PENDING.name + '.new')
    fd = os.open(stage, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(value, out)
        out.flush()
        os.fsync(out.fileno())
    os.replace(stage, PENDING)
    flush_pending()


def flush_pending():
    fd = os.open(PENDING.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def clear_pending():
    PENDING.unlink(missing_ok=True)
    flush_pending()


def finish_pending():
    if not PENDING.exists():
        return
    pending = json.loads(PENDING.read_text())
    value = rpc('status', startup=True)
    current = device(value)
    state = current['state']
    if value['job']['phase'] in ACTIVE:
        raise RuntimeError('Update job active; leaving final reboot record for diagnosis')
    match = (pending.get('profile') == PROFILE and pending.get('layout') == LAYOUT
             and state.get('profile') == PROFILE and state.get('layout') == LAYOUT
             and current['version'] == pending['version'] and current['slot'] == pending['target']
             and state.get('version') == pending['version'] and state.get('target') == pending['target']
             and state.get('previous') == pending['previous'] and state.get('phase') == 'committed')
    if not current['trial']:
        say('Normal boot; no automatic reboot needed.' if match else
            'Requested trial was not committed on its target; no automatic reboot. Inspect update status and journal.')
        clear_pending()
        return
    if not match:
        raise RuntimeError('Trial does not match the accepted committed release; no automatic reboot')
    say(f"{pending['version']} committed on slot {pending['target'].upper()}; finishing with an ordinary reboot.")
    rpc('finish', {'accept': True})  # API repeats fresh device/version/slot/job checks.
    clear_pending()


def update(source):
    value = rpc('status', startup=True)
    summary(value)
    current = device(value)
    if value['job']['phase'] in ACTIVE:
        raise RuntimeError('An update is already active. Use update.sh --status')
    if current['trial']:
        raise RuntimeError('Previous trial still active. If committed, run systemctl reboot first')
    rpc('select-source', {'source': source})
    say(f'Checking {source} source...')
    job = rpc('check')
    value = wait_job(job['job_id'], 'check')
    current = device(value)
    offer = value.get('offer')
    if value.get('offer_error') or not offer:
        raise RuntimeError(f"No verified offer: {value.get('offer_error')}")
    say(f"Current version: {current['version']}")
    say(f"New version:     {offer['version']} ({offer['bundle']['size'] / 1024**2:.1f} MiB)")
    say(f"Source:          {source} | {offer['bundle']['url']}")
    say(f"Release notes:   {offer.get('notes', '')}")
    if offer['version'] == current['version']:
        say('This version is already running. No update needed.')
        return
    say('Acceptance authorizes download, installation, a trial reboot, and a final ordinary reboot after successful health confirmation.')
    if input('Update y/n? [y/N] ').strip().lower() not in ('y', 'yes'):
        say('Update declined.')
        return
    identity = offer['offer_id']
    job = rpc('download', {'offer_id': identity, 'accept': True})
    value = wait_job(job['job_id'], 'download')
    if not value.get('download_ready') or value.get('offer', {}).get('offer_id') != identity:
        raise RuntimeError('The accepted download is not ready; refusing installation')
    say('Download verified. Installing inactive boot/root pair; keep power connected.')
    current = device(value)
    save_pending(dict(version=offer['version'], offer_id=identity, profile=PROFILE, layout=LAYOUT,
                      previous=current['slot'], target='b' if current['slot'] == 'a' else 'a'))
    try:
        job = rpc('install', {'offer_id': identity, 'accept': True})
    except Exception:
        # Keep the durable authorization if acceptance may have reached the API.
        say('Install request failed or its response was lost; inspect update.sh --status before retrying.')
        raise
    say('Trial reboot will occur automatically. After successful trial health, a second ordinary reboot completes the update.')
    try:
        value = wait_job(job['job_id'], 'install')
    except (OSError, RuntimeError):
        # A real failure remains an error; disappearance of the socket during
        # reboot is reported as unconfirmed, not as a successful installation.
        say('Monitoring ended. Reconnect after reboot and run update.sh --status.')
        raise
    if value['job']['phase'] != 'installed':
        raise RuntimeError('Unexpected install result; inspect update.sh --status')
    say('Installer returned. Awaiting trial reboot; success is confirmed only after health checks.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--remote', action='store_true')
    modes.add_argument('--local', action='store_true')
    modes.add_argument('--status', action='store_true')
    modes.add_argument('--finish-pending', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run as root')
    try:
        with open('/run/edgemap-update-wrapper.lock', 'w') as lock:
            if not args.status:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.status:
                value = rpc('status', startup=True)
                summary(value)
                say(progress(value))
                if value['job'].get('error'):
                    say(f"Job error: {value['job']['error']}")
            elif args.finish_pending:
                finish_pending()
            else:
                update('remote' if args.remote else 'local')
        return 0
    except KeyboardInterrupt:
        say('Stopped monitoring. Accepted work continues; inspect update.sh --status.')
        return 130
    except (OSError, ValueError, RuntimeError, EOFError) as error:
        print(f'update: {error}', file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
