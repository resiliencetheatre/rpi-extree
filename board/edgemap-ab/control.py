#!/usr/bin/env python3
"""Root-only, local installation and replay-safe trial confirmation."""
import fcntl
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
from common import PROFILE, LAYOUT, SIZES, UUIDS, archive_read, description, metadata

DATA = Path('/data/ab')
SELECTOR = Path('/selector/autoboot.txt')
PERSISTENT_PATHS = ('/etc/default', '/etc/ssh', '/var/lib', '/etc/apache2',
                    '/opt/data', '/opt/situation/maps')
PERSISTENT_FILES = ()

def run(*args, **kw):
    return subprocess.run(args, check=True, **kw)

def atomic(path, data):
    path = Path(path)
    stage = path.with_name(path.name + '.new')
    with stage.open('wb') as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
    os.replace(stage, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    assert path.read_bytes() == data

def record(value):
    value = dict(value, profile=PROFILE, layout=LAYOUT, timestamp=int(time.time()))
    atomic(DATA / 'state.json', json.dumps(value, sort_keys=True).encode())
    with (DATA / 'events.jsonl').open('a') as out:
        out.write(json.dumps(value, sort_keys=True) + '\n')
        out.flush()
        os.fsync(out.fileno())

def tree():
    return json.loads(subprocess.check_output(['lsblk', '--json', '--bytes', '--paths',
        '--output', 'NAME,TYPE,PKNAME,PARTUUID,SIZE,MOUNTPOINTS,PARTN,TRAN']))['blockdevices']

def check_transport(nodes, parent):
    disks = [n for n in nodes if n['name'] == parent and n['type'] == 'disk']
    assert len(disks) == 1, 'ambiguous parent disk'
    disk = disks[0]
    if disk.get('tran') == 'usb':
        # Device letters change with enumeration. Use the identified parent disk.
        return 'usb'
    assert Path(parent).name.startswith('mmcblk'), 'unsupported storage transport'
    kind = (Path('/sys/class/block') / Path(parent).name / 'device/type').read_text().strip()
    assert kind == 'SD', 'native storage must be SD, not eMMC'
    return 'sd'

def inspect():
    nodes = []
    def walk(items):
        for item in items:
            nodes.append(item)
            walk(item.get('children', []))
    walk(tree())
    parts = []
    for uuid in UUIDS:
        hits = [n for n in nodes if (n.get('partuuid') or '').lower() == uuid]
        assert len(hits) == 1, 'missing or cloned partition identity'
        parts.append(hits[0])
    disks = {p['pkname'] for p in parts}
    assert len(disks) == 1 and None not in disks
    transport = check_transport(nodes, next(iter(disks)))
    for i, p in enumerate(parts):
        assert int(p['partn']) == i + 1
        minimum = SIZES[i] * 1024**2
        assert int(p['size']) >= minimum if i == 5 else int(p['size']) == minimum
    roots = [i for i in (3, 4) if '/' in (parts[i]['mountpoints'] or [])]
    assert len(roots) == 1, 'running root is not a known slot'
    slot = 'a' if roots[0] == 3 else 'b'
    def dt(name):
        raw = (Path('/proc/device-tree/chosen/bootloader') / name).read_bytes()
        assert len(raw) == 4
        return struct.unpack('>I', raw)[0]
    assert dt('partition') == (2 if slot == 'a' else 3), 'firmware/root mismatch'
    boot_mode = dt('boot-mode')
    assert boot_mode in ((4, 5) if transport == 'usb' else (1,)), 'firmware/storage transport mismatch'
    trial = dt('tryboot')
    assert trial in (0, 1)
    return parts, slot, bool(trial)

def mount_table():
    def unescape(value):
        return re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), value)
    records = []
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        fields = line.split()
        separator = fields.index('-')
        records.append(dict(device=fields[2], root=unescape(fields[3]),
                            target=unescape(fields[4]), kind=fields[separator + 1]))
    return records

