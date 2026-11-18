#!/usr/bin/env python3
"""Save the visible Linux true-colour framebuffer as a 24-bit BMP."""
import argparse
import fcntl
import mmap
import os
from pathlib import Path
import struct
import sys

FBIOGET_VSCREENINFO = 0x4600
FBIOGET_FSCREENINFO = 0x4602
MAX_IMAGE_BYTES = 64 * 1024 * 1024


def screen_info(fd):
    variable = bytearray(160)  # struct fb_var_screeninfo: forty __u32 values
    fixed = bytearray(80)      # sufficient for 32/64-bit struct fb_fix_screeninfo
    fcntl.ioctl(fd, FBIOGET_VSCREENINFO, variable, True)
    fcntl.ioctl(fd, FBIOGET_FSCREENINFO, fixed, True)
    values = struct.unpack('=40I', variable)
    # Native alignment matters: smem_start is unsigned long, followed by
    # four __u32, three __u16 and the aligned __u32 line_length.
    info = struct.unpack_from('@16sL4I3HI', fixed)
    return dict(width=values[0], height=values[1], virtual_width=values[2],
                virtual_height=values[3], xoffset=values[4], yoffset=values[5],
                bpp=values[6], grayscale=values[7],
                channels=[tuple(values[index:index + 3]) for index in (8, 11, 14)],
                nonstd=values[20], vmode=values[33],
                memory=info[2], type=info[3], visual=info[5], stride=info[9])


def validate(info):
    width, height, bpp = info['width'], info['height'], info['bpp']
    if info['type'] != 0 or info['visual'] != 2 or info['grayscale'] or info['nonstd']:
        raise ValueError('Only standard packed-pixel TRUECOLOR framebuffers are supported')
    if bpp not in (16, 24, 32) or not (0 < width <= 16384 and 0 < height <= 16384):
        raise ValueError('Unsupported framebuffer depth or dimensions')
    if width * height * 4 > MAX_IMAGE_BYTES:
        raise ValueError('Framebuffer exceeds screenshot size limit')
    if (info['xoffset'] + width > info['virtual_width'] or
            info['yoffset'] + height > info['virtual_height'] or info['vmode'] & 256):
        raise ValueError('Invalid visible offsets or unsupported Y-wrap mode')
    if (info['stride'] < (info['xoffset'] + width) * (bpp // 8) or
            (info['yoffset'] + height) * info['stride'] > info['memory']):
        raise ValueError('Framebuffer stride/visible region exceeds mapped memory')
    occupied = 0
    for offset, length, msb_right in info['channels']:
        if msb_right or not 0 < length <= 16 or offset + length > bpp:
            raise ValueError('Unsupported RGB bitfields')
        mask = ((1 << length) - 1) << offset
        if mask & occupied:
            raise ValueError('Overlapping RGB bitfields')
        occupied |= mask


def snapshot(device):
    fd = os.open(device, os.O_RDONLY | os.O_CLOEXEC)
    try:
        info = screen_info(fd)
        validate(info)
        width, height = info['width'], info['height']
        pixel_bytes = info['bpp'] // 8
        # Map only as far as the last visible row. Copy visible pixels promptly;
        # pixel conversion and file encoding happen after releasing the mapping.
        end = (info['yoffset'] + height) * info['stride']
        with mmap.mmap(fd, end, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ) as memory:
            rows = []
            for y in range(height):
                start = (info['yoffset'] + y) * info['stride'] + info['xoffset'] * pixel_bytes
                rows.append(memory[start:start + width * pixel_bytes])
        return info, rows
    finally:
        os.close(fd)


def bmp(info, rows, byteorder=sys.byteorder):
    """Convert native framebuffer RGB bitfields to bottom-up, padded BGR rows."""
    validate(info)
    width, height = info['width'], info['height']
    pixel_bytes = info['bpp'] // 8
    row_size = (width * 3 + 3) & ~3
    image_size = row_size * height
    header = struct.pack('<2sIHHI', b'BM', 54 + image_size, 0, 0, 54)
    header += struct.pack('<IiiHHIIiiII', 40, width, height, 1, 24, 0, image_size, 0, 0, 0, 0)
    result = bytearray(header)
    if len(rows) != height:
        raise ValueError('Incomplete framebuffer snapshot')
    for row in reversed(rows):
        if len(row) != width * pixel_bytes:
            raise ValueError('Incomplete framebuffer row')
        for x in range(width):
            pixel = int.from_bytes(row[x * pixel_bytes:(x + 1) * pixel_bytes], byteorder)
            rgb = []
            for offset, length, _ in info['channels']:
                maximum = (1 << length) - 1
                value = (pixel >> offset) & maximum
                rgb.append((value * 255 + maximum // 2) // maximum)
            result.extend(reversed(rgb))
        result.extend(b'\0' * (row_size - width * 3))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New BMP file, preferably under /data')
    parser.add_argument('--device', default=os.environ.get('LV_LINUX_FBDEV_DEVICE') or '/dev/fb0')
    args = parser.parse_args()
    try:
        if args.output.suffix.lower() != '.bmp':
            raise ValueError('Use a .bmp output filename')
        if args.output.exists() or args.output.is_symlink():
            raise ValueError('Output already exists; choose a new filename')
        info, rows = snapshot(args.device)
        encoded = bmp(info, rows)
        with args.output.open('xb') as stream:
            stream.write(encoded)
        print(f'Saved {info["width"]}x{info["height"]} screenshot to {args.output}')
        return 0
    except (OSError, ValueError) as error:
        print(f'fb-screenshot: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
