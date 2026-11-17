"""Exercise the installation hook against a disposable target; no image build."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BOARD = Path(__file__).resolve().parent


class PostBuildTests(unittest.TestCase):
    def test_wrapper_template_and_finish_unit_installed_without_health_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root/'target'
            (target/'etc').mkdir(parents=True)
            (target/'etc/fstab').write_text('old /boot vfat defaults 0 0\n')
            for name in ('usr/bin/openssl', 'usr/bin/lsblk', 'usr/bin/swupdate',
                         'usr/sbin/sfdisk', 'usr/sbin/partx', 'usr/sbin/blockdev', 'usr/sbin/resize2fs'):
                path = target/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('#!/bin/sh\nexit 0\n')
                path.chmod(0o755)
            ssl = target/'usr/lib/python3.13/lib-dynload/_ssl.fixture.so'
            ssl.parent.mkdir(parents=True)
            ssl.touch()
            build = root/'build/swupdate-2026.05.1'
            build.mkdir(parents=True)
            (build/'.config').write_text(''.join('CONFIG_'+option+'=y\n' for option in
                ('SSL_IMPL_OPENSSL', 'HASH_VERIFY', 'SIGNED_IMAGES', 'SIGALG_RAWRSA', 'HW_COMPATIBILITY', 'LIBCONFIG', 'RAW')))
            images = root/'images'; images.mkdir()
            private = root/'private.pem'; public = root/'public.pem'
            subprocess.run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(private)], check=True, stderr=subprocess.DEVNULL)
            subprocess.run(['openssl','pkey','-in',str(private),'-pubout','-out',str(public)], check=True)
            env = dict(os.environ, AB_RELEASE_VERSION='test-1', AB_VERIFY_KEY=str(public),
                       BUILD_DIR=str(root/'build'), BINARIES_DIR=str(images))
            subprocess.run(['sh',str(BOARD/'post-build.sh'),str(target)], env=env, check=True)
            self.assertEqual((target/'usr/sbin/update.sh').resolve(), target/'usr/lib/pocketterm-ab/update_wrapper.py')
            self.assertTrue(os.access(target/'usr/sbin/update.sh', os.X_OK))
            self.assertEqual((target/'usr/share/pocketterm-update-api/sources.example.json').read_bytes(),
                             (BOARD/'api/sources.example.json').read_bytes())
            units = target/'etc/systemd/system'
            finish = (units/'pocketterm-update-finish.service').read_text()
            self.assertIn('After=pocketterm-ab-prepare.service pocketterm-ab.service pocketterm-update-api.service', finish)
            self.assertNotIn('Requires=pocketterm-ab.service', finish)
            self.assertTrue((units/'multi-user.target.wants/pocketterm-update-finish.service').is_file())
            self.assertNotIn('After=pocketterm-update-api', (units/'lvgl-console.service.d/update-api.conf').read_text())
            self.assertFalse((target/'etc/default/pocketterm-update-sources.json').exists())
