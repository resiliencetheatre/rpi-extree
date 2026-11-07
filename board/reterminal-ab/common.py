"""Fixed layout and canonical SWUpdate manifest. No manifest-controlled devices."""
import hashlib
import json
import re
import shutil
from pathlib import Path

if not __debug__:
    raise RuntimeError('update validation requires Python assertions; disable optimization')

PROFILE = 'reterminal-cm4-lvgl-v1'
LAYOUT = 1
SIZES = [32, 128, 128, 768, 768, 4096]
UUIDS = [f'67b6d541-1883-4ac4-a501-{n:012d}' for n in range(1, 7)]

def payload_metadata(data):
    if isinstance(data, Path):
        with data.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        return dict(size=data.stat().st_size, sha256=digest)
    return dict(size=len(data), sha256=hashlib.sha256(data).hexdigest())

def metadata(version, images):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]{0,63}', version):
        raise ValueError('invalid release version')
    return dict(version=version, profile=PROFILE, layout=LAYOUT,
                payloads={name: payload_metadata(data)
                          for name, data in images.items()})

def description(meta):
    assert meta['profile'] == PROFILE and meta['layout'] == LAYOUT
    metadata(meta['version'], {})  # Validate before interpolating libconfig strings.
    assert set(meta['payloads']) == {'boot-a.vfat', 'boot-b.vfat', 'rootfs.ext4'}
    selections = []
    for slot in ('a', 'b'):
        entries = []
        for filename, device, limit in [(f'boot-{slot}.vfat', '/dev/ab-boot', 128),
                                        ('rootfs.ext4', '/dev/ab-root', 768)]:
            p = meta['payloads'][filename]
            assert 0 < p['size'] <= limit * 1024**2
            assert re.fullmatch('[a-f0-9]{64}', p['sha256'])
            entries.append('{ filename = "%s"; device = "%s"; type = "raw"; sha256 = "%s"; }'
                           % (filename, device, p['sha256']))
        selections.append('%s = { images = (%s); };' % (slot, ','.join(entries)))
    return ('software = { version = "%s"; hardware-compatibility = ["%s"]; '
            'stable = { %s }; };\n' % (meta['version'], PROFILE, ' '.join(selections))).encode()

def archive_write(path, entries):
    with open(path, 'wb') as out:
        for i, (name, data) in enumerate(entries + [('TRAILER!!!', b'')]):
            name = name.encode() + b'\0'
            size = data.stat().st_size if isinstance(data, Path) else len(data)
            fields = [i, 0o100644, 0, 0, 1, 0, size, 0, 0, 0, 0, len(name), 0]
            head = b'070701' + ''.join(f'{x:08x}' for x in fields).encode()
            out.write(head + name + b'\0' * (-(110 + len(name)) % 4))
            if isinstance(data, Path):
                with data.open('rb') as source:
                    shutil.copyfileobj(source, out, 1024**2)
            else:
                out.write(data)
            out.write(b'\0' * (-size % 4))

def archive_read(path, directory=None):
    # Never extract archive paths. Bound the archive and each member before allocation.
    assert path.stat().st_size <= 1100 * 1024**2
    result = {}
    with path.open('rb') as src:
        while True:
            h = src.read(110)
            assert len(h) == 110 and h[:6] == b'070701'
            f = [int(h[i:i+8], 16) for i in range(6, 110, 8)]
            size, namesize = f[6], f[11]
            assert 1 <= namesize <= 128 and size <= 768 * 1024**2 and f[4] == 1
            raw = src.read(namesize)
            assert raw.endswith(b'\0')
            name = raw[:-1].decode('ascii')
            src.read(-(110 + namesize) % 4)
            if name == 'TRAILER!!!':
                assert size == 0
                while chunk := src.read(1024**2):
                    assert not chunk.strip(b'\0')
                break
            assert name in {'sw-description', 'sw-description.sig', 'release.json',
                            'release.sig', 'boot-a.vfat', 'boot-b.vfat', 'rootfs.ext4'}
            assert name not in result
            payload = name in {'boot-a.vfat', 'boot-b.vfat', 'rootfs.ext4'}
            if not payload:
                assert size <= 64 * 1024, 'oversized manifest or signature'
            if directory is not None and payload:
                data = Path(directory) / name
                with data.open('xb') as out:
                    remaining = size
                    while remaining:
                        chunk = src.read(min(1024**2, remaining))
                        assert chunk, 'truncated payload'
                        out.write(chunk)
                        remaining -= len(chunk)
            else:
                data = src.read(size)
                assert len(data) == size
            assert len(src.read(-size % 4)) == -size % 4
            result[name] = data
    assert list(result)[:2] == ['sw-description', 'sw-description.sig']
    assert len(result) == 7
    return result
