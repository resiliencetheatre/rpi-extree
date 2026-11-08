#!/usr/bin/env python3
"""Publish metadata for an already built/signed bundle. Does not deploy it."""
import argparse
import base64
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import PROFILE, LAYOUT
from remote_release import canonical, verify_bundle, verify_offer, url_origin


def publish(bundle, private_key, url, sequence, expires, notes, output, allow_http=False):
    # Validate URL policy without fetching the release server.
    url_origin(url, allow_http)
    with tempfile.TemporaryDirectory(prefix='publish-release-') as directory:
        directory = Path(directory)
        public = directory / 'public.pem'
        subprocess.run(['openssl', 'pkey', '-in', str(private_key), '-pubout', '-out', str(public)], check=True)
        # Read only the small signed release record first; full binding is checked below.
        from common import archive_read
        entries = archive_read(bundle, directory)
        from remote_release import loads
        version = loads(entries['release.json'])['version']
        # Release the first payload staging before doing the complete validation pass.
        for value in entries.values():
            if isinstance(value, Path):
                value.unlink()
        verify_bundle(bundle, version, public)
        with bundle.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        signed = dict(schema=1, profile=PROFILE, layout=LAYOUT, version=version,
                      sequence=sequence, expires=expires, notes=notes,
                      bundle=dict(url=url, size=bundle.stat().st_size, sha256=digest))
        source = directory / 'signed.json'
        source.write_bytes(canonical(signed))
        signature = subprocess.check_output(['openssl', 'dgst', '-sha256', '-sign', str(private_key), str(source)])
        envelope = dict(signed=signed, signature=base64.b64encode(signature).decode())
        verify_offer(envelope, dict(manifest_url=url, public_key=str(public), allow_http_loopback=allow_http))
        output.write_bytes(canonical(envelope) + b'\n')
    return envelope


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--key', type=Path, required=True)
    parser.add_argument('--url', required=True, help='Final bundle URL on the metadata origin')
    parser.add_argument('--sequence', type=int, required=True, help='Monotonically increasing channel sequence')
    parser.add_argument('--expires-in-days', type=int, default=7)
    parser.add_argument('--notes', default='')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-http-loopback', action='store_true')
    args = parser.parse_args()
    if args.expires_in_days <= 0:
        parser.error('--expires-in-days must be positive')
    publish(args.bundle, args.key, args.url, args.sequence,
            int(time.time()) + args.expires_in_days * 86400, args.notes, args.output, args.allow_http_loopback)


if __name__ == '__main__':
    main()