def mount(part, where, kind):
    device_id = os.stat(part['name']).st_rdev
    device = f'{os.major(device_id)}:{os.minor(device_id)}'
    expected = {where: '/'}
    if where == '/data':
        expected.update({path: '/persist' + path for path in PERSISTENT_PATHS})

    def validate(records):
        for entry in records:
            if entry['device'] == device or entry['target'] in expected:
                assert (entry['device'] == device and entry['kind'] == kind
                        and entry['target'] in expected
                        and entry['root'] == expected[entry['target']]), 'unexpected mount or bind source'
        # Refuse stacked mounts, even when their sources happen to match.
        for target in expected:
            assert sum(e['target'] == target for e in records) <= 1, 'stacked mounts'

    records = mount_table()
    validate(records)
    if not any(e['target'] == where for e in records):
        run('mount', '-t', kind, part['name'], where)
        records = mount_table()
        validate(records)
    assert any(e['target'] == where for e in records), 'mount did not appear'

def selector(slot):
    normal, trial = (2, 3) if slot == 'a' else (3, 2)
    return f'[all]\ntryboot_a_b=1\nboot_partition={normal}\n[tryboot]\nboot_partition={trial}\n'.encode()

def verify(data, sig, folder, stem):
    p = Path(folder)
    (p / stem).write_bytes(data)
    (p / (stem + '.sig')).write_bytes(sig)
    run('openssl', 'dgst', '-sha256', '-verify', '/etc/edgemap-ab/public.pem',
        '-signature', str(p / (stem + '.sig')), str(p / stem), stdout=subprocess.DEVNULL)

def install(bundle, parts, slot, trial, state):
    assert not trial and state.get('phase') not in ('pending', 'trial', 'committing'), 'trial outstanding'
    assert SELECTOR.read_bytes() == selector(slot), 'selector disagrees with running slot'
    target = 'b' if slot == 'a' else 'a'
    boot, root = (parts[2], parts[4]) if target == 'b' else (parts[1], parts[3])
    assert not any(boot['mountpoints'] or []) and not any(root['mountpoints'] or []), 'target mounted'
    # Snapshot the input before authentication. Never pass a mutable operator path to SWUpdate.
    assert shutil.disk_usage('/data').free > 8200 * 1024**2, 'insufficient Data staging space'
    with tempfile.TemporaryDirectory(prefix='ab-', dir='/data') as work:
        entries = archive_read(Path(bundle), work)
        verify(entries['release.json'], entries['release.sig'], work, 'release')
        meta = json.loads(entries['release.json'])
        images = {n: entries[n] for n in ('boot-a.vfat', 'boot-b.vfat', 'rootfs.ext4')}
        assert meta == metadata(meta['version'], images), 'payload metadata mismatch'
        assert entries['sw-description'] == description(meta), 'unsupported manifest'
        verify(entries['sw-description'], entries['sw-description.sig'], work, 'description')
        from common import archive_write
        snapshot = Path(work) / 'bundle.swu'
        archive_write(snapshot, list(entries.items()))
        # SWUpdate uses the snapshot; discard staging before its own extraction.
        for image in images.values():
            image.unlink()
        aliases = [(Path('/dev/ab-boot'), boot), (Path('/dev/ab-root'), root)]
        for link, _ in aliases:
            assert not link.exists() and not link.is_symlink(), 'device alias already present'
        created = []
        try:
            for link, part in aliases:
                link.symlink_to(part['name'])
                created.append(link)
            record(dict(phase='installing', previous=slot, target=target, version=meta['version']))
            latest, current, trying = inspect()
            assert current == slot and not trying
            for index in ((2, 4) if target == 'b' else (1, 3)):
                assert not any(latest[index]['mountpoints'] or [])
            run('/usr/bin/swupdate', '-i', str(snapshot), '-k', '/etc/edgemap-ab/public.pem',
                '-e', 'stable,' + target, '-H', PROFILE + ':' + PROFILE,
                env=dict(os.environ, TMPDIR=work))
            for part in (boot, root):
                fd = os.open(part['name'], os.O_RDWR)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            # Independently read back both payloads before activation.
            for part, name in [(boot, f'boot-{target}.vfat'), (root, 'rootfs.ext4')]:
                with open(part['name'], 'rb', buffering=0) as src:
                    digest = hashlib.sha256()
                    remaining = meta['payloads'][name]['size']
                    while remaining:
                        chunk = src.read(min(1024**2, remaining))
                        assert chunk
                        digest.update(chunk)
                        remaining -= len(chunk)
                    assert digest.hexdigest() == meta['payloads'][name]['sha256']
            os.sync()
            record(dict(phase='pending', previous=slot, target=target, version=meta['version']))
        except Exception:
            record(dict(phase='failed', previous=slot, target=target, version=meta['version']))
            raise
        finally:
            for link in created:
                link.unlink(missing_ok=True)
    run('systemctl', 'reboot', '--reboot-argument=0 tryboot')

