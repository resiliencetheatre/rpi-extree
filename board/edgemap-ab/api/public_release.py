#!/usr/bin/env python3
"""Ordered rclone publication; credentials remain in the operator's rclone config."""
import argparse
from datetime import datetime
import hashlib
import json
from functools import partial
from pathlib import Path
import re
import subprocess
import sys
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from remote_release import Fetcher, loads, url_origin, verify_offer


def log(message):
    print(f"[{datetime.now().astimezone().isoformat(timespec='seconds')}] publish: {message}",
          file=sys.stderr, flush=True)


def rclone(*args):
    action = ' '.join(map(str, args[:3]))
    log(f'rclone starting: {action}')
    command = ['rclone', *map(str, args)]
    if args[0] in ('copyto', 'moveto'):
        # rclone writes periodic statistics to inherited stderr; stdout remains
        # captured for callers that parse JSON or retrieve signed metadata.
        command += ['--stats', '10s', '--stats-log-level', 'NOTICE']
    result = subprocess.check_output(command, timeout=3600)
    log(f'rclone completed: {action}')
    return result


def inspect(remote, base, version, sequence, public_key, *, backend=None, fetcher=None):
    backend = backend or rclone
    fetcher = fetcher or Fetcher
    if not re.fullmatch(r'[A-Za-z0-9_-]+:[^\r\n]+', remote):
        raise ValueError('Expected a named rclone remote and directory')
    url_origin(base)
    features = json.loads(backend('backend', 'features', remote))
    if not features.get('Features', {}).get('Move'):
        raise ValueError('Remote must support server-side file moves for metadata publication')
    entries = json.loads(backend('lsjson', remote, '--max-depth', '1'))
    names = {entry['Name'] for entry in entries}
    if f'{version}.swu' in names or f'{version}.SHA256SUMS' in names:
        raise ValueError('Remote release already exists; use a new version')
    previous = backend('cat', remote + '/latest.json') if 'latest.json' in names else b''
    if previous:
        _, signed = verify_offer(loads(previous), dict(manifest_url=base+'/latest.json',
                                  public_key=str(public_key)), now=0)
        if sequence <= signed['sequence']:
            raise ValueError('Sequence must exceed published sequence')
        # Detect incorrect web-root mapping, redirects, stale caching and TLS errors.
        with fetcher(base+'/latest.json').open(base+'/latest.json') as response:
            if response.read(65537) != previous:
                raise ValueError('Public latest.json differs from rclone destination')
    return previous


def upload(remote, base, version, sequence, public_key, snapshot, release, *, backend=None, fetcher=None):
    backend = backend or rclone
    fetcher = fetcher or Fetcher
    log('Checking remote publication state before upload')
    previous = inspect(remote, base, version, sequence, public_key, backend=backend, fetcher=fetcher)
    if previous != snapshot.read_bytes():
        raise ValueError('Published offer changed during build; refusing publication')
    envelope = loads((release/'latest.json').read_bytes())
    _, signed = verify_offer(envelope, dict(manifest_url=base+'/latest.json', public_key=str(public_key)))
    expected_url = f'{base}/{version}.swu'
    if signed['version'] != version or signed['sequence'] != sequence or signed['bundle']['url'] != expected_url:
        raise ValueError('Release metadata does not match requested publication')
    bundle = release/f'{version}.swu'
    with bundle.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    if digest != signed['bundle']['sha256'] or bundle.stat().st_size != signed['bundle']['size']:
        raise ValueError('Local bundle changed after verification')
    log(f'Uploading {version}.swu ({bundle.stat().st_size:,} bytes)')
    if backend is rclone:
        log('rclone transfer statistics every 10 seconds')
    backend('copyto', bundle, remote+f'/{version}.swu', '--immutable')
    log('Uploading release checksum')
    backend('copyto', release/'SHA256SUMS', remote+f'/{version}.SHA256SUMS', '--immutable')
    # Check exactly what devices will receive, without following redirects or
    # allocating an entire SWU in memory. Metadata remains untouched on failure.
    log('Verifying public bundle over HTTPS; downloading and hashing the entire bundle')
    received, digest = 0, hashlib.sha256()
    with fetcher(base+'/latest.json').open(expected_url) as response:
        while chunk := response.read(1024**2):
            received += len(chunk)
            if received > signed['bundle']['size']:
                raise ValueError('Public bundle exceeds signed size')
            digest.update(chunk)
    if received != signed['bundle']['size'] or digest.hexdigest() != signed['bundle']['sha256']:
        raise ValueError('Public bundle size/hash mismatch; previous offer preserved')
    log('Public bundle verified; rechecking offer before metadata publication')
    current = backend('cat', remote+'/latest.json') if previous else b''
    if not previous:
        entries = json.loads(backend('lsjson', remote, '--max-depth', '1'))
        if any(entry['Name'] == 'latest.json' for entry in entries):
            raise ValueError('Another publisher created latest.json')
    if current != previous:
        raise ValueError('Another publisher changed latest.json')
    temporary = remote+'/.latest-'+uuid.uuid4().hex+'.json'
    log('Uploading signed metadata and activating latest.json')
    backend('copyto', release/'latest.json', temporary, '--immutable')
    backend('moveto', temporary, remote+'/latest.json', '--ignore-times')
    log('Verifying published latest.json over HTTPS')
    with fetcher(base+'/latest.json').open(base+'/latest.json') as response:
        if response.read(65537) != (release/'latest.json').read_bytes():
            raise ValueError('Metadata was published, but HTTPS verification failed; inspect caching/web-root mapping')

    log(f'Publication verified: {base}/{version}.swu')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preflight', 'upload'])
    parser.add_argument('--remote')
    parser.add_argument('--local-host', type=Path)
    parser.add_argument('--ca-file', type=Path)
    parser.add_argument('--base', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--sequence', required=True, type=int)
    parser.add_argument('--public-key', required=True, type=Path)
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--release', type=Path)
    args = parser.parse_args()
    if not args.public_key.is_absolute() or not args.snapshot.is_absolute() or (args.release is not None and not args.release.is_absolute()):
        parser.error('Use absolute key, snapshot and release paths')
    if bool(args.remote) == bool(args.local_host):
        parser.error('Select exactly one of --remote or --local-host')
    backend, fetcher = None, None
    if args.local_host:
        from local_release import LocalBackend
        backend = LocalBackend(args.local_host)
        args.remote = 'local:root'
        ca = args.ca_file or args.local_host / 'tls/ca.pem'
        if not ca.is_absolute():
            parser.error('CA path must be absolute')
        fetcher = partial(Fetcher, ca_file=str(ca))
        log('Checking local Python HTTPS server (keep it running during publication)')
        with fetcher(args.base+'/latest.json').open(args.base+'/health.json') as response:
            if loads(response.read(65537)).get('service') != 'edgemap-update-test-host':
                raise ValueError('Unexpected local HTTPS host')
    elif args.ca_file:
        parser.error('--ca-file is only supported with --local-host')
    if args.action == 'preflight':
        args.snapshot.write_bytes(inspect(args.remote, args.base, args.version, args.sequence, args.public_key,
                                          backend=backend, fetcher=fetcher))
    else:
        if args.release is None:
            parser.error('--release required for upload')
        upload(args.remote, args.base, args.version, args.sequence, args.public_key, args.snapshot, args.release,
               backend=backend, fetcher=fetcher)


if __name__ == '__main__':
    main()
