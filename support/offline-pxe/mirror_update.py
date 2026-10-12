#!/usr/bin/env python3
"""Manual Wi-Fi refresh. No operation is scheduled; activation is separate."""
import argparse
import contextlib
import fcntl
import ipaddress
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from common import settings, digest
from mirror_acquire import (Fetcher, acquire, atomic_json, check_rotation, module,
                            name_ok, plan, space, verifier, GIB)

BASE = Path('/srv/offline')
RUN = Path('/run/offline-pxe')
RECORD = Path('/var/lib/offline-pxe/update-transaction.json')
SITE = Path('/etc/offline-pxe/settings.json')
SERVICES = ['offline-dnsmasq.service', 'offline-nginx.service', 'offline-recover.timer']
profiles = module('unattended_profiles', 'prepare-unattended.py')


def command(*args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, umask=0o022, **kwargs)


def output(*args):
    return subprocess.check_output(list(map(str, args)), text=True).strip()


def mounted(s, readonly=True):
    if output('findmnt', '-rn', '-M', BASE, '-o', 'UUID') != s['ssd_uuid']:
        raise ValueError('Mirror mount UUID differs from installed settings')
    if output('findmnt', '-rn', '-M', BASE, '-o', 'FSTYPE') != 'ext4':
        raise ValueError('Mirror must be an ext4 mount')
    if readonly and 'ro' not in output('findmnt', '-rn', '-M', BASE, '-o', 'OPTIONS').split(','):
        raise ValueError('Mirror must initially be mounted read-only')


def active_root():
    active = (BASE/'current').resolve(strict=True)
    if active.parent != BASE/'generations':
        raise ValueError('Active generation escapes generations directory')
    return active


def network(s):
    command('offline-ready', stdout=subprocess.DEVNULL)
    command('systemctl', 'is-active', '--quiet', 'iwd', 'systemd-resolved')
    addresses = json.loads(output('ip', '-j', '-4', 'address', 'show', 'dev', 'wlan0'))
    lan = ipaddress.ip_interface(s['server']).network
    if not addresses or not addresses[0].get('addr_info'):
        raise ValueError('Connect wlan0 with iwctl first')
    for entry in addresses[0]['addr_info']:
        if ipaddress.ip_interface(f"{entry['local']}/{entry['prefixlen']}").network.overlaps(lan):
            raise ValueError('Wi-Fi and PXE subnets overlap')
    routes = json.loads(output('ip', '-j', '-4', 'route', 'show', 'default'))
    if not routes or any(r.get('dev') != 'wlan0' for r in routes):
        raise ValueError('The upstream default route must use wlan0 exclusively')
    if not Path(s['keyring']).is_file():
        raise ValueError('Missing Debian archive keyring')


@contextlib.contextmanager
def lock():
    RUN.mkdir(parents=True, exist_ok=True)
    RUN.chmod(0o755)
    with (RUN/'activation.lock').open('w') as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def restore(s):
    """Called under the shared lock, on exit or by boot recovery; never downloads."""
    if not RECORD.exists():
        return
    record = json.loads(RECORD.read_text())
    if record['uuid'] != s['ssd_uuid'] or record['active'] != str(active_root()):
        raise ValueError('Interrupted update identity changed; inspect transaction before recovery')
    mounted(s, readonly=False)
    command('systemctl', 'stop', *SERVICES[:2])
    os.sync()
    command('mount', '-o', 'remount,ro', BASE)
    mounted(s)
    # offline-ready requires maintenance to be absent; restore marker on failure.
    (RUN/'maintenance').unlink(missing_ok=True)
    try:
        command('offline-ready', stdout=subprocess.DEVNULL, env={**os.environ, 'OFFLINE_UPDATE_RECOVERING': '1'})
    except BaseException:
        (RUN/'maintenance').touch()
        raise
    if any(unit not in SERVICES for unit in record['services']):
        raise ValueError('Invalid saved service state')
    RECORD.unlink()
    os.sync()
    # Restore the retry timer first so a transient daemon start failure remains
    # recoverable without leaving the old mirror permanently offline.
    for unit in sorted(record['services'], key=lambda unit: not unit.endswith('.timer')):
        command('systemctl', 'start', unit)


