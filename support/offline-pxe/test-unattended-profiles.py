#!/usr/bin/env python3
"""No real credentials, disks, mounts or services are used by these tests."""
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from common import settings
from render import generation

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('profiles', BASE/'prepare-unattended.py')
profiles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profiles)


def private_input(disk):
    return f'''d-i partman-auto/disk string {disk}
d-i grub-installer/bootdev string {disk}
d-i partman-auto/method string crypto
d-i partman/confirm boolean true
d-i partman/confirm_nooverwrite boolean true
d-i partman-partitioning/confirm_write_new_label boolean true
d-i partman-crypto/passphrase password fixture-only-not-a-secret
d-i partman-crypto/passphrase-again password fixture-only-not-a-secret
d-i passwd/username string fixtureuser
d-i passwd/user-password password fixture-only-not-a-secret
d-i passwd/user-password-again password fixture-only-not-a-secret
d-i netcfg/hostname string fixturehost
d-i mirror/http/hostname string deb.debian.org
d-i clock-setup/ntp boolean true
tasksel tasksel/first multiselect standard, ssh-server
d-i preseed/late_command string in-target usermod -a -G sudo fixtureuser
'''


class Profiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='profiles-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.site = settings(BASE/'settings.json')
        self.inputs = {}
        for name, disk in [('nvme', '/dev/nvme0n1'), ('sata', '/dev/sda')]:
            path = self.root/(name+'.cfg')
            path.write_text(private_input(disk))
            self.inputs[name] = path

    def test_adaptation_and_disk_types(self):
        for name, path in self.inputs.items():
            result, disk, host, late = profiles.adapt(self.site, path.read_text(), name)
            data = profiles.parse(result)
            self.assertNotIn('deb.debian.org', result)
            self.assertEqual(data['d-i', 'clock-setup/ntp'], ('boolean', 'false'))
            self.assertEqual(data['d-i', 'passwd/username'][1], 'fixtureuser')
            self.assertIn(f'/preseed/{name}-early.sh', result)
            self.assertIn('partman/early_command', result)
            with self.assertRaises(ValueError):
                profiles.adapt(self.site, path.read_text(), 'sata' if name == 'nvme' else 'nvme')

    def make_bundle(self, default='menu'):
        bundle = self.root/('bundle-'+default)
        profiles.build(self.site, self.inputs, bundle, default)
        expanded = self.root/('expanded-'+default)
        expanded.mkdir()
        with tarfile.open(bundle/'unattended-profile.tar.gz') as t:
            t.extractall(expanded, filter='data')
        subprocess.run(['sha256sum', '--quiet', '-c', 'payload.sha256'], cwd=expanded, check=True)
        self.assertEqual(bundle.stat().st_mode & 0o777, 0o700)
        self.assertEqual((bundle/'unattended-profile.tar.gz').stat().st_mode & 0o777, 0o600)
        return bundle, expanded

    def test_menus_and_permissions(self):
        for default in ['menu', 'nvme', 'sata']:
            bundle, expanded = self.make_bundle(default)
            grub = (expanded/'tftp/debian-installer/amd64/grub/grub.cfg').read_text()
            bios = (expanded/'tftp/debian-installer/amd64/boot-screens/syslinux.cfg').read_text()
            self.assertIn('UI menu.c32', bios)
            for name in ['nvme', 'sata']:
                self.assertIn('--id '+name, grub)
                self.assertIn('LABEL '+name, bios)
                self.assertIn('/preseed/'+name+'.cfg', grub)
            self.assertIn('set timeout=-1' if default == 'menu' else 'set default='+default, grub)
            self.assertNotIn('dell.cfg', grub)
            for path in expanded.rglob('*.sh'):
                subprocess.run(['sh', '-n', str(path)], check=True)

    def test_deployment_and_rollback(self):
        bundle, expanded = self.make_bundle()
        root = self.root/'pi'
        g = root/'srv/offline/generations'/self.site['generation']
        generation(self.site, g)
        original = {str(p.relative_to(g)): p.read_bytes() for p in g.rglob('*') if p.is_file()}
        (g/'ready.sha256').write_text(''.join(hashlib.sha256(v).hexdigest()+'  '+k+'\n' for k,v in original.items()))
        (root/'srv/offline/current').symlink_to('generations/'+self.site['generation'])
        (root/'etc/offline-pxe').mkdir(parents=True)
        (root/'etc/offline-pxe/runtime.conf').write_text("SSD_UUID='fixture'\nSERVER='192.168.50.1'\n")
        bins = root/'bin'; bins.mkdir()
        for name, body in {'id':'echo 0', 'findmnt':'echo fixture', 'mount':'exit 0', 'systemctl':'exit 0',
                           'offline-ready':'exit "${TEST_READY_FAIL:-0}"', 'sync':'exit 0'}.items():
            p = bins/name; p.write_text('#!/bin/sh\n'+body+'\n'); p.chmod(0o755)
        script = bundle/'fixture-deploy.sh'
        script.write_text((BASE/'deploy-unattended.sh').read_text().replace('/srv/offline', str(root/'srv/offline')).replace(
            '/run/', str(root/'run')+'/').replace('/etc/offline-pxe', str(root/'etc/offline-pxe')).replace(
            '/usr/sbin/offline-ready', str(bins/'offline-ready')))
        env = dict(os.environ, PATH=str(bins)+':'+os.environ['PATH'])
        failure = subprocess.run(['sh', str(script), '--enable-destructive-profile'], env=dict(env, TEST_READY_FAIL='1'))
        self.assertNotEqual(failure.returncode, 0)
        self.assertFalse((g/'unattended-profile-backup').exists())
        subprocess.run(['sh', str(script), '--enable-destructive-profile'], env=env, check=True)
        self.assertTrue((g/'www/preseed/nvme.cfg').exists())
        self.assertTrue((g/'www/preseed/sata.cfg').exists())
        subprocess.run(['sh', str(script), '--disable'], env=env, check=True)
        for name, content in original.items(): self.assertEqual((g/name).read_bytes(), content)
        self.assertFalse((g/'www/preseed/nvme.cfg').exists())
        subprocess.run(['sha256sum', '--quiet', '-c', 'ready.sha256'], cwd=g, check=True)

    def test_manual_acknowledgement_survives_rtc_retry(self):
        root = self.root/'rtc'; root.mkdir()
        marker = root/'ready'; marker.touch()
        bins = root/'bin'; bins.mkdir()
        for name, body in {'id':'echo 0', 'hwclock':'exit 99'}.items():
            p=bins/name; p.write_text('#!/bin/sh\n'+body+'\n'); p.chmod(0o755)
        script=root/'rtc.sh'
        script.write_text((BASE/'runtime-rtc.sh').read_text().replace('/run/offline-clock-ready', str(marker)).replace(
            '/sys/class/rtc/rtc0/name', str(root/'missing-device')))
        subprocess.run(['sh', str(script), '--restore'], env=dict(os.environ, PATH=str(bins)+':'+os.environ['PATH']), check=True)
        self.assertTrue(marker.exists())

    def test_offline_clock_can_trigger_recovery_with_failed_rtc(self):
        root = self.root/'clock-recovery'; root.mkdir()
        marker = root/'ready'
        unit = root/'offline-rtc.service'; unit.touch()
        bins = root/'bin'; bins.mkdir()
        rtc = root/'rtc.sh'
        rtc.write_text((BASE/'runtime-rtc.sh').read_text().replace('/run/offline-clock-ready', str(marker)).replace(
            '/sys/class/rtc/rtc0/name', str(root/'missing-rtc')))
        clock = root/'clock.sh'
        clock.write_text((BASE/'runtime-clock.sh').read_text().replace('/run/offline-clock-ready', str(marker)).replace(
            '/etc/systemd/system/offline-rtc.service', str(unit)))
        for name, body in {
            'id':'echo 0', 'date':'echo 1791700000', 'hwclock':'exit 99',
            'systemctl':'if [ "$1" = start ]; then sh "$RTC_TEST_SCRIPT" --restore; fi',
        }.items():
            p=bins/name; p.write_text('#!/bin/sh\n'+body+'\n'); p.chmod(0o755)
        env=dict(os.environ, PATH=str(bins)+':'+os.environ['PATH'], RTC_TEST_SCRIPT=str(rtc))
        subprocess.run(['sh', str(clock), '2026-10-11 06:00:00'], env=env, check=True)
        self.assertTrue(marker.exists())


if __name__ == '__main__':
    unittest.main()
