#!/usr/bin/env python3
"""Build a signed SWU from the factory build's slot images."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from common import metadata, description, archive_write

p = argparse.ArgumentParser()
p.add_argument('--images', type=Path, required=True)
p.add_argument('--key', type=Path, required=True)
p.add_argument('--version', required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
images = {n: (a.images / n).read_bytes() for n in ('boot-a.vfat', 'boot-b.vfat', 'rootfs.ext4')}
meta = metadata(a.version, images)
assert (a.images / 'release-version').read_text().strip() == a.version, 'rootfs release mismatch'
release = json.dumps(meta, sort_keys=True).encode()
desc = description(meta)
def sign(data):
    with tempfile.TemporaryDirectory() as d:
        source = Path(d) / 'input'
        source.write_bytes(data)
        return subprocess.check_output(['openssl', 'dgst', '-sha256', '-sign', str(a.key), str(source)])
archive_write(a.output, [('sw-description', desc), ('sw-description.sig', sign(desc)),
                         ('release.json', release), ('release.sig', sign(release)), *images.items()])
