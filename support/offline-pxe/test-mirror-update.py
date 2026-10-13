#!/usr/bin/env python3
"""Synthetic repositories and mocked services only; never mounts a disk or uses Wi-Fi."""
import gzip
import contextlib
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import patch
import archive_inspect as inspect
import mirror_acquire as engine
import mirror_update as update
from common import settings, digest

HERE = Path(__file__).parent
profiles_test = engine.module('profile_fixtures', 'test-unattended-profiles.py')


def cpio(name, data=b''):
    name = name.encode()+b'\0'
    fields = [1, 0o100644, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name), 0]
    header = b'070701' + ''.join(f'{n:08x}' for n in fields).encode()
    return header+name+b'\0'*(-(110+len(name)) % 4)+data+b'\0'*(-len(data) % 4)


def ar_member(name, data):
    return (f'{name+"/":<16}{0:<12}{0:<6}{0:<6}{644:<8}{len(data):<10}`\n'.encode()
            + data + b'\n'*(len(data) % 2))


class ReaderTests(unittest.TestCase):
    def test_initramfs_concatenation_and_truncation(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'initrd'
            plain = cpio('early', b'x')+cpio('TRAILER!!!')
            late = cpio('usr/lib/firmware/example.bin', b'abc')+cpio('TRAILER!!!')
            for compressed in (gzip.compress(late), lzma.compress(late)):
                path.write_bytes(plain+b'\0'*16+compressed)
                self.assertEqual(inspect.initramfs_names(path), ['early', 'usr/lib/firmware/example.bin'])
                path.write_bytes(plain+compressed[:-8])
                with self.assertRaises(ValueError):
                    inspect.initramfs_names(path)
            path.write_bytes(gzip.compress(cpio('../escape')+cpio('TRAILER!!!')))
            with self.assertRaises(ValueError):
                inspect.initramfs_names(path)
            path.write_bytes(gzip.compress(late))
            with patch.object(inspect, 'LIMIT', 32), self.assertRaises(ValueError):
                inspect.initramfs_names(path)

    def test_deb_extracts_only_requested_regular_files(self):
        with tempfile.TemporaryDirectory() as d:
            payload = io.BytesIO()
            with tarfile.open(fileobj=payload, mode='w:xz') as tf:
                info = tarfile.TarInfo('./usr/share/policy')
                info.size = 3
                tf.addfile(info, io.BytesIO(b'abc'))
            deb = Path(d)/'test.udeb'
            deb.write_bytes(b'!<arch>\n'+ar_member('debian-binary', b'2.0\n')+ar_member('data.tar.xz', payload.getvalue()))
            self.assertEqual(inspect.deb_files(deb, {'usr/share/policy'}), {'usr/share/policy': b'abc'})
            deb.write_bytes(deb.read_bytes()[:-20])
            with self.assertRaises(ValueError):
                inspect.deb_files(deb, {'usr/share/policy'})

    def test_clearsigned_envelope_and_no_output_gpgv(self):
        raw = (b'-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA256\n\n'
               b'Codename: trixie\nSHA256:\n'
               b'-----BEGIN PGP SIGNATURE-----\n\nfixture\n'
               b'-----END PGP SIGNATURE-----\n')
        self.assertEqual(engine.verifier.clearsigned_text(raw), 'Codename: trixie\nSHA256:\n')
        for bad in (b'prefix\n'+raw, raw+b'unsigned data', raw+raw,
                    raw.replace(b'Codename:', b'-Codename:')):
            with self.assertRaises(ValueError):
                engine.verifier.clearsigned_text(bad)
        escaped = raw.replace(b'Codename: trixie', b'- -example')
        self.assertTrue(engine.verifier.clearsigned_text(escaped).startswith('-example'))
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            signed = root/'dists/trixie/InRelease'
            signed.parent.mkdir(parents=True)
            signed.write_bytes(raw)
            def verify_only(cmd, **kwargs):
                self.assertNotIn('--output', cmd)
                self.assertEqual(Path(cmd[-1]).read_bytes(), raw)
                return subprocess.CompletedProcess(cmd, 0)
            with patch.object(engine.verifier.subprocess, 'run', side_effect=verify_only):
                _, fields, _, _ = engine.verifier.release(root, 'trixie', root/'keyring')
            self.assertEqual(fields['Codename'], 'trixie')
            with patch.object(engine.verifier.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'gpgv')):
                with self.assertRaises(subprocess.CalledProcessError):
                    engine.verifier.release(root, 'trixie', root/'keyring')

    def test_bzip2_translation_selection(self):
        raw = 'main/i18n/Translation-ar'
        sums = {raw: (4598, 'uncompressed-hash'), raw+'.bz2': (1635, 'compressed-hash')}
        self.assertFalse(engine.preferred_index(raw, sums))
        self.assertTrue(engine.preferred_index(raw+'.bz2', sums))
        sums[raw+'.xz'] = (1000, 'xz-hash')
        self.assertFalse(engine.preferred_index(raw+'.bz2', sums))
        self.assertTrue(engine.preferred_index(raw+'.xz', sums))
        self.assertTrue(engine.preferred_index('main/binary-amd64/Release', {}))

    def test_dep11_selection(self):
        policy = {'components': ['main'], 'architectures': ['amd64'], 'sources': False}
        for name in ('main/dep11/Components-amd64.yml.gz', 'main/dep11/icons-48x48.tar.gz',
                     'main/dep11/icons-64x64@2.tar.gz'):
            self.assertTrue(engine.selected(policy, name))
            engine.relative(name)
        self.assertFalse(engine.selected(policy, 'main/dep11/Components-arm64.yml.gz'))
        self.assertFalse(engine.selected(policy, 'contrib/dep11/icons-48x48.tar.gz'))
        raw = 'main/dep11/icons-48x48.tar'
        self.assertFalse(engine.preferred_index(raw, {raw: (), raw+'.gz': ()}))
        self.assertTrue(engine.preferred_index(raw+'.gz', {raw: (), raw+'.gz': ()}))

    def test_dates_and_paths(self):
        now = datetime.now(timezone.utc)
        valid = {'Date': format_datetime(now-timedelta(days=1)), 'Valid-Until': format_datetime(now+timedelta(days=1))}
        engine.valid_release(valid, now=now)
        for fields in (dict(valid, Date=format_datetime(now+timedelta(days=1))),
                       dict(valid, **{'Valid-Until': format_datetime(now-timedelta(days=1))})):
            with self.assertRaises(ValueError):
                engine.valid_release(fields, now=now)
        with self.assertRaises(ValueError):
            engine.valid_release(valid, format_datetime(now), now=now)
        for name in ('../secret', '/absolute', 'pool/a%2fb', 'a\ncommand'):
            with self.assertRaises(ValueError):
                engine.relative(name)


class SignedRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.home = Path(cls.temp.name)/'gnupg'
        cls.home.mkdir(mode=0o700)
        subprocess.run(['gpg', '--homedir', str(cls.home), '--batch', '--pinentry-mode', 'loopback',
                        '--passphrase', '', '--quick-generate-key', 'Updater fixture', 'ed25519', 'sign', '0'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.keyring = Path(cls.temp.name)/'fixture.gpg'
        cls.keyring.write_bytes(subprocess.check_output(['gpg', '--homedir', str(cls.home), '--export']))

    @classmethod
    def tearDownClass(cls):
        subprocess.run(['gpgconf', '--homedir', str(cls.home), '--kill', 'gpg-agent'], check=False)
        cls.temp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.upstream = self.root/'upstream'
        self.stage = self.root/'stage'
        self.s = settings(HERE/'settings.json')
        self.s['keyring'] = str(self.keyring)
        self.s['generation'] = 'stage'
        self.requests = []
        for archive, suites in [('debian', ['trixie', 'trixie-updates']), ('debian-security', ['trixie-security'])]:
            for suite in suites:
                dist = self.upstream/archive/'dists'/suite
                dist.mkdir(parents=True)
                sums = []
                for component in self.s['components']:
                    body = b'package '+component.encode()
                    pool = f'pool/{component}/p/package.deb'
                    dest = self.upstream/archive/pool
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(body)
                    record = (f'Package: fixture\nArchitecture: all\nFilename: {pool}\nSize: {len(body)}\n'
                              f'SHA256: {hashlib.sha256(body).hexdigest()}\n\n').encode()
                    for index, data in [(f'{component}/binary-amd64/Packages', record),
                                        (f'{component}/debian-installer/binary-amd64/Packages', b'')]:
                        packed = lzma.compress(data)
                        path = dist/(index+'.xz')
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(packed)
                        sha = digest(path)
                        sums.append(f' {sha} {len(packed)} {index}.xz\n')
                        byhash = path.parent/'by-hash/SHA256'/sha
                        byhash.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(path, byhash)
                release = dist/'Release'
                release.write_text(f'Codename: {suite}\nDate: {format_datetime(datetime.now(timezone.utc)-timedelta(minutes=1))}\n'
                                   'Acquire-By-Hash: yes\nSHA256:\n'+''.join(sums))
                subprocess.run(['gpg', '--homedir', str(self.home), '--batch', '--yes', '--output', str(dist/'InRelease'),
                                '--clearsign', str(release)], check=True)
                subprocess.run(['gpg', '--homedir', str(self.home), '--batch', '--yes',
                                '--output', str(dist/'Release.gpg'), '--detach-sign', str(release)], check=True)
        owner = self
        class FixtureFetcher:
            def fetch(self, archive, name, dest, expected=None, limit=None):
                owner.requests.append(name)
                source = owner.upstream/archive/name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, dest)
                if expected:
                    engine.verifier.check(dest, expected)
        self.fetcher = FixtureFetcher()

    def test_signed_plan_and_all_coverage(self):
        files, releases = engine.plan(self.s, self.stage, self.fetcher, check_only=True)
        self.assertEqual(len(files), 8)  # four components in each distinct archive
        self.assertEqual(len(releases), 3)
        self.assertTrue(any('/by-hash/' in name for name in self.requests))
        active = self.root/'active'
        active.mkdir()
        for name in files:
            src = self.upstream/name
            target = active/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
        with patch.object(engine, 'space'):
            engine.acquire(files, self.stage, active, self.fetcher, 0)
        for name, expected in files.items():
            engine.verifier.check(self.stage/name, expected)
            self.assertNotEqual((active/name).stat().st_ino, (self.stage/name).stat().st_ino)
        before = digest(active/next(iter(files)))
        (self.stage/next(iter(files))).write_bytes(b'corrupt')
        self.assertEqual(digest(active/next(iter(files))), before)
        with self.assertRaises(ValueError):
            engine.verifier.verify(self.stage, self.s)

    def test_signature_and_index_corruption(self):
        signed = self.upstream/'debian/dists/trixie/InRelease'
        signed.write_text(signed.read_text().replace('Codename: trixie', 'Codename: invalid'))
        with self.assertRaises(subprocess.CalledProcessError):
            engine.plan(self.s, self.stage, self.fetcher, check_only=True)

    def test_missing_or_mismatched_installer_release_rejected(self):
        dist = self.upstream/'debian/dists/trixie'
        (dist/'Release.gpg').unlink()
        with self.assertRaises(FileNotFoundError):
            engine.plan(self.s, self.stage, self.fetcher, check_only=True)
        # Correctly signed, but inconsistent with the selected InRelease.
        release = dist/'Release'
        release.write_text(release.read_text().replace('Codename: trixie', 'Codename: other'))
        subprocess.run(['gpg', '--homedir', str(self.home), '--batch', '--yes',
                        '--output', str(dist/'Release.gpg'), '--detach-sign', str(release)], check=True)
        with self.assertRaisesRegex(ValueError, 'Release and InRelease metadata differ'):
            engine.plan(self.s, self.stage, self.fetcher, check_only=True)

    def test_offline_repair_preserves_pool_current_and_authenticity(self):
        base = self.root/'card'
        target = base/'generations/new'
        shutil.copytree(self.upstream, target)
        old = base/'generations/old'
        old.mkdir()
        (base/'current').symlink_to('generations/old')
        (target/'manifest.json').write_text(json.dumps({'generation': 'new', 'outcome': 'verified'}))
        for archive, suite in [('debian', 'trixie'), ('debian', 'trixie-updates'), ('debian-security', 'trixie-security')]:
            for name in ('Release', 'Release.gpg'):
                (target/archive/'dists'/suite/name).unlink()
        original = {str(p.relative_to(target)): p.read_bytes() for p in target.rglob('*') if p.is_file()}
        (target/'ready.sha256').write_text(''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n'
                                                 for name, data in original.items()))
        with patch.object(update, 'BASE', base), patch.object(update, 'maintenance', return_value=contextlib.nullcontext()), \
                patch.object(update.os, 'sync'):
            update.repair_metadata(self.s, 'new')
            update.repair_metadata(self.s, 'new')  # Repeat is safe, including after a partial repair.
            with self.assertRaisesRegex(ValueError, 'known-good'):
                update.repair_metadata(self.s, 'old')
        for name, content in original.items():
            self.assertEqual((target/name).read_bytes(), content)
        self.assertEqual((base/'current').readlink(), Path('generations/old'))
        self.assertEqual(sum('/Release' in line for line in (target/'ready.sha256').read_text().splitlines()), 6)
        # Splitting cannot make an invalid upstream signature acceptable.
        isolated = self.root/'bad'
        dist = isolated/'dists/trixie'
        dist.mkdir(parents=True)
        raw = (target/'debian/dists/trixie/InRelease').read_text()
        (dist/'InRelease').write_text(raw.replace('Codename: trixie', 'Codename: other'))
        with self.assertRaises(subprocess.CalledProcessError):
            engine.verifier.detached_from_inrelease(isolated, 'trixie', str(self.keyring))
        self.assertFalse((dist/'Release').exists())

    def test_index_hash_and_rotation(self):
        files, releases = engine.plan(self.s, self.stage, self.fetcher, check_only=True)
        engine.check_rotation(self.s, self.stage, self.fetcher, releases)
        signed = self.upstream/'debian/dists/trixie/InRelease'
        signed.write_bytes(signed.read_bytes()+b'\n')
        with self.assertRaises(ValueError):
            engine.check_rotation(self.s, self.stage, self.fetcher, releases)
        blob = next((self.upstream/'debian/dists/trixie/main/binary-amd64/by-hash/SHA256').iterdir())
        blob.write_bytes(b'broken')
        # Restore original signature; corruption is in authenticated index bytes.
        shutil.copyfile(self.stage/'debian/dists/trixie/InRelease', signed)
        with self.assertRaises(ValueError):
            engine.plan(self.s, self.root/'other', self.fetcher, check_only=True)


