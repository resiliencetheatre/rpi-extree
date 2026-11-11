#!/usr/bin/env python3
"""Host-only tiny signed release server. Uses its own temporary trust domain."""
import argparse
import functools
import http.server
import json
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import metadata, description, archive_write
from publish import publish


def create(root, port):
    root.mkdir(parents=True, exist_ok=True)
    www, secrets = root / 'www', root / 'secrets'
    www.mkdir(exist_ok=True)
    secrets.mkdir(mode=0o700, exist_ok=True)
    private, public = secrets / 'private.pem', root / 'public.pem'
    if not private.exists():
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048', '-out', str(private)],
                       check=True, stderr=subprocess.DEVNULL)
    subprocess.run(['openssl', 'pkey', '-in', str(private), '-pubout', '-out', str(public)], check=True)
    images = {name: (name + ' lab-only fixture; NOT a real filesystem\n').encode()
              for name in ('boot-a.vfat', 'boot-b.vfat', 'rootfs.ext4')}
    release = json.dumps(metadata('lab-1', images), sort_keys=True).encode()
    desc = description(metadata('lab-1', images))
    def sign(data):
        source = secrets / 'signing-input'
        source.write_bytes(data)
        return subprocess.check_output(['openssl', 'dgst', '-sha256', '-sign', str(private), str(source)])
    bundle = www / 'lab-1.swu'
    archive_write(bundle, [('sw-description', desc), ('sw-description.sig', sign(desc)),
                          ('release.json', release), ('release.sig', sign(release)), *images.items()])
    publish(bundle, private, f'http://127.0.0.1:{port}/lab-1.swu', 1,
            int(time.time()) + 86400, 'Lab fixture only; installation is disabled', www / 'latest.json', True)
    config = dict(manifest_url=f'http://127.0.0.1:{port}/latest.json', public_key=str(public.resolve()),
                  data_dir=str((root / 'client-data').resolve()), allow_http_loopback=True)
    (root / 'lab-config.json').write_text(json.dumps(config, indent=2) + '\n')
    return www


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True, help='A disposable host directory')
    parser.add_argument('--port', type=int, default=9080)
    args = parser.parse_args()
    www = create(args.directory.resolve(), args.port)
    print('Fixture serves only', www, flush=True)
    print('Do not install fixture bundles on hardware. Private key is outside the served directory.', flush=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(www))
    with http.server.ThreadingHTTPServer(('127.0.0.1', args.port), handler) as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
