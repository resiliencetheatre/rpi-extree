"""Synthetic archives and disposable workspaces only; no make or network."""
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('kernel_hash', Path(__file__).with_name('kernel-hash.py'))
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)
COMMIT = 'a' * 40
FILENAME = f'linux-{COMMIT}.tar.gz'


class KernelHashTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'buildroot').mkdir()
        (self.root/'buildroot/Makefile').touch()
        self.ext = self.root/'rpi-extree'
        self.ext.mkdir()
        (self.ext/'external.desc').write_text('name: rpi\n')
        self.hashes = []
        for package in ('linux', 'linux-headers'):
            path = self.ext/f'patches/{package}/custom/{package}.hash'
            path.parent.mkdir(parents=True)
            path.write_text('# Preserve this comment\nsha256  '+ 'f'*64 +'  old.tar.gz\n')
            self.hashes.append(path)
        self.output = self.root/'output'
        self.output.mkdir()
        self.config = self.output/'.config'
        self.config.write_text('BR2_ROOTFS_POST_BUILD_SCRIPT="${BR2_EXTERNAL}/board/pocketterm-ab/post-build.sh"\n'
                               'BR2_LINUX_KERNEL_CUSTOM_TARBALL=y\nBR2_KERNEL_HEADERS_AS_KERNEL=y\n'
                               f'BR2_LINUX_KERNEL_CUSTOM_TARBALL_LOCATION="$(call github,raspberrypi,linux,{COMMIT})/{FILENAME}"\n'
                               'BR2_DL_DIR="$(TOPDIR)/dl"\nBR2_GLOBAL_PATCH_DIR="${BR2_EXTERNAL}/patches"\n')
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:gz') as archive:
            payload = b'VERSION = 6\nPATCHLEVEL = 18\n'
            entry = tarfile.TarInfo(f'linux-{COMMIT}/Makefile')
            entry.size = len(payload)
            archive.addfile(entry, io.BytesIO(payload))
        self.payload = data.getvalue()
        self.digest = hashlib.sha256(self.payload).hexdigest()

    def selected(self, environment=None):
        return helper.plan(self.root, self.output, environment or {})

    def run_helper(self, selected, downloader):
        with contextlib.redirect_stdout(io.StringIO()):
            helper.prepare(selected, downloader)

    def test_download_record_reuse_and_idempotence(self):
        selected = self.selected()
        calls = []
        def download(url, path):
            calls.append(url)
            path.write_bytes(self.payload)
        self.run_helper(selected, download)
        for path in self.hashes:
            self.assertIn('# Preserve this comment', path.read_text())
            self.assertIn('old.tar.gz', path.read_text())
            self.assertIn(f'sha256  {self.digest}  {FILENAME}', path.read_text())
        self.assertEqual(selected['archive'].read_bytes(), self.payload)
        self.run_helper(selected, download)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.hashes[0].read_text().count(FILENAME), 1)

    def test_conflict_prevents_all_hash_writes_and_cache_publication(self):
        self.hashes[1].write_text(f'sha256  {"0"*64}  {FILENAME}\n')
        originals = [path.read_bytes() for path in self.hashes]
        selected = self.selected()
        with self.assertRaisesRegex(helper.HashError, 'Checksum conflict'):
            self.run_helper(selected, lambda url, path: path.write_bytes(self.payload))
        self.assertEqual([path.read_bytes() for path in self.hashes], originals)
        self.assertFalse(selected['archive'].exists())

    def test_failed_download_leaves_no_archive_or_hash_changes(self):
        selected = self.selected()
        originals = [path.read_bytes() for path in self.hashes]
        def fail(url, path):
            path.write_bytes(b'partial')
            raise OSError('network interrupted')
        with self.assertRaisesRegex(OSError, 'interrupted'):
            self.run_helper(selected, fail)
        self.assertFalse(selected['archive'].exists())
        self.assertFalse(list(selected['archive'].parent.glob('.kernel-hash-*')))
        self.assertEqual([path.read_bytes() for path in self.hashes], originals)

    def test_bad_archive_does_not_gain_a_hash(self):
        for data in (b'<html>error</html>', self.payload[:-12]):
            with self.subTest(data=data[:12]):
                selected = self.selected()
                with self.assertRaises((OSError, EOFError, tarfile.TarError)):
                    self.run_helper(selected, lambda url, path: path.write_bytes(data))
                self.assertNotIn(FILENAME, self.hashes[0].read_text())
                self.assertFalse(selected['archive'].exists())

    def test_symlinked_hash_and_unversioned_fallback_preserved(self):
        original = self.hashes[1]
        original.unlink()
        original.symlink_to(self.hashes[0])
        unversioned = self.hashes[0].parents[1]/'linux.hash'
        self.hashes[0].rename(unversioned)
        original.unlink()
        original.symlink_to(unversioned)
        selected = self.selected()
        self.assertEqual(selected['writable'], [unversioned])
        self.run_helper(selected, lambda url, path: path.write_bytes(self.payload))
        self.assertTrue(original.is_symlink())
        self.assertIn(FILENAME, original.read_text())

    def test_resolves_cache_override_and_rejects_unexpanded_expressions(self):
        cache = self.root/'other-cache'
        self.assertEqual(self.selected({'DL_DIR': str(cache)})['archive'], cache/'linux'/FILENAME)
        with self.assertRaisesRegex(helper.HashError, 'absolute'):
            self.selected({'DL_DIR': 'relative'})
        self.config.write_text(self.config.read_text().replace('$(TOPDIR)/dl', '$(shell touch unsafe)'))
        with self.assertRaisesRegex(helper.HashError, 'Unsupported variable'):
            self.selected()

    def test_rejects_wrong_profile_unpinned_url_and_missing_active_hashes(self):
        original = self.config.read_text()
        for old, new in [('pocketterm-ab/', 'another-board/'), (COMMIT, 'moving-branch'),
                         ('${BR2_EXTERNAL}/patches', '${BR2_EXTERNAL}/missing')]:
            with self.subTest(new=new):
                self.config.write_text(original.replace(old, new))
                with self.assertRaises(helper.HashError):
                    self.selected()
        self.config.write_text(original)
        self.hashes[1].unlink()
        with self.assertRaisesRegex(helper.HashError, 'linux-headers.hash'):
            self.selected()

    def test_changed_configuration_aborts_before_hash_writes(self):
        selected = self.selected()
        def download(url, path):
            path.write_bytes(self.payload)
            self.config.write_text(self.config.read_text()+'# changed\n')
        with self.assertRaisesRegex(helper.HashError, 'configuration changed'):
            self.run_helper(selected, download)
        self.assertNotIn(FILENAME, self.hashes[0].read_text())

    def test_dry_run_never_downloads_writes_or_invokes_make(self):
        script = self.root/'rpi-extree/board/pocketterm-ab/kernel-hash.py'
        script.parent.mkdir(parents=True)
        with patch.object(helper, '__file__', str(script)), patch('sys.argv', [str(script), '--output', str(self.output), '--dry-run']), patch.object(helper, 'prepare') as prepare, patch.object(helper.subprocess, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(helper.main(), 0)
        prepare.assert_not_called()
        run.assert_not_called()
        self.assertFalse((self.root/'buildroot/dl').exists())
        self.assertFalse(script.with_name('.kernel-hash.lock').exists())

    def test_all_existing_algorithms_are_checked(self):
        self.hashes[0].write_text(f'sha512  {"0"*128}  {FILENAME}\n')
        with self.assertRaisesRegex(helper.HashError, 'Checksum conflict'):
            self.run_helper(self.selected(), lambda url, path: path.write_bytes(self.payload))

    def test_explicit_url_and_other_output_external_tree(self):
        text = self.config.read_text().replace(f'$(call github,raspberrypi,linux,{COMMIT})',
                                             f'https://github.com/raspberrypi/linux/archive/{COMMIT}')
        self.config.write_text(text)
        self.assertEqual(self.selected()['filename'], FILENAME)
        (self.output/'.br2-external.mk').write_text('export BR2_EXTERNAL_rpi_PATH = /another/tree\n')
        with self.assertRaisesRegex(helper.HashError, 'another external tree'):
            self.selected()