class UpdateLog:
    def __init__(self, terminal):
        self.terminal = terminal
        self.path = BASE/'.update.log'
        if self.path.is_symlink():
            raise ValueError('Unexpected log symlink')

    def write(self, text):
        self.terminal.write(text)
        if self.path.exists() and self.path.stat().st_size + len(text.encode()) > 1024**2:
            os.replace(self.path, BASE/'.update.log.previous')
        with self.path.open('a') as f:
            f.write(text)
        return len(text)

    def flush(self):
        self.terminal.flush()


@contextlib.contextmanager
def maintenance(s, action):
    if RECORD.exists() or (RUN/'maintenance').exists():
        raise ValueError('Unfinished maintenance; recover it before another operation')
    command('offline-ready', stdout=subprocess.DEVNULL)
    prior = [unit for unit in SERVICES if subprocess.run(
        ['systemctl', 'is-active', '--quiet', unit]).returncode == 0]
    # Persistent intent precedes any writable remount. A rootfs update also replaces
    # this record; normal boot always mounts the data partition read-only.
    atomic_json(RECORD, {'uuid': s['ssd_uuid'], 'active': str(active_root()),
                         'services': prior, 'action': action})
    (RUN/'maintenance').touch()
    try:
        command('systemctl', 'stop', 'offline-recover.timer', 'offline-recover.service')
        command('systemctl', 'stop', *SERVICES[:2])
        command('mount', '-o', 'remount,rw', BASE)
        with contextlib.redirect_stdout(UpdateLog(sys.stdout)):
            print('Operation:', action, datetime.now(timezone.utc).isoformat(), flush=True)
            try:
                yield
            except BaseException as error:
                print('Operation stopped:', str(error), flush=True)
                raise
            else:
                print('Operation completed; restoring read-only service.', flush=True)
    finally:
        # Do not let a second Ctrl-C interrupt restoration.
        for signum in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, signal.SIG_IGN)
        restore(s)


def private_root():
    root = BASE/'.private-profiles'
    if root.is_symlink():
        raise ValueError('Private profile directory must not be a symlink')
    return root


def read_profiles(s, active):
    private = private_root()
    config = private/'profiles.json'
    if not config.exists():
        # Detect legacy Dell as well as the two-profile deployment.
        if (active/'unattended-profile-backup').exists() or any(
                (active/'www/preseed'/name).exists() for name in ('dell.cfg', 'nvme.cfg', 'sata.cfg')):
            raise ValueError('Import both private source preseeds before refreshing an unattended generation')
        return None
    if private.stat().st_mode & 0o077:
        raise ValueError('Private profile directory must have mode 0700')
    meta = json.loads(config.read_text())
    if meta['default'] not in ('menu', 'guided', 'nvme', 'sata'):
        raise ValueError('Invalid saved profile default')
    result = {}
    for name in ('nvme', 'sata'):
        path = private/(name+'.cfg')
        if path.is_symlink() or path.stat().st_mode & 0o077 or digest(path) != meta['sha256'][name]:
            raise ValueError('Private source profile permissions/hash changed; reimport explicitly')
        result[name] = profiles.adapt(s, path.read_text(), name)
    return result, meta['default']


def import_profiles(s, paths, default):
    # Validate before stopping anything; no secret values in diagnostics.
    texts = {}
    for name, path in zip(('nvme', 'sata'), paths):
        p = Path(path)
        if p.stat().st_size > 1024**2:
            raise ValueError('Private input too large')
        texts[name] = p.read_text()
        profiles.adapt(s, texts[name], name)
    with maintenance(s, 'import-profiles'):
        root = private_root()
        root.mkdir(mode=0o700, exist_ok=True)
        root.chmod(0o700)
        hashes = {}
        for name, text in texts.items():
            target = root/(name+'.cfg')
            if target.is_symlink():
                raise ValueError('Private input destination is a symlink')
            temp = root/(name+'.new')
            temp.write_text(text)
            temp.chmod(0o600)
            os.replace(temp, target)
            hashes[name] = digest(target)
        atomic_json(root/'profiles.json', {'default': default, 'sha256': hashes})
    print('Private NVMe/SATA source profiles saved; they will be rendered for the next generation.')