class TransportTests(unittest.TestCase):
    def test_interrupted_partial_resumes_and_is_bound_to_wifi(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            payload = b'abcdef'
            dest = root/'package.deb'
            calls = []
            def curl(cmd, **kwargs):
                calls.append(cmd)
                out = Path(cmd[cmd.index('--output')+1])
                if len(calls) == 1:
                    out.write_bytes(payload[:3])
                    return subprocess.CompletedProcess(cmd, 18, '200', 'interrupted')
                self.assertEqual(cmd[cmd.index('--continue-at')+1], '3')
                out.write_bytes(payload)
                return subprocess.CompletedProcess(cmd, 0, '206', '')
            fetcher = engine.Fetcher({'debian': 'https://fixture.invalid/debian'}, root)
            with patch.object(engine.subprocess, 'run', side_effect=curl), patch.object(engine.time, 'sleep'):
                fetcher.fetch('debian', 'pool/test.deb', dest, (len(payload), hashlib.sha256(payload).hexdigest()))
            self.assertEqual(dest.read_bytes(), payload)
            self.assertFalse((root/'package.deb.partial').exists())
            for cmd in calls:
                self.assertIn('if!wlan0', cmd)
                self.assertIn('=https', cmd)
                self.assertNotIn('--location', cmd)
                self.assertIn('--noproxy', cmd)

    def test_transport_error_reports_curl_http_and_partial_size(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fetcher = engine.Fetcher({'debian': 'https://fixture.invalid/debian'}, root)
            failure = subprocess.CompletedProcess([], 28, '000', 'curl: (28) Connection timed out')
            with patch.object(engine.subprocess, 'run', return_value=failure), patch.object(engine.time, 'sleep'):
                with self.assertRaisesRegex(ValueError, r'curl exit=28, HTTP=000, partial bytes=0; curl: .*timed out'):
                    fetcher.fetch('debian', 'pool/test.deb', root/'final', (3, hashlib.sha256(b'yes').hexdigest()))
            self.assertFalse((root/'final').exists())

    def test_hash_failure_never_publishes_download(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            def curl(cmd, **kwargs):
                Path(cmd[cmd.index('--output')+1]).write_bytes(b'bad')
                return subprocess.CompletedProcess(cmd, 0, '200', '')
            fetcher = engine.Fetcher({'debian': 'https://fixture.invalid/debian'}, root)
            with patch.object(engine.subprocess, 'run', side_effect=curl), patch.object(engine.time, 'sleep'):
                with self.assertRaisesRegex(ValueError, 'SHA256 mismatch: expected'):
                    fetcher.fetch('debian', 'pool/test.deb', root/'final', (3, hashlib.sha256(b'yes').hexdigest()))
            self.assertFalse((root/'final').exists())


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)/'data'
        self.run = Path(self.tmp.name)/'run'
        self.record = Path(self.tmp.name)/'state/transaction.json'
        self.active = self.base/'generations/old'
        self.active.mkdir(parents=True)
        (self.base/'current').symlink_to('generations/old')
        (self.active/'sentinel').write_bytes(b'preserve me')
        self.run.mkdir()
        self.s = settings(HERE/'settings.json')
        self.s['generation'] = 'new'
        self.calls = []
        def fake(*args, **kwargs):
            self.calls.append(tuple(map(str, args)))
        for target, value in [('BASE', self.base), ('RUN', self.run), ('RECORD', self.record),
                              ('command', fake), ('mounted', lambda *a, **k: None)]:
            patcher = patch.object(update, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(update.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0))
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.object(update.signal, 'signal')
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.object(update.os, 'sync')
        patcher.start()
        self.addCleanup(patcher.stop)

    def assert_old(self):
        self.assertEqual((self.base/'current').readlink(), Path('generations/old'))
        self.assertEqual((self.active/'sentinel').read_bytes(), b'preserve me')

    def test_appstream_repair_is_staged_and_keeps_active(self):
        target = self.base/'generations/new'
        target.mkdir()
        (target/'manifest.json').write_text('{"generation":"new","outcome":"verified"}')
        (target/'settings.json').write_text(json.dumps(self.s))
        (target/'ready.sha256').write_text('')
        name = 'main/dep11/icons-48x48.tar.gz'
        data = b'fixture icons'
        expected = (len(data), hashlib.sha256(data).hexdigest())
        def release(root, suite, keyring, **kwargs):
            return root/'dists'/suite, {'Acquire-By-Hash':'yes'}, {name: expected}, None
        def download(archive, remote, dest, expected):
            self.assertIn('/by-hash/SHA256/', remote)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        with patch.object(update.verifier, 'release', side_effect=release), \
                patch.object(update, 'space'), patch.object(update, 'Fetcher') as factory:
            factory.return_value.fetch.side_effect = ValueError('unavailable snapshot')
            with self.assertRaises(ValueError):
                update.repair_appstream(self.s, 'new')
            self.assertFalse((target/'debian').exists())
            factory.return_value.fetch.side_effect = download
            update.repair_appstream(self.s, 'new')
        dest = target/'debian/dists/trixie'/name
        self.assertEqual(dest.read_bytes(), data)
        self.assertEqual(dest.stat().st_mode & 0o777, 0o644)
        self.assertIn(name, (target/'ready.sha256').read_text())
        self.assert_old()
        self.assertFalse(self.record.exists())

    def test_failure_restores_readonly_and_prior_services(self):
        with self.assertRaises(InterruptedError):
            with update.maintenance(self.s, 'fixture'):
                self.assertTrue(self.record.exists())
                raise InterruptedError('fixture wifi loss')
        self.assertFalse(self.record.exists())
        self.assertFalse((self.run/'maintenance').exists())
        self.assertIn(('mount', '-o', 'remount,ro', str(self.base)), self.calls)
        self.assert_old()

    def test_boot_recovery_no_network(self):
        engine.atomic_json(self.record, {'uuid': self.s['ssd_uuid'], 'active': str(self.active),
                                        'services': update.SERVICES})
        update.restore(self.s)
        self.assertFalse(self.record.exists())
        self.assert_old()
        self.assertFalse(any('curl' in call for call in self.calls))

    def test_failed_restore_keeps_record_and_services_off(self):
        engine.atomic_json(self.record, {'uuid': self.s['ssd_uuid'], 'active': str(self.active), 'services': update.SERVICES})
        def fail(*args, **kwargs):
            if args[0] == 'mount':
                raise OSError('fixture mount failure')
        with patch.object(update, 'command', side_effect=fail), self.assertRaises(OSError):
            update.restore(self.s)
        self.assertTrue(self.record.exists())
        self.assert_old()

    def test_private_profile_import_render_and_seal(self):
        inputs = []
        for name, disk in [('nvme', '/dev/nvme0n1'), ('sata', '/dev/sda')]:
            source = Path(self.tmp.name)/(name+'.cfg')
            source.write_text(profiles_test.private_input(disk))
            inputs.append(source)
        update.import_profiles(self.s, inputs, 'menu')
        selected = update.read_profiles(self.s, self.active)
        self.assertEqual(update.private_root().stat().st_mode & 0o777, 0o700)
        target = self.base/'generations/new'
        update.profiles.generation(self.s, target)
        (target/'ready.sha256').write_text(''.join(f'{digest(p)}  {p.relative_to(target)}\n' for p in target.rglob('*') if p.is_file()))
        update.apply_profiles(self.s, target, selected)
        grub = (target/'tftp/debian-installer/amd64/grub/grub.cfg').read_text()
        self.assertIn('--id nvme', grub)
        self.assertIn('--id sata', grub)
        self.assertIn('set timeout=-1', grub)
        for line in (target/'ready.sha256').read_text().splitlines():
            sha, name = line.split('  ', 1)
            self.assertEqual(digest(target/name), sha)
        self.assertTrue((target/'unattended-profile-backup/ready.sha256').exists())
        self.assert_old()

    def test_publication_and_resume_keep_current_unchanged(self):
        def planned(s, root, fetcher, active):
            (root/'debian').mkdir(exist_ok=True)
            return {}, []
        def verified(root, s):
            update.profiles.generation(s, root)
            (root/'manifest.json').write_text('{"outcome": "verified"}')
            (root/'ready.sha256').write_text(''.join(f'{digest(p)}  {p.relative_to(root)}\n'
                                                   for p in root.rglob('*') if p.is_file()))
        with patch.object(update, 'plan', side_effect=planned), patch.object(update, 'acquire'), \
                patch.object(update, 'check_rotation'), patch.object(update.verifier, 'verify', side_effect=verified):
            update.refresh(self.s, 'new', False)
        self.assertTrue((self.base/'generations/new/ready.sha256').is_file())
        self.assertFalse((self.base/'.staging/new').exists())
        self.assertEqual((self.base/'generations/new/www').stat().st_mode & 0o777, 0o755)
        self.assert_old()
        self.s['generation'] = 'resume'
        with patch.object(update, 'plan', side_effect=InterruptedError('network lost')):
            with self.assertRaises(InterruptedError):
                update.refresh(self.s, 'resume', False)
        stage = self.base/'.staging/resume'
        self.assertTrue(stage.is_dir())
        self.assertFalse((stage/'ready.sha256').exists())
        with patch.object(update, 'plan', side_effect=planned), patch.object(update, 'acquire'), \
                patch.object(update, 'check_rotation'), patch.object(update.verifier, 'verify', side_effect=verified):
            update.refresh(self.s, 'resume', True)
        self.assertTrue((self.base/'generations/resume/ready.sha256').is_file())
        self.assert_old()

    def test_unimported_legacy_profile_and_space_fail_closed(self):
        (self.active/'unattended-profile-backup').mkdir()
        with self.assertRaises(ValueError):
            update.read_profiles(self.s, self.active)
        with patch.object(engine.shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(10, 9, 1)):
            with self.assertRaises(ValueError):
                engine.space(self.base, 2, 0)
        self.assert_old()


if __name__ == '__main__':
    unittest.main()
