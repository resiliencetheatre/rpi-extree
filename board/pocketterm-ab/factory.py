#!/usr/bin/env python3
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from common import SIZES, UUIDS, PROFILE, LAYOUT

board = Path(__file__).resolve().parent
images = Path(os.environ['BINARIES_DIR'])
host = Path(os.environ['HOST_DIR'])
version = (images / 'release-version').read_text().strip()
fixed_firmware = images / 'rpi-tryboot-firmware'
assert (fixed_firmware / 'revision').read_text().strip() == 'ab5c7f86283ceb58b7adb269cae1d16092a31bf6'
with tempfile.TemporaryDirectory(dir=os.environ['BUILD_DIR']) as work:
    work = Path(work)
    firmware = images / 'rpi-firmware'
    chunks = []
    (work / 'empty').mkdir()
    def fat(name, stage, size):
        files = ' '.join('file "' + p.name + '" { image = "' + str(p) + '" }' for p in sorted(stage.iterdir()))
        return f'image {name}.vfat {{ vfat {{ {files} }} size = {size}M }}' 
    for slot, rootindex in [('a', 4), ('b', 5)]:
        stage = work / slot
        shutil.copytree(firmware, stage)
        for name in ('start4.elf', 'fixup4.dat'):
            shutil.copy2(fixed_firmware / name, stage / name)
        shutil.copy2(images / 'Image', stage / 'Image')
        shutil.copy2(images / 'bcm2711-rpi-4-b.dtb', stage)
        cmd = (board.parent / 'raspberrypi4-64/cmdline_videoterm.txt').read_text().split()
        cmd = [x for x in cmd if not x.startswith('root=') and x not in ('rw', 'ro')]
        (stage / 'cmdline.txt').write_text(' '.join([f'root=PARTUUID={UUIDS[rootindex-1]}', 'rw', *cmd]) + '\n')
        chunks.append(fat('boot-' + slot, stage, 128))
    selector = work / 'selector'
    selector.mkdir()
    for name in ('start4.elf', 'fixup4.dat', 'config.txt'):
        source = firmware if name == 'config.txt' else fixed_firmware
        shutil.copy2(source / name, selector / name)
    # start.elf makes this discoverable by the Pi 4 firmware's default FAT search.
    shutil.copy2(fixed_firmware / 'start4.elf', selector / 'start.elf')
    (selector / 'autoboot.txt').write_text('[all]\ntryboot_a_b=1\nboot_partition=2\n[tryboot]\nboot_partition=3\n')
    chunks.append(fat('selector', selector, 32))
    data_stage = work / 'data'
    data_stage.mkdir()
    (data_stage / '.pocketterm-factory-grow-v1').write_text(f'{PROFILE} {LAYOUT}\n')
    chunks.append(f'image data.ext4 {{ mountpoint = "/data" ext4 {{ label = "ab-data" }} size = 4096M }}')
    shutil.copytree(data_stage, work / 'empty/data')
    chunks.append('image sdcard-ab.img { hdimage { partition-table-type = "gpt" }')
    names = ['selector', 'boot-a', 'boot-b', 'root-a', 'root-b', 'data']
    payloads = ['selector.vfat', 'boot-a.vfat', 'boot-b.vfat', 'rootfs.ext4', 'rootfs.ext4', 'data.ext4']
    for i, (name, payload, size, uuid) in enumerate(zip(names, payloads, SIZES, UUIDS)):
        assert not (images / payload).exists() or (images / payload).stat().st_size <= size * 1024**2
        kind = 'U' if i < 3 else 'L'
        chunks.append(f'partition {name} {{ image = "{payload}" size = {size}M partition-type-uuid = {kind} partition-uuid = "{uuid}"' + (' offset = 1M' if i == 0 else '') + ' }')
    chunks.append('}')
    cfg = images / 'genimage-ab.cfg'
    cfg.write_text('\n'.join(chunks))
    subprocess.run([str(host / 'bin/genimage'), '--rootpath', str(work / 'empty'),
                    '--inputpath', str(images), '--outputpath', str(images),
                    '--tmppath', str(work / 'genimage'), '--config', str(cfg)], check=True)