def apply_profiles(s, root, selected):
    if selected is None:
        return
    # Preserve deployment rollback compatibility: snapshot original controls/seal
    # and track newly added files exactly as deploy-unattended.sh expects.
    backup = root/'unattended-profile-backup'
    backup.mkdir(mode=0o700)
    shutil.copyfile(root/'ready.sha256', backup/'ready.sha256')
    with tempfile.TemporaryDirectory(dir=root, prefix='.profile-') as tmp:
        temp = Path(tmp)
        profiles.render_profiles(s, selected[0], temp, selected[1])
        new = []
        changed = []
        for source in temp.rglob('*'):
            if not source.is_file() or source.name == 'settings.json':
                continue
            rel = source.relative_to(temp)
            dest = root/rel
            if dest.exists():
                old = backup/'original'/rel
                old.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(dest, old)
            else:
                new.append(str(rel))
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            dest.chmod(0o644)
            changed.append(str(rel))
        (backup/'new-files').write_text(''.join(n+'\n' for n in new))
        lines = [line for line in (root/'ready.sha256').read_text().splitlines()
                 if line.split('  ', 1)[1] not in changed]
        lines += [f'{digest(root/n)}  {n}' for n in changed]
        (root/'ready.sha256').write_text('\n'.join(lines)+'\n')


def clean_controls(root):
    # Only generated outputs in this unserved, validated staging directory.
    for name in ('tftp', 'www', 'unattended-profile-backup'):
        p = root/name
        if p.is_symlink():
            raise ValueError('Unexpected staging symlink')
        if p.exists():
            shutil.rmtree(p)
    for name in ('ready.sha256', 'manifest.json'):
        (root/name).unlink(missing_ok=True)


@contextlib.contextmanager
def temporary_storage(path):
    previous = tempfile.tempdir
    tempfile.tempdir = str(path)
    try:
        yield
    finally:
        tempfile.tempdir = previous


