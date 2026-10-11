#!/usr/bin/env python3
"""Stage an authenticated diagnostic bundle in this board's rootfs overlay."""
import argparse
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from common import digest, netboot_uefi_links

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('bundle')
p.add_argument('--sha256', required=True, help='trusted hash printed by prepare-netboot-test.py')
a = p.parse_args()
if digest(a.bundle) != a.sha256:
    p.error('Bundle SHA256 mismatch')
dest = Path(__file__).resolve().parents[2]/'board/rpi4-offline-pxe/rootfs-overlay/usr/share/offline-pxe/netboot-test'
if dest.exists():
    p.error('Overlay payload already exists; move it aside before staging a replacement')
with tempfile.TemporaryDirectory(prefix='netboot-overlay-') as tmp:
    with tarfile.open(a.bundle) as archive:
        archive.extractall(tmp, filter='data')
    source = Path(tmp)/'netboot-test'
    for file in source.rglob('*'):
        if file.is_symlink() and not file.resolve().is_relative_to(source.resolve()):
            p.error('Payload contains an escaping symlink')
    subprocess.run(['sha256sum', '--quiet', '-c', 'files.sha256'], cwd=source, check=True)
    netboot_uefi_links(source/'tftp')
    shutil.copytree(source, dest, symlinks=True)
print('Staged '+str(dest))