def boot(slot, trial, state):
    version = Path('/etc/edgemap-ab/version').read_text().strip()
    if not trial:
        if state.get('phase') == 'installing':
            record(dict(state, phase='failed'))
        if state.get('phase') in ('pending', 'trial', 'committing'):
            if slot == state['target'] and SELECTOR.read_bytes() == selector(slot):
                assert state['phase'] == 'committing', 'normal candidate without health authorization'
                assert version == state['version']
                record(dict(state, phase='committed'))
            else:
                assert slot == state['previous'] and SELECTOR.read_bytes() == selector(slot)
                record(dict(state, phase='fallback'))
        return
    assert state.get('phase') in ('pending', 'trial', 'committing')
    assert slot == state['target'] and version == state['version']
    expected = [selector(state['previous'])]
    if state['phase'] == 'committing':
        expected.append(selector(slot))
    assert SELECTOR.read_bytes() in expected
    record(dict(state, phase='trial'))
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        from health import ready
        if ready():
            break
        time.sleep(1)
    else:
        raise RuntimeError('EdgeMap local HTTP readiness deadline expired')
    record(dict(state, phase='committing'))
    atomic(SELECTOR, selector(slot))
    os.sync()
    record(dict(state, phase='committed'))

def prepare_persistence():
    for source in (*PERSISTENT_PATHS, *PERSISTENT_FILES):
        target = Path(source)
        saved = Path('/data/persist') / source.lstrip('/')
        if not saved.exists():
            assert not target.is_symlink(), 'unexpected initial persistence symlink'
            saved.parent.mkdir(parents=True, exist_ok=True)
            stage = saved.with_name(saved.name + '.new')
            if stage.exists():
                shutil.rmtree(stage) if stage.is_dir() else stage.unlink()
            if source in PERSISTENT_PATHS:
                shutil.copytree(target, stage, symlinks=True)
            else:
                shutil.copy2(target, stage)
            os.sync()
            os.rename(stage, saved)
            os.sync()
        assert not saved.is_symlink(), 'unexpected persistent backing symlink'
        if source in PERSISTENT_PATHS:
            assert saved.is_dir()
            if not os.path.ismount(target):
                run('mount', '--bind', str(saved), str(target))
        else:
            assert saved.is_file()
            # Symlinks keep readers on the current inode after an atomic settings
            # replacement. Writers must replace the backing path (see README).
            if target.is_symlink():
                assert target.readlink() == saved, 'unexpected settings symlink'
            else:
                target.unlink(missing_ok=True)
                target.symlink_to(saved)
    os.sync()


def main():
    assert os.geteuid() == 0
    if sys.argv[1:] == ['failure-reset']:
        trial = Path('/proc/device-tree/chosen/bootloader/tryboot').read_bytes()
        assert len(trial) == 4, 'invalid firmware tryboot property'
        flag = struct.unpack('>I', trial)[0]
        assert flag in (0, 1), 'invalid firmware tryboot value'
        if flag == 1:
            run('systemctl', 'reboot')
        else:
            print('A/B service failed on a normal boot; leaving console available.', file=sys.stderr)
        return
    Path('/run/edgemap-ab').mkdir(mode=0o700, exist_ok=True)
    with open('/run/edgemap-update.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        compatible = Path('/proc/device-tree/compatible').read_bytes().split(b'\0')
        assert b'raspberrypi,4-model-b' in compatible, 'profile requires Raspberry Pi 4 Model B'
        parts, slot, trial = inspect()
        mount(parts[5], '/data', 'ext4')
        mount(parts[0], '/selector', 'vfat')
        DATA.mkdir(exist_ok=True)
        statefile = DATA / 'state.json'
        state = json.loads(statefile.read_text()) if statefile.exists() else {}
        command = sys.argv[1]
        if command == 'status':
            print(json.dumps(dict(slot=slot, trial=trial, state=state), indent=2))
        elif command == 'install' and len(sys.argv) == 3:
            install(sys.argv[2], parts, slot, trial, state)
        elif command == 'prepare':
            from grow import grow_factory_data
            grow_factory_data(parts, slot, trial, state, run, atomic)
            prepare_persistence()
        elif command == 'boot':
            boot(slot, trial, state)
        else:
            raise ValueError('usage: edgemap-update status | install BUNDLE | boot')

if __name__ == '__main__':
    main()
