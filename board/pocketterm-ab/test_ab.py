#!/usr/bin/env python3
import copy
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import common
import control

class ABTests(unittest.TestCase):
    def setUp(self):
        self.images = {n: n.encode() for n in ('boot-a.vfat', 'boot-b.vfat', 'rootfs.ext4')}
        self.meta = common.metadata('test-1', self.images)

    def test_real_signed_bundle_and_tamper(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            private, public = folder / 'private.pem', folder / 'public.pem'
            subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt',
                            'rsa_keygen_bits:2048', '-out', str(private)],
                           check=True, stderr=subprocess.DEVNULL)
            subprocess.run(['openssl', 'pkey', '-in', str(private), '-pubout', '-out', str(public)],
                           check=True)
            for name, data in self.images.items():
                (folder / name).write_bytes(data)
            (folder / 'release-version').write_text('test-1')
            (folder / 'release-profile').write_text(common.PROFILE)
            bundle = folder / 'release.swu'
            subprocess.run([sys.executable, str(Path(__file__).with_name('package.py')),
                            '--images', str(folder), '--key', str(private),
                            '--version', 'test-1', '--output', str(bundle)], check=True)
            entries = common.archive_read(bundle)
            (folder / 'release-profile').write_text('reterminal-cm4-lvgl-v1')
            rejected = subprocess.run([sys.executable, str(Path(__file__).with_name('package.py')),
                '--images', str(folder), '--key', str(private), '--version', 'test-1',
                '--output', str(folder / 'wrong.swu')], capture_output=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn(b'wrong build profile', rejected.stderr)
            self.assertFalse((folder / 'wrong.swu').exists())
            for name, signature in [('sw-description', 'sw-description.sig'), ('release.json', 'release.sig')]:
                data, sig = folder / 'input', folder / 'sig'
                sig.write_bytes(entries[signature])
                command = ['openssl', 'dgst', '-sha256', '-verify', str(public),
                           '-signature', str(sig), str(data)]
                data.write_bytes(entries[name])
                subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
                data.write_bytes(entries[name] + b'tampered')
                self.assertNotEqual(subprocess.run(command, stdout=subprocess.DEVNULL,
                                                   stderr=subprocess.DEVNULL).returncode, 0)

    def test_manifest_fixed_devices_and_selections(self):
        desc = common.description(self.meta)
        self.assertEqual(desc.count(b'device = "/dev/ab-boot"'), 2)
        self.assertEqual(desc.count(b'device = "/dev/ab-root"'), 2)
        for key, value in [('profile', 'other-board'), ('layout', 2), ('version', 'bad";')]:
            meta = dict(self.meta, **{key: value})
            with self.assertRaises((AssertionError, ValueError)):
                common.description(meta)
        self.meta['payloads']['boot-a.vfat']['size'] = 129 * 1024**2
        with self.assertRaises(AssertionError):
            common.description(self.meta)

    def test_archive_roundtrip_and_duplicate_rejection(self):
        entries = [('sw-description', common.description(self.meta)), ('sw-description.sig', b'sig'),
                   ('release.json', json.dumps(self.meta).encode()), ('release.sig', b'sig'), *self.images.items()]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bundle.swu'
            common.archive_write(path, entries)
            self.assertEqual(common.archive_read(path), dict(entries))
            for bad in [entries + [entries[-1]], entries + [('../escape', b'evil')]]:
                common.archive_write(path, bad)
                with self.assertRaises(AssertionError):
                    common.archive_read(path)
            path.write_bytes(b'070701')
            with self.assertRaises(AssertionError):
                common.archive_read(path)

    def test_trial_and_mounted_target_rejected_before_bundle_open(self):
        parts = [{'mountpoints': []} for _ in range(6)]
        with patch.object(control, 'SELECTOR') as selector:
            selector.read_bytes.return_value = control.selector('a')
            with self.assertRaises(AssertionError):
                control.install('not-opened', parts, 'a', True, {})
            parts[4]['mountpoints'] = ['/mnt/target']
            with self.assertRaises(AssertionError):
                control.install('not-opened', parts, 'a', False, {})

    def test_clone_and_firmware_root_mismatch(self):
        nodes = [dict(name=f'/dev/mmcblk0p{i+1}', type='part', pkname='/dev/mmcblk0', partuuid=u,
                      partn=i+1, size=common.SIZES[i]*1024**2,
                      mountpoints=['/'] if i == 3 else []) for i,u in enumerate(common.UUIDS)]
        nodes.append(dict(name='/dev/mmcblk0', type='disk', tran='mmc'))
        with patch.object(control, 'tree', return_value=nodes), patch.object(Path, 'read_text', return_value='SD'), patch.object(Path, 'read_bytes', side_effect=[b'\0\0\0\2', b'\0\0\0\1', b'\0\0\0\0']):
            _, slot, trial = control.inspect()
            self.assertEqual((slot, trial), ('a', False))
        with patch.object(control, 'tree', return_value=nodes + [copy.deepcopy(nodes[0])]):
            with self.assertRaisesRegex(AssertionError, 'cloned'):
                control.inspect()
        with patch.object(control, 'tree', return_value=nodes), patch.object(Path, 'read_text', return_value='SD'), patch.object(Path, 'read_bytes', return_value=b'\0\0\0\3'):
            with self.assertRaisesRegex(AssertionError, 'mismatch'):
                control.inspect()

    def test_usb_root_uses_actual_parent_and_checks_boot_transport(self):
        for disk, slot, partition, root in [('sda', 'a', 2, 3), ('sdc', 'b', 3, 4)]:
            nodes = [dict(name=f'/dev/{disk}{i+1}', type='part', pkname=f'/dev/{disk}', partuuid=u,
                          partn=i+1, size=common.SIZES[i]*1024**2,
                          mountpoints=['/'] if i == root else []) for i,u in enumerate(common.UUIDS)]
            nodes.append(dict(name=f'/dev/{disk}', type='disk', tran='usb'))
            for mode in (4, 5):
                values = [partition.to_bytes(4, 'big'), mode.to_bytes(4, 'big'), bytes(4)]
                with patch.object(control, 'tree', return_value=nodes), patch.object(Path, 'read_bytes', side_effect=values):
                    parts, actual, trial = control.inspect()
                    self.assertEqual((actual, trial), (slot, False))
                    self.assertTrue(all(p['pkname'] == f'/dev/{disk}' for p in parts))
            with patch.object(control, 'tree', return_value=nodes), patch.object(Path, 'read_bytes', side_effect=[partition.to_bytes(4, 'big'), (1).to_bytes(4, 'big')]):
                with self.assertRaisesRegex(AssertionError, 'transport mismatch'):
                    control.inspect()
            nodes[0]['pkname'] = '/dev/sdz'
            with patch.object(control, 'tree', return_value=nodes):
                with self.assertRaises(AssertionError):
                    control.inspect()

    def test_expanded_data_is_accepted_but_slot_sizes_stay_fixed(self):
        nodes = [dict(name=f'/dev/sda{i+1}', type='part', pkname='/dev/sda', partuuid=u,
                      partn=i+1, size=common.SIZES[i]*1024**2,
                      mountpoints=['/'] if i == 3 else []) for i,u in enumerate(common.UUIDS)]
        nodes.append(dict(name='/dev/sda', type='disk', tran='usb'))
        nodes[5]['size'] = 28*1024**3
        with patch.object(control, 'tree', return_value=nodes), patch.object(Path, 'read_bytes', side_effect=[(2).to_bytes(4,'big'),(5).to_bytes(4,'big'),bytes(4)]):
            self.assertEqual(control.inspect()[1:], ('a',False))
        for index in (0,1,2,3,4,5):
            bad=copy.deepcopy(nodes)
            bad[index]['size'] = common.SIZES[index]*1024**2-512
            with patch.object(control, 'tree', return_value=bad):
                with self.assertRaises(AssertionError):
                    control.inspect()

    def test_emmc_nvme_and_sata_are_rejected(self):
        with patch.object(Path, 'read_text', return_value='MMC'):
            with self.assertRaisesRegex(AssertionError, 'not eMMC'):
                control.check_transport([dict(name='/dev/mmcblk0', type='disk', tran='mmc')], '/dev/mmcblk0')
        for name, tran in [('/dev/sda', 'sata'), ('/dev/nvme0n1', 'nvme')]:
            with self.assertRaisesRegex(AssertionError, 'unsupported storage'):
                control.check_transport([dict(name=name, type='disk', tran=tran)], name)

    def test_disk_staging_roundtrip_and_truncation(self):
        entries = [('sw-description', common.description(self.meta)), ('sw-description.sig', b'sig'),
                   ('release.json', json.dumps(self.meta).encode()), ('release.sig', b'sig'), *self.images.items()]
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            original = folder / 'original.swu'
            common.archive_write(original, entries)
            staged = common.archive_read(original, folder)
            self.assertIsInstance(staged['rootfs.ext4'], Path)
            self.assertEqual(common.metadata('test-1', {n:staged[n] for n in self.images}), self.meta)
            snapshot = folder / 'snapshot.swu'
            common.archive_write(snapshot, list(staged.items()))
            self.assertEqual(common.archive_read(snapshot), dict(entries))
            original.write_bytes(original.read_bytes()[:-300])
            with self.assertRaises(AssertionError):
                common.archive_read(original)

    def test_postbuild_removes_old_boot_mount_and_preserves_other_entries(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            target, build, images = folder / 'target', folder / 'build', folder / 'images'
            (target / 'etc').mkdir(parents=True)
            images.mkdir()
            ssl = target / 'usr/lib/python3.14/lib-dynload/_ssl.cpython-test.so'
            ssl.parent.mkdir(parents=True)
            ssl.write_bytes(b'test fixture')
            for name in ('openssl', 'lsblk', 'swupdate', 'sfdisk', 'partx', 'blockdev', 'resize2fs'):
                binary = target / 'usr/bin' / name
                binary.parent.mkdir(parents=True, exist_ok=True)
                binary.write_text('#!/bin/sh\nexit 0\n')
                binary.chmod(0o755)
            config = build / 'swupdate-2026.05.1/.config'
            config.parent.mkdir(parents=True)
            config.write_text(''.join('CONFIG_' + key + '=y\n' for key in
                ('SSL_IMPL_OPENSSL', 'HASH_VERIFY', 'SIGNED_IMAGES', 'SIGALG_RAWRSA', 'HW_COMPATIBILITY', 'LIBCONFIG', 'RAW')))
            private, public = folder / 'key.pem', folder / 'public.pem'
            subprocess.run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(private)], check=True, stderr=subprocess.DEVNULL)
            subprocess.run(['openssl','pkey','-in',str(private),'-pubout','-out',str(public)], check=True)
            fstab = target / 'etc/fstab'
            keep = '/dev/root / auto rw 0 1\n# /boot is controller managed\ntmpfs /tmp tmpfs defaults 0 0\n'
            fstab.write_text(keep + 'PARTUUID=72657465-01 /boot vfat rw,defaults 0 2\n')
            environment = dict(os.environ, AB_RELEASE_VERSION='test-1', AB_VERIFY_KEY=str(public),
                               BUILD_DIR=str(build), BINARIES_DIR=str(images))
            script = Path(__file__).with_name('post-build.sh')
            for _ in range(2):
                subprocess.run(['sh', str(script), str(target)], env=environment, check=True)
                self.assertEqual(fstab.read_text(), keep)
            installed = target / 'usr/lib/pocketterm-ab/control.py'
            self.assertIn('check_transport', installed.read_text())
            self.assertEqual(installed.read_bytes(), Path(__file__).with_name('control.py').read_bytes())
            self.assertTrue((target / 'usr/lib/pocketterm-ab/api_service.py').is_file())
            self.assertFalse((target / 'etc/systemd/system/multi-user.target.wants/pocketterm-update-api.service').exists())
            ssl.unlink()
            rejected = subprocess.run(['sh', str(script), str(target)], env=environment, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn('Missing Python _ssl extension', rejected.stderr)

    def test_data_mount_accepts_only_verified_persistence_binds(self):
        from types import SimpleNamespace
        part = dict(name='/dev/sdc6', mountpoints=['/data', *control.PERSISTENT_PATHS])
        records = [dict(device='8:38', root='/', target='/data', kind='ext4')]
        records += [dict(device='8:38', root='/persist'+p, target=p, kind='ext4')
                    for p in control.PERSISTENT_PATHS]
        with patch.object(control.os, 'stat', return_value=SimpleNamespace(st_rdev=os.makedev(8,38))), patch.object(control, 'run') as run:
            with patch.object(control, 'mount_table', return_value=records):
                for _ in range(3):
                    control.mount(part, '/data', 'ext4')
                run.assert_not_called()
            for field, value in [('root', '/wrong-directory'), ('device', '8:39'),
                                 ('kind', 'vfat'), ('target', '/mnt/other')]:
                bad = copy.deepcopy(records)
                bad[1][field] = value
                with patch.object(control, 'mount_table', return_value=bad):
                    with self.assertRaisesRegex(AssertionError, 'unexpected mount'):
                        control.mount(part, '/data', 'ext4')
            with patch.object(control, 'mount_table', return_value=records + [records[1]]):
                with self.assertRaisesRegex(AssertionError, 'stacked'):
                    control.mount(part, '/data', 'ext4')

    def test_mount_checks_source_after_mounting(self):
        from types import SimpleNamespace
        part = dict(name='/dev/sdc1', mountpoints=[])
        correct = [dict(device='8:33', root='/', target='/selector', kind='vfat')]
        with patch.object(control.os, 'stat', return_value=SimpleNamespace(st_rdev=os.makedev(8,33))), patch.object(control, 'run') as run:
            with patch.object(control, 'mount_table', side_effect=[[], correct]):
                control.mount(part, '/selector', 'vfat')
                run.assert_called_once_with('mount', '-t', 'vfat', '/dev/sdc1', '/selector')
            wrong = [dict(correct[0], device='8:34')]
            with patch.object(control, 'mount_table', return_value=wrong):
                with self.assertRaisesRegex(AssertionError, 'unexpected mount'):
                    control.mount(part, '/selector', 'vfat')

    def test_failure_reset_only_reboots_a_trial(self):
        for trial in (0, 1):
            with patch.object(sys, 'argv', ['pocketterm-update', 'failure-reset']), patch.object(control.os, 'geteuid', return_value=0), patch.object(Path, 'read_bytes', return_value=trial.to_bytes(4, 'big')), patch.object(control, 'run') as run:
                control.main()
                if trial:
                    run.assert_called_once_with('systemctl', 'reboot')
                else:
                    run.assert_not_called()

    def test_normal_candidate_requires_prior_health_authorization(self):
        state = dict(phase='pending', previous='a', target='b', version='test-1')
        with patch.object(Path, 'read_text', return_value='test-1'), patch.object(control, 'SELECTOR') as selector:
            selector.read_bytes.return_value = control.selector('b')
            with self.assertRaisesRegex(AssertionError, 'health authorization'):
                control.boot('b', False, state)

    def test_commit_recovery_and_fallback_replay(self):
        state = dict(phase='committing', previous='a', target='b', version='test-1')
        for slot, phase in [('a', 'fallback'), ('b', 'committed')]:
            with patch.object(Path, 'read_text', return_value='test-1'), patch.object(control, 'SELECTOR') as selector, patch.object(control, 'record') as record:
                selector.read_bytes.return_value = control.selector(slot)
                control.boot(slot, False, state)
                self.assertEqual(record.call_args.args[0]['phase'], phase)

class GrowthTests(unittest.TestCase):
    def layout(self):
        entries = []
        start = 2048
        for i, (size, uid) in enumerate(zip(common.SIZES, common.UUIDS)):
            entries.append(dict(node=f'/dev/test{i+1}', start=start, size=size*2048, uuid=uid))
            start += size*2048
        return dict(label='gpt', unit='sectors', sectorsize=512, id='disk-id',
                    firstlba=34, lastlba=start+100, partitions=entries)

    def test_grow_only_data_and_retry_after_interruption(self):
        import grow
        before = self.layout()
        relocated = copy.deepcopy(before)
        relocated['lastlba'] += 50_000_000
        after = copy.deepcopy(relocated)
        after['partitions'][5]['size'] = after['lastlba']-after['partitions'][5]['start']+1
        grow.check_preserved(before, after)
        parts = [{} for _ in range(5)] + [dict(pkname='/dev/test', name='/dev/test6', mountpoints=['/data'])]
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            marker=folder/'marker';backup=folder/'backup';done=folder/'done'
            marker.write_text(f'{common.PROFILE} {common.LAYOUT}\n')
            with patch.object(grow, 'MARKER', marker), patch.object(grow, 'BACKUP', backup), patch.object(grow, 'DONE', done), patch.object(grow.os, 'sync'), patch.object(grow.subprocess, 'check_output', return_value=str(after['partitions'][5]['size']*512).encode()):
                def interrupted(*args, **kwargs):
                    if args[0]=='resize2fs':
                        raise RuntimeError('power interruption')
                with patch.object(grow, 'table', side_effect=[before, relocated, after]):
                    with self.assertRaisesRegex(RuntimeError, 'interruption'):
                        grow.grow_factory_data(parts, 'a', False, {}, interrupted, control.atomic)
                self.assertTrue(marker.exists())
                self.assertFalse(done.exists())
                with patch.object(grow, 'table', side_effect=[after, after, after]):
                    from unittest.mock import Mock
                    runner=Mock()
                    grow.grow_factory_data(parts, 'a', False, {}, runner, control.atomic)
                    self.assertFalse(any('-N' in call.args for call in runner.call_args_list))
                    self.assertIn(('resize2fs', '/dev/test6'), [call.args for call in runner.call_args_list])
                self.assertFalse(marker.exists())
                self.assertEqual(json.loads(done.read_text())['bytes'], after['partitions'][5]['size']*512)
                from unittest.mock import Mock
                runner=Mock()
                grow.grow_factory_data(parts, 'a', False, {}, runner, control.atomic)
                runner.assert_not_called()

    def test_growth_rejects_unknown_layout_or_nonfactory_boot(self):
        import grow
        original=self.layout()
        for i in range(5):
            changed=copy.deepcopy(original)
            changed['partitions'][i]['size'] += 1
            with self.assertRaises(AssertionError):
                grow.check_preserved(original, changed)
        extra=copy.deepcopy(original)
        extra['partitions'].append(dict(original['partitions'][5]))
        with self.assertRaises(AssertionError):
            grow.validate_table(extra)
        with tempfile.TemporaryDirectory() as folder:
            marker=Path(folder)/'marker';marker.write_text(f'{common.PROFILE} {common.LAYOUT}\n')
            with patch.object(grow, 'MARKER', marker):
                for slot,trial,state in [('b',False,{}),('a',True,{}),('a',False,{'phase':'committed'})]:
                    with self.assertRaisesRegex(AssertionError, 'initial factory'):
                        grow.grow_factory_data([],slot,trial,state,None,None)

if __name__ == '__main__':
    unittest.main()
