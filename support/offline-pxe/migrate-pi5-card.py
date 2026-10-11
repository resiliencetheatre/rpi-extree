#!/usr/bin/env python3
"""Desk-only, explicit partition-image replacement; never writes the disk node."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def table(path):
    return json.loads(run('sfdisk', '--json', str(path)))['partitiontable']


def check_geometry(card, image):
    for t in (card, image):
        if t['label'] != 'dos' or t.get('sectorsize', 512) != 512 or t.get('unit', 'sectors') != 'sectors':
            raise ValueError('Expected DOS partition table with 512-byte sectors')
    cp, ip = card['partitions'], image['partitions']
    if len(cp) != 3 or len(ip) != 2:
        raise ValueError('Expected exactly three card partitions and two image partitions')
    if cp[0]['type'] != 'c' or cp[1]['type'] != '83':
        raise ValueError('Expected FAT32 LBA boot and Linux rootfs partitions')
    for n, (actual, expected, size) in enumerate(zip(cp, ip, (128*1024**2, 512*1024**2)), 1):
        for key in ('start', 'size', 'type', 'bootable'):
            if actual.get(key) != expected.get(key):
                raise ValueError(f'Partition {n} {key} differs from the Pi 5 image')
        if actual['size'] * 512 != size:
            raise ValueError(f'Partition {n} is not the expected fixed size')
    if cp[0]['start'] < 1 or cp[0]['start'] + cp[0]['size'] > cp[1]['start']:
        raise ValueError('Invalid boot/root partition geometry')
    if cp[2]['type'] != '83' or cp[2]['start'] < cp[1]['start'] + cp[1]['size']:
        raise ValueError('Mirror partition overlaps rootfs or is not a Linux partition')
    if cp[2]['size'] <= 0:
        raise ValueError('Empty mirror partition')


def digest_bytes(path, size):
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        remaining = size
        while remaining:
            data = f.read(min(4*1024**2, remaining))
            if not data:
                raise ValueError(f'Short read: {path}')
            digest.update(data)
            remaining -= len(data)
    return digest.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--device', required=True, type=Path, help='Explicit whole microSD device, e.g. /dev/sdc')
    p.add_argument('--images', required=True, type=Path, help='Pi 5 output/images directory')
    p.add_argument('--mirror-uuid', required=True)
    p.add_argument('--backup-dir', type=Path, help='New directory on desk; required with --write')
    p.add_argument('--write', action='store_true', help='Replace ONLY card partitions 1 and 2 after backing them up')
    a = p.parse_args()
    if os.geteuid() != 0:
        p.error('Run with sudo on desk to inspect block devices')
    disk = a.device.resolve()
    if not disk.is_block_device() or run('lsblk', '-dnro', 'TYPE', str(disk)) != 'disk':
        p.error('Supply an explicit whole card block device')
    print(run('lsblk', '-o', 'NAME,TYPE,SIZE,MODEL,SERIAL,FSTYPE,UUID,MOUNTPOINTS', str(disk)), flush=True)
    nodes = json.loads(run('lsblk', '-J', '-p', '-o', 'NAME,TYPE,MOUNTPOINTS', str(disk)))['blockdevices']

    def unmounted(nodes):
        for node in nodes:
            if any(node.get('mountpoints') or []) or node['type'] not in ('disk', 'part'):
                raise ValueError('Unmount every card partition first; swap/holders are forbidden')
            holders = Path('/sys/class/block') / Path(node['name']).name / 'holders'
            if holders.exists() and any(holders.iterdir()):
                raise ValueError('Device has active holders')
            unmounted(node.get('children', []))

    unmounted(nodes)
    images = a.images.resolve()
    manifest = json.loads((images/'offline-pxe-build.json').read_text())
    if manifest['defconfig'] != 'rpi5_offline_pxe_defconfig':
        p.error('Artifacts are not from the Pi 5 offline PXE target')
    card = table(disk)
    check_geometry(card, table(images/'sdcard.img'))
    last = card['partitions'][2]
    if (last['start'] + last['size']) * 512 > int(run('blockdev', '--getsize64', str(disk))):
        p.error('Mirror partition extends beyond the card')
    parts = [Path(entry['node']).resolve() for entry in card['partitions']]
    for part, entry in zip(parts, card['partitions']):
        if not part.is_block_device() or run('lsblk', '-dnro', 'PKNAME', str(part)) != disk.name:
            p.error('Partition does not belong to selected card')
        if int(run('blockdev', '--getsize64', str(part))) != entry['size'] * 512:
            p.error('Kernel partition size differs from on-disk table; reinsert card')
        sys_start = Path('/sys/class/block') / part.name / 'start'
        if int(sys_start.read_text()) != entry['start']:
            p.error('Kernel partition offset differs from on-disk table; reinsert card')
    if run('blkid', '-s', 'UUID', '-o', 'value', str(parts[2])) != a.mirror_uuid:
        p.error('Third partition UUID does not match the mirror')
    if run('blkid', '-s', 'TYPE', '-o', 'value', str(parts[2])) != 'ext4':
        p.error('Mirror partition is not ext4')
    artifacts = [images/'boot.vfat', images/'rootfs.ext4']
    for source, entry in zip(artifacts, card['partitions']):
        if source.stat().st_size != entry['size'] * 512:
            p.error(f'{source.name} size does not exactly match destination partition')
    # Ensure partition artifacts match the image whose geometry was checked.
    hashes = [digest_bytes(source, source.stat().st_size) for source in artifacts]
    with (images/'sdcard.img').open('rb') as f:
        for entry, expected in zip(card['partitions'], hashes):
            f.seek(entry['start'] * 512)
            h = hashlib.sha256()
            remaining = entry['size'] * 512
            while remaining:
                data = f.read(min(4*1024**2, remaining))
                if not data:
                    p.error('Truncated sdcard.img')
                h.update(data)
                remaining -= len(data)
            if h.hexdigest() != expected:
                p.error('Partition artifacts differ from sdcard.img; use one completed build')
    print('PASS: image/card geometry matches: boot 128 MiB, rootfs 512 MiB.', flush=True)
    print(f'Preserving partition table and mirror {parts[2]} UUID={a.mirror_uuid}', flush=True)
    if not a.write:
        print('Read-only check complete. No card data written. Add --write --backup-dir NEW_DIRECTORY to migrate.')
        return
    if a.backup_dir is None:
        p.error('--write requires --backup-dir')
    backup = a.backup_dir.resolve()
    if backup.exists() or not backup.parent.is_dir():
        p.error('Backup must be a new directory with an existing parent on desk')
    if shutil.disk_usage(backup.parent).free < 650*1024**2:
        p.error('Need at least 650 MiB free for boot/root backups')
    # Repeat after source hashing to catch desktop automounts before any writes.
    unmounted(json.loads(run('lsblk', '-J', '-p', '-o', 'NAME,TYPE,MOUNTPOINTS', str(disk)))['blockdevices'])
    if table(disk) != card:
        p.error('Card partition table changed during preflight')
    backup.mkdir(mode=0o700)
    (backup/'partition-table.json').write_text(json.dumps(card, indent=2)+'\n')
    (backup/'partition-table.sfdisk').write_text(run('sfdisk', '--dump', str(disk))+'\n')
    with disk.open('rb') as f:
        mbr = f.read(512)
    (backup/'mbr.bin').write_bytes(mbr)
    for n, part in enumerate(parts[:2], 1):
        dest = backup/f'partition{n}.img'
        subprocess.run(['dd', f'if={part}', f'of={dest}', 'bs=4M', 'conv=fsync', 'status=progress'], check=True)
        if dest.stat().st_size != card['partitions'][n-1]['size'] * 512:
            raise ValueError('Backup size is incorrect; no new image written')
        if digest_bytes(part, dest.stat().st_size) != digest_bytes(dest, dest.stat().st_size):
            raise ValueError('Backup verification failed; no new image written')
    print(f'Verified rollback images saved in {backup}', flush=True)
    os.sync()
    for source, part, expected in zip(artifacts, parts, hashes):
        print(f'Replacing {part} with {source.name}', flush=True)
        subprocess.run(['dd', f'if={source}', f'of={part}', 'bs=4M', 'conv=fsync', 'status=progress'], check=True)
        if digest_bytes(part, source.stat().st_size) != expected:
            raise ValueError(f'Read-back verification failed for {part}; retain rollback images')
    with disk.open('rb') as f:
        if f.read(512) != mbr:
            raise ValueError('Unexpected MBR change')
    if table(disk) != card or run('blkid', '-s', 'UUID', '-o', 'value', str(parts[2])) != a.mirror_uuid:
        raise ValueError('Unexpected partition table or mirror UUID change')
    os.sync()
    print('PASS: boot/root read-back verified; MBR, partition geometry and mirror UUID unchanged.')
    print('Rootfs customizations were replaced. On Pi 5, configure the existing third partition (never create/format), set UTC and enroll RTC.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f'Migration stopped: {error}')
