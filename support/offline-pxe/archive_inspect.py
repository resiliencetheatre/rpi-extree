"""Read authenticated installer archives without installing Debian packages.

Only regular files explicitly requested from a .deb are returned. Initramfs names
are listed, never extracted. Limits also apply to signed-but-unexpected inputs.
"""
import bz2
import gzip
import io
import lzma
import tarfile
import tempfile
import zlib
from pathlib import PurePosixPath

LIMIT = 512 * 1024**2


def safe_name(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\x00' in name:
        raise ValueError('Unsafe archive path')
    return str(p)


def deb_files(path, wanted):
    result = {}
    with open(path, 'rb') as f:
        if f.read(8) != b'!<arch>\n':
            raise ValueError('Not a Debian ar archive')
        found = False
        while header := f.read(60):
            if len(header) != 60 or header[58:] != b'`\n':
                raise ValueError('Invalid ar header')
            size = int(header[48:58])
            if not 0 <= size <= LIMIT:
                raise ValueError('Oversized Debian archive member')
            name = header[:16].decode('ascii').strip().rstrip('/')
            if name.startswith('data.tar'):
                if found:
                    raise ValueError('Duplicate Debian data member')
                found = True
                data = f.read(size)
                if len(data) != size:
                    raise ValueError('Truncated Debian archive')
                # tarfile supports gzip, xz and bzip2. Unknown formats fail closed.
                with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as tf:
                    expanded = 0
                    for entry in tf:
                        expanded += max(0, entry.size)
                        if expanded > LIMIT:
                            raise ValueError('Oversized Debian data archive')
                        entry_name = safe_name(entry.name)
                        if entry_name in wanted:
                            if not entry.isfile() or entry.size > 4 * 1024**2 or entry_name in result:
                                raise ValueError('Invalid installer policy member')
                            result[entry_name] = tf.extractfile(entry).read()
            else:
                f.seek(size, 1)
            if size % 2:
                f.read(1)
        if not found:
            raise ValueError('No Debian data archive')
    return result


def initramfs_names(path):
    """List newc archives, optionally with early uncompressed and compressed parts."""
    names = []
    budget = [LIMIT]

    def scan(f, depth=0):
        if depth > 3:
            raise ValueError('Nested initramfs compression')
        while True:
            # Archives and compressed streams may have zero padding between them.
            byte = f.read(1)
            while byte == b'\0':
                byte = f.read(1)
            if not byte:
                return
            f.seek(-1, 1)
            start = f.tell()
            magic = f.read(6)
            f.seek(start)
            if magic in (b'070701', b'070702'):
                while True:
                    header = f.read(110)
                    if len(header) != 110 or header[:6] not in (b'070701', b'070702'):
                        raise ValueError('Invalid newc header')
                    values = [int(header[i:i+8], 16) for i in range(6, 110, 8)]
                    size, nsize = values[6], values[11]
                    if not 1 <= nsize <= 4096 or size > LIMIT:
                        raise ValueError('Invalid newc size')
                    raw = f.read(nsize)
                    if len(raw) != nsize or raw[-1:] != b'\0':
                        raise ValueError('Truncated newc name')
                    name = safe_name(raw[:-1].decode('utf-8'))
                    f.read(-(110 + nsize) % 4)
                    remaining = size
                    while remaining:
                        block = f.read(min(remaining, 1024**2))
                        if not block:
                            raise ValueError('Truncated newc data')
                        remaining -= len(block)
                    f.read(-size % 4)
                    if name == 'TRAILER!!!':
                        break
                    names.append(name)
                    if len(names) > 200000:
                        raise ValueError('Too many initramfs entries')
                continue
            if magic.startswith(b'\x1f\x8b'):
                decoder = zlib.decompressobj(31)
                is_zlib = True
            elif magic == b'\xfd7zXZ\0':
                decoder = lzma.LZMADecompressor(memlimit=LIMIT)
                is_zlib = False
            else:
                raise ValueError('Unsupported initramfs compression; review installer')
            with tempfile.TemporaryFile() as expanded:
                while not decoder.eof:
                    block = f.read(65536)
                    if not block:
                        raise ValueError('Truncated compressed initramfs')
                    while True:
                        out = decoder.decompress(block, max_length=min(budget[0]+1, 1024**2))
                        budget[0] -= len(out)
                        if budget[0] < 0:
                            raise ValueError('Initramfs exceeds inspection limit')
                        expanded.write(out)
                        if decoder.eof:
                            f.seek(-len(decoder.unused_data), 1)
                            break
                        if is_zlib:
                            block = decoder.unconsumed_tail
                            if not block:
                                break
                        else:
                            if decoder.needs_input:
                                break
                            block = b''
                expanded.seek(0)
                scan(expanded, depth+1)
    with open(path, 'rb') as f:
        scan(f)
    return names
