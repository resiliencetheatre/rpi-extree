#!/usr/bin/env python3
"""Explicit partition preparation and verified transfer on a Debian workstation."""
import argparse
import fcntl
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from common import settings


def run(*args):
    return subprocess.check_output(args,text=True).strip()


def check_partition(device):
    device=Path(device).resolve()
    if not device.is_block_device(): raise ValueError('Explicit block-device partition required')
    if run('lsblk','-dnro','TYPE',str(device))!='part': raise ValueError('Supply an existing data partition, never a whole disk')
    parent=run('lsblk','-dnro','PKNAME',str(device))
    disk='/dev/'+parent
    print(run('lsblk','-o','NAME,TYPE,SIZE,MODEL,SERIAL,FSTYPE,UUID,MOUNTPOINTS',disk),flush=True)
    data=json.loads(run('lsblk','-J','-p','-o','NAME,TYPE,MOUNTPOINTS',disk))
    def scan(nodes):
        for node in nodes:
            if any(node.get('mountpoints') or []): raise ValueError('Disk has mounted or swap partitions; unmount it first')
            if node['type'] not in ('disk','part'): raise ValueError('Disk has active device-mapper/RAID holders')
            holders=Path('/sys/class/block')/Path(node['name']).name/'holders'
            if holders.exists() and any(holders.iterdir()): raise ValueError('Device has active holders')
            scan(node.get('children',[]))
    scan(data['blockdevices'])
    return device


p=argparse.ArgumentParser(); p.add_argument('settings'); p.add_argument('--device',required=True)
p.add_argument('--format',action='store_true'); p.add_argument('--destroy-partition',action='store_true')
p.add_argument('--generation',help='verified staging generation to copy')
p.add_argument('--mountpoint',default='/mnt/offline-ssd')
a=p.parse_args(); s=settings(a.settings)
if os.geteuid()!=0: p.error('Run as root on the workstation (mount/format requires it)')
if a.format != a.destroy_partition: p.error('Formatting requires BOTH --format and --destroy-partition')
if not a.format and not a.generation: p.error('Choose formatting or generation transfer')
if a.format and a.generation: p.error('Format and transfer are separate operations')
device=check_partition(a.device)
if a.format:
    subprocess.run(['mkfs.ext4','-L','offline-pxe',str(device)],check=True)
    print('Put this filesystem UUID in settings.json, then rebuild: '+run('blkid','-s','UUID','-o','value',str(device)))
else:
    if run('blkid','-s','UUID','-o','value',str(device))!=s['ssd_uuid']: p.error('Device UUID does not match settings')
    if run('blkid','-s','TYPE','-o','value',str(device))!='ext4': p.error('Data partition must be ext4')
    src=Path(a.generation).resolve()
    if src.name!=s['generation'] or not (src/'ready.sha256').is_file(): p.error('Source is not a verified generation')
    mount=Path(a.mountpoint).resolve(); mount.mkdir(parents=True,exist_ok=True)
    if any(mount.iterdir()) or os.path.ismount(mount): p.error('Mountpoint must be empty and unmounted')
    subprocess.run(['mount','-o','nosuid,nodev,noexec',str(device),str(mount)],check=True)
    try:
        with (mount/'.populate.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            target=mount/'generations'/s['generation']
            if target.exists(): p.error('Generation already exists; never overwrite a published snapshot')
            staging=mount/'.staging'/s['generation']; staging.mkdir(parents=True,exist_ok=True)
            needed=int(run('du','-sb',str(src)).split()[0])
            already=int(run('du','-sb',str(staging)).split()[0])
            if shutil.disk_usage(mount).free < max(0,needed-already)+1024**3:
                p.error('Insufficient SSD space for this generation while retaining previous generations')
            subprocess.run(['rsync','-a','--safe-links','--partial','--delete','--exclude=ready.sha256','--exclude=tftp',str(src)+'/',str(staging)+'/'],check=True)
            # Rehash destination after transfer, including all packages; no reliance on rsync size/time.
            subprocess.run(['python3',str(Path(__file__).with_name('verify-mirror.py')),a.settings,str(staging)],check=True)
            target.parent.mkdir(exist_ok=True)
            os.rename(staging,target); os.sync()
            print(f'Copied {target.name}. On Pi run offline-activate {target.name} --no-active-installers')
    finally:
        subprocess.run(['umount',str(mount)],check=True)
