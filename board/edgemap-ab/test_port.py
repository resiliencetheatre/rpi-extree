"""EdgeMap policy and factory integration checks; no images or devices built."""
import json
import os
from pathlib import Path
import re
import runpy
import tempfile
import unittest
from unittest.mock import patch
import common
import control

BOARD = Path(__file__).resolve().parent


class PortTests(unittest.TestCase):
    def test_factory_config_and_slot_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            images = root / 'images'
            firmware = images / 'rpi-firmware'
            firmware.mkdir(parents=True)
            (firmware / 'config.txt').write_text('kernel=Image\n')
            fixed = images / 'rpi-tryboot-firmware'
            fixed.mkdir()
            (fixed / 'revision').write_text('ab5c7f86283ceb58b7adb269cae1d16092a31bf6')
            for name in ('start4.elf', 'fixup4.dat'):
                (fixed / name).write_bytes(b'pinned fixture')
            for name in ('Image', 'bcm2711-rpi-4-b.dtb', 'ptt_keys.dtb', 'rootfs.ext4'):
                (images / name).write_bytes(b'fixture')
            (images / 'release-version').write_text('test-1')

            def inspect(command, **kwargs):
                cfg = (images / 'genimage-ab.cfg').read_text()
                self.assertIn('partition-table-type = "gpt"', cfg)
                self.assertIn('size = 16384M', cfg)
                for uid in common.UUIDS:
                    self.assertIn(uid, cfg)
                # genimage consumes these transient staging directories.
                boot = Path(re.search(r'image = "([^"]+/a/config.txt)"', cfg)[1]).parent
                work = boot.parent
                for slot, index in [('a', 3), ('b', 4)]:
                    cmdline = (work / slot / 'cmdline.txt').read_text().split()
                    self.assertEqual([x for x in cmdline if x.startswith('root=')],
                                     ['root=PARTUUID=' + common.UUIDS[index]])
                    self.assertTrue((work / slot / 'ptt_keys.dtb').is_file())
                    self.assertEqual((work / slot / 'start4.elf').read_bytes(), b'pinned fixture')
                self.assertEqual((work / 'selector/autoboot.txt').read_bytes(), control.selector('a'))
                self.assertEqual((work / 'data/.edgemap-factory-grow-v1').read_text(),
                                 f'{common.PROFILE} {common.LAYOUT}\n')
            with patch.dict(os.environ, BINARIES_DIR=str(images), HOST_DIR=str(root/'host'), BUILD_DIR=str(root)), patch('subprocess.run', side_effect=inspect) as run:
                runpy.run_path(str(BOARD / 'factory.py'))
                run.assert_called_once()

    def test_trial_health_controls_commit(self):
        state = dict(phase='pending', previous='a', target='b', version='test-1')
        for healthy in (True, False):
            with patch.object(Path, 'read_text', return_value='test-1'), patch.object(control, 'SELECTOR') as selector, patch.object(control, 'record') as record, patch.object(control, 'atomic') as atomic, patch.object(control.os, 'sync'), patch('health.ready', return_value=healthy), patch.object(control.time, 'monotonic', side_effect=[0, 0, 61]), patch.object(control.time, 'sleep'):
                selector.read_bytes.return_value = control.selector('a')
                if healthy:
                    control.boot('b', True, state)
                    atomic.assert_called_once_with(selector, control.selector('b'))
                    self.assertEqual(record.call_args.args[0]['phase'], 'committed')
                else:
                    with self.assertRaisesRegex(RuntimeError, 'readiness deadline'):
                        control.boot('b', True, state)
                    atomic.assert_not_called()

    def test_settings_symlinks_survive_atomic_replacement_and_prepare_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root/'settings.ini'
            target.write_text('original')
            source = str(target)
            backing_root = root/'data'
            real_path = Path
            def remap(value):
                return backing_root if value == '/data/persist' else real_path(value)
            with patch.object(control, 'PERSISTENT_PATHS', ()), patch.object(control, 'PERSISTENT_FILES', (source,)), patch.object(control, 'Path', side_effect=remap), patch.object(control.os, 'sync'):
                control.prepare_persistence()
                backing = target.readlink()
                stage = backing.with_suffix('.new')
                stage.write_text('changed')
                os.replace(stage, backing)
                control.prepare_persistence()
                self.assertTrue(target.is_symlink())
                self.assertEqual(target.read_text(), 'changed')