def refresh(s, generation, resume):
    active = active_root()
    selected_profiles = read_profiles(s, active)
    reserve = int(s['minimum_free_gib']) * GIB
    stage = BASE/'.staging'/generation
    final = BASE/'generations'/generation
    if final.exists() or final.is_symlink():
        raise ValueError('Generation already published; choose another name')
    if stage.is_symlink() or stage.parent.is_symlink():
        raise ValueError('Unexpected staging symlink')
    if stage.exists() != resume:
        raise ValueError('Use --resume for an existing staging generation')
    with maintenance(s, generation):
        stage.mkdir(parents=True, mode=0o700, exist_ok=True)
        saved = stage/'update-settings.json'
        if saved.exists() and json.loads(saved.read_text()) != s:
            raise ValueError('Settings changed since staging began; start a new generation')
        atomic_json(saved, s)
        clean_controls(stage)
        # Temp decompression data is on the mirror, never on rootfs or /run.
        scratch = stage/'.scratch'
        scratch.mkdir(exist_ok=True)
        with temporary_storage(scratch):
            fetcher = Fetcher({'debian': s['debian_upstream'], 'debian-security': s['security_upstream']}, BASE, reserve)
            atomic_json(stage/'acquisition.json', {'started': datetime.now(timezone.utc).isoformat(),
                        'method': 'Pi manual HTTPS refresh', 'debian_upstream': s['debian_upstream'],
                        'security_upstream': s['security_upstream']})
            for archive in ('debian', 'debian-security'):
                metadata = stage/archive/'dists'
                if metadata.is_symlink():
                    raise ValueError('Unexpected staging metadata symlink')
                if metadata.exists():
                    shutil.rmtree(metadata)
            files, releases = plan(s, stage, fetcher, active)
            acquire(files, stage, active, fetcher, reserve)
            check_rotation(s, stage, fetcher, releases)
            print('Verifying every selected package and installer artifact...', flush=True)
            verifier.verify(stage, s)
            apply_profiles(s, stage, selected_profiles)
            # Recheck at publication too: a full SD hash scan may cross a metadata update.
            check_rotation(s, stage, fetcher, releases)
            shutil.rmtree(scratch)
            (stage/'update-settings.json').unlink()
            # Exclude incomplete network retry files from publication.
            for p in stage.rglob('*'):
                if p.name.endswith(('.partial', '.partial.json', '.copy')):
                    p.unlink()
            # Private staging permissions must not leak into the published HTTP tree.
            for p in stage.rglob('*'):
                if p.is_symlink() or p.is_relative_to(stage/'unattended-profile-backup'):
                    continue
                p.chmod(0o755 if p.is_dir() else 0o644)
            stage.chmod(0o755)
            os.sync()
            os.rename(stage, final)
            os.sync()
    print(f'Verified generation: {generation}\nOld generation remains active. When no clients are installing, run:\n'
          f'offline-activate {generation} --no-active-installers')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--check', action='store_true')
    group.add_argument('--status', action='store_true')
    group.add_argument('--resume', metavar='GENERATION')
    group.add_argument('--recover', action='store_true', help='Recover interrupted maintenance locally; no downloads')
    group.add_argument('--import-profiles', nargs=2, metavar=('NVME_CFG', 'SATA_CFG'))
    parser.add_argument('--default', choices=('menu', 'guided', 'nvme', 'sata'), default='menu')
    parser.add_argument('--enable-destructive-profile', action='store_true')
    parser.add_argument('--no-active-installers', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run as root on Pi 5')
    os.umask(0o077)
    s = settings(SITE)
    # The image owns trust, not private site files or downloaded metadata.
    s['keyring'] = '/usr/share/keyrings/debian-archive-keyring.gpg'
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: (_ for _ in ()).throw(InterruptedError('Update interrupted; staging retained')))
    with lock():
        if args.recover:
            restore(s)
            return
        mounted(s)
        if args.status:
            print('Active:', active_root().name)
            print('Interrupted maintenance:', RECORD.exists())
            for p in sorted((BASE/'.staging').glob('*')):
                if p.is_dir():
                    print('Staging:', p.name)
            for p in sorted((BASE/'generations').glob('*')):
                if p.is_dir():
                    print('Generation:', p.name)
            print('Free bytes:', shutil.disk_usage(BASE).free)
            return
        if args.import_profiles:
            if not args.no_active_installers or not args.enable_destructive_profile:
                parser.error('Profile import requires --no-active-installers and --enable-destructive-profile')
            import_profiles(s, args.import_profiles, args.default)
            return
        if not args.check and not args.no_active_installers:
            parser.error('Refresh pauses PXE/HTTP; pass --no-active-installers during a maintenance window')
        if RECORD.exists() or (RUN/'maintenance').exists():
            raise ValueError('Recover unfinished maintenance first with --recover')
        network(s)
        s['generation'] = name_ok(args.resume or datetime.now(timezone.utc).strftime('trixie-%Y%m%dT%H%M%SZ'))
        if args.check:
            # Only indexes during planning; no installer tarball or pool downloads.
            with tempfile.TemporaryDirectory(prefix='mirror-plan-', dir=RUN) as tmp:
                fetcher = Fetcher({'debian': s['debian_upstream'], 'debian-security': s['security_upstream']}, RUN)
                files, _ = plan(s, Path(tmp), fetcher, active_root(), check_only=True)
                required = sum(size for size, _ in files.values()) + GIB
                reserve = int(s['minimum_free_gib'])*GIB
                print(f'Complete package files: {len(files)}\nNew generation estimate (including 1 GiB overhead): {required}\n'
                      f'Reserve: {reserve}\nAvailable: {shutil.disk_usage(BASE).free}')
                read_profiles(s, active_root())
                space(BASE, required, reserve)
                print('PASS: upstream verification and capacity checks; no packages downloaded.')
        else:
            print('Staging generation:', s['generation'], flush=True)
            refresh(s, s['generation'], bool(args.resume))


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        # Avoid tracebacks containing private preseed local variables.
        print(f'offline-mirror-update: {error}', file=__import__('sys').stderr)
        raise SystemExit(1)
