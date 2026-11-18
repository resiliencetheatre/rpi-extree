"""Synthetic framebuffer tests; no real device reads or builds."""
import contextlib
import importlib.util
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('fb_screenshot', Path(__file__).with_name('fb-screenshot.py'))
capture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture)


def screen(width=2, height=1, bpp=32):
    channels = [(16, 8, 0), (8, 8, 0), (0, 8, 0)] if bpp != 16 else [(11, 5, 0), (5, 6, 0), (0, 5, 0)]
    return dict(width=width, height=height, virtual_width=width, virtual_height=height,
                xoffset=0, yoffset=0, bpp=bpp, grayscale=0, nonstd=0, vmode=0,
                channels=channels, memory=width*height*(bpp//8), type=0, visual=2,
                stride=width*(bpp//8))


class ScreenshotTests(unittest.TestCase):
    def test_rgb565_24_32_and_bmp_padding(self):
        for bpp, raw in [(16, bytes.fromhex('00f8e007')), (24, bytes.fromhex('0000ff00ff00')),
                         (32, bytes.fromhex('0000ffff00ff00ff'))]:
            with self.subTest(bpp=bpp):
                data = capture.bmp(screen(bpp=bpp), [raw], 'little')
                self.assertEqual(data[:2], b'BM')
                self.assertEqual(struct.unpack_from('<I', data, 2)[0], len(data))
                self.assertEqual(data[54:], bytes.fromhex('0000ff00ff000000'))
                self.assertEqual(struct.unpack_from('<ii', data, 18), (2, 1))

    def test_bottom_up_and_big_endian_pixel_values(self):
        data = capture.bmp(screen(width=1, height=2), [bytes.fromhex('00ff0000'), bytes.fromhex('000000ff')], 'big')
        self.assertEqual(data[54:], bytes.fromhex('ff0000000000ff00'))

    def test_ioctl_decodes_native_fixed_layout_and_variable_fields(self):
        values = [0]*40
        values[:8] = [2, 1, 4, 3, 1, 2, 32, 0]
        values[8:17] = [16,8,0,8,8,0,0,8,0]
        values[33] = 256
        values[35] = 99  # colorspace, distinct from vmode
        def ioctl(fd, request, buffer, mutate):
            self.assertTrue(mutate)
            if request == capture.FBIOGET_VSCREENINFO:
                buffer[:] = struct.pack('=40I', *values)
            else:
                encoded = struct.pack('@16sL4I3HI', b'fixture', 0, 48, 0, 0, 2, 0, 0, 0, 16)
                buffer[:len(encoded)] = encoded
        with patch.object(capture.fcntl, 'ioctl', side_effect=ioctl):
            info = capture.screen_info(7)
        self.assertEqual((info['stride'],info['memory'],info['vmode']), (16,48,256))
        self.assertEqual(info['channels'], [(16,8,0),(8,8,0),(0,8,0)])

    def test_snapshot_crops_offsets_and_stride_without_writing_device(self):
        info = screen()
        info.update(virtual_width=4, virtual_height=2, xoffset=1, yoffset=1, stride=20, memory=40)
        red_green = bytes.fromhex('0000ff0000ff0000')
        memory = bytes(24)+red_green+bytes(8)
        with patch.object(capture.os, 'open', return_value=7) as opened, patch.object(capture.os, 'close') as closed, patch.object(capture, 'screen_info', return_value=info), patch.object(capture.mmap, 'mmap', return_value=contextlib.nullcontext(memory)) as mapped:
            _, rows = capture.snapshot('/dev/fb0')
        self.assertEqual(rows, [red_green])
        opened.assert_called_once_with('/dev/fb0', capture.os.O_RDONLY | capture.os.O_CLOEXEC)
        self.assertEqual(mapped.call_args.kwargs['prot'], capture.mmap.PROT_READ)
        closed.assert_called_once_with(7)

    def test_unsupported_formats_and_out_of_bounds_are_rejected(self):
        for changes in [dict(visual=3), dict(type=1), dict(grayscale=1), dict(bpp=8),
                        dict(xoffset=1), dict(memory=1), dict(stride=1), dict(vmode=256),
                        dict(channels=[(0,8,0)]*3)]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                capture.validate(dict(screen(), **changes))

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'screen.bmp'
            path.write_bytes(b'keep')
            with patch('sys.argv', ['fb-screenshot', str(path)]), patch.object(capture, 'snapshot') as snap, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(capture.main(), 1)
            snap.assert_not_called()
            self.assertEqual(path.read_bytes(), b'keep')

    def test_main_creates_bmp_and_closes_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'screen.bmp'
            with patch('sys.argv', ['fb-screenshot', str(path)]), patch.object(capture, 'snapshot', return_value=(screen(), [bytes(8)])), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(capture.main(), 0)
            self.assertEqual(path.read_bytes()[:2], b'BM')
