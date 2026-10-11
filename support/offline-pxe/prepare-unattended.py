#!/usr/bin/env python3
"""Adapt a private preseed to the verified offline mirror; emit a Pi deployment bundle."""
import argparse
import hashlib
import re
import tarfile
import tempfile
from pathlib import Path
from common import settings, write
from render import generation


def parse(text):
    records = {}
    logical = ''
    for line in text.splitlines():
        if not logical and (not line.strip() or line.lstrip().startswith('#')):
            continue
        if line.rstrip().endswith('\\'):
            logical += line.rstrip()[:-1] + ' '
            continue
        line = logical + line
        logical = ''
        fields = line.split(None, 3)
        if len(fields) < 3:
            raise ValueError('Invalid preseed line (contents withheld)')
        owner, key, kind = fields[:3]
        if (owner, key) in records:
            raise ValueError('Duplicate preseed key: ' + key)
        records[owner, key] = (kind, fields[3] if len(fields) == 4 else '')
    if logical:
        raise ValueError('Unfinished preseed continuation')
    return records


def adapt(s, text, profile_name):
    if profile_name not in ('nvme', 'sata'):
        raise ValueError('Profile must be nvme or sata')
    records = parse(text)
    def value(key):
        return records.get(('d-i', key), ('', ''))[1]
    disk = value('partman-auto/disk')
    if not re.fullmatch(r'/dev/(?:nvme[0-9]+n[0-9]+|sd[a-z]+)', disk):
        raise ValueError('An explicit whole target disk is required')
    if value('grub-installer/bootdev') != disk:
        raise ValueError('GRUB and partitioning target disks must match')
    pattern = r'/dev/nvme[0-9]+n[0-9]+' if profile_name == 'nvme' else r'/dev/sd[a-z]+'
    if not re.fullmatch(pattern, disk):
        raise ValueError('Selected disk does not match profile storage type')
    hostname = value('netcfg/hostname') or value('netcfg/get_hostname')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9-]{0,62}', hostname):
        raise ValueError('Explicit hostname required')
    if not value('passwd/username'):
        raise ValueError('Explicit username required')
    if not (value('passwd/user-password-crypted') or
            (value('passwd/user-password') and value('passwd/user-password') == value('passwd/user-password-again'))):
        raise ValueError('Complete user credentials required')
    if value('partman-auto/method') == 'crypto':
        if not value('partman-crypto/passphrase') or value('partman-crypto/passphrase') != value('partman-crypto/passphrase-again'):
            raise ValueError('Matching encryption passphrases required')
    for key in ('partman/confirm', 'partman/confirm_nooverwrite', 'partman-partitioning/confirm_write_new_label'):
        if value(key) != 'true':
            raise ValueError('Unattended disk confirmation missing: ' + key)
    if value('preseed/early_command') or value('partman/early_command'):
        raise ValueError('Custom early hooks require manual integration with the offline policy')
    # Never copy Internet mirror selections, public NTP, or public source generators.
    late = value('preseed/late_command')
    selected = {k: v for k, v in records.items() if not (
        k[1].startswith(('mirror/', 'apt-setup/', 'clock-setup/ntp', 'preseed/')))}
    base = Path(__file__).parent
    template = (base/'preseed/offline.cfg.in').read_text()
    for key, val in [('ADDRESS', s['address']), ('CODENAME', s['codename']), ('COMPONENTS', ' '.join(s['components']))]:
        template = template.replace('@'+key+'@', val)
    # Appliance constraints override mirror/clock/profile hooks, not requested tasks/accounts.
    selected.update(parse(template))
    a = s['address']
    selected['d-i', 'netcfg/get_nameservers'] = ('string', a)
    selected['d-i', 'netcfg/no_default_route'] = ('boolean', 'true')
    # Storage detection may not have run during preseed/early_command.
    selected['d-i', 'partman/early_command'] = ('string', f'[ -b {disk} ] || {{ echo "Configured install disk is absent" >&2; exit 1; }}')
    selected['d-i', 'preseed/early_command'] = ('string', f'wget -O /tmp/{profile_name}-early.sh http://{a}/preseed/{profile_name}-early.sh && OFFLINE_UNATTENDED=1 sh /tmp/{profile_name}-early.sh')
    selected['d-i', 'preseed/late_command'] = ('string', f'wget -O /tmp/{profile_name}-late.sh http://{a}/preseed/{profile_name}-late.sh && sh /tmp/{profile_name}-late.sh')
    result = '#_preseed_V1\n# PRIVATE: automatic disk replacement; generated for the isolated offline LAN.\n'
    result += ''.join(f'{owner} {key} {kind} {val}\n' for (owner, key), (kind, val) in selected.items())
    return result, disk, hostname, late


def build(s, inputs, output, default='menu'):
    profiles = {name: adapt(s, path.read_text(), name) for name, path in inputs.items()}
    output = output.resolve()
    repo = Path(__file__).resolve().parents[2]
    if output.is_relative_to(repo) or output.exists():
        raise ValueError('Output must be a new private directory outside rpi-extree')
    for source in inputs.values():
        if source.resolve().is_relative_to(repo):
            raise ValueError('Private preseed inputs must be outside rpi-extree')
    output.mkdir(parents=True, mode=0o700)
    base = Path(__file__).parent
    with tempfile.TemporaryDirectory(prefix='offline-unattended-') as d:
        root = Path(d)
        generation(s, root)
        early = (root/'www/preseed/early.sh').read_text()
        grub = root/'tftp/debian-installer/amd64/grub/grub.cfg'
        grub_text = grub.read_text().replace('set timeout=10', 'set timeout=-1' if default == 'menu' else 'set timeout=10')
        if default in profiles:
            grub_text = grub_text.replace('set default=0', 'set default='+default)
        bios = root/'tftp/debian-installer/amd64/boot-screens/syslinux.cfg'
        bios_text = bios.read_text().replace('PROMPT 1', 'PROMPT 0').replace('TIMEOUT 100', 'TIMEOUT 0' if default == 'menu' else 'TIMEOUT 100')
        bios_text = bios_text.replace('SAY Enter offline (guided) or interactive; disk changes always require confirmation.',
            'PATH debian-installer/amd64/boot-screens/\nUI menu.c32\nMENU TITLE Offline Debian installation')
        if default in profiles:
            bios_text = bios_text.replace('DEFAULT offline', 'DEFAULT '+default)
        for name, (profile, disk, hostname, late) in profiles.items():
            write(root, f'www/preseed/{name}.cfg', profile)
            write(root, f'www/preseed/{name}-early.sh', early, 0o755)
            late_script = (root/'www/preseed/late.sh').read_text()
            if late:
                late_script += '\n# Private final setup, after local APT configuration.\n' + late + '\n'
            write(root, f'www/preseed/{name}-late.sh', late_script, 0o755)
            args = (f'auto=true priority=critical interface=auto netcfg/get_nameservers={s["address"]} '
                    f'netcfg/no_default_route=true netcfg/get_hostname={hostname} netcfg/hostname={hostname} '
                    f'netcfg/get_domain= preseed/url=http://{s["address"]}/preseed/{name}.cfg')
            label = 'NVMe' if name == 'nvme' else 'SATA'
            grub_text += f"\nmenuentry '{label} unattended - ERASE {disk}' --id {name} {{\n linux /debian-installer/amd64/linux {args} ---\n initrd /debian-installer/amd64/initrd.gz\n}}\n"
            bios_text += f'\nLABEL {name}\n MENU LABEL {label} unattended - ERASE {disk}\n KERNEL debian-installer/amd64/linux\n APPEND initrd=debian-installer/amd64/initrd.gz {args} ---\n'
        grub.write_text(grub_text)
        bios.write_text(bios_text)
        files = sorted(x for x in root.rglob('*') if x.is_file() and x.name != 'settings.json')
        write(root, 'payload.sha256', ''.join(f'{hashlib.sha256(x.read_bytes()).hexdigest()}  {x.relative_to(root)}\n' for x in files))
        write(root, 'profile-generation', s['generation']+'\n')
        write(root, 'profile-server', s['address']+'\n')
        archive = output/'unattended-profile.tar.gz'
        # Create with private permissions before writing credentials, regardless of umask.
        archive.touch(mode=0o600)
        with tarfile.open(archive, 'w:gz') as tar:
            for x in files + [root/'payload.sha256', root/'profile-generation', root/'profile-server']:
                tar.add(x, arcname=str(x.relative_to(root)), recursive=False)
    for source, target in [('deploy-unattended.sh', 'deploy-unattended.sh'),
                           ('runtime-clock.sh', 'offline-clock'), ('runtime-rtc.sh', 'offline-rtc'),
                           ('update-clock-tools.sh', 'update-clock-tools.sh')]:
        write(output, target, (base/source).read_text(), 0o700)
    print('Prepared private NVMe and SATA profiles; default: '+default)
    for name, (_, disk, _, _) in profiles.items():
        print(f'{name}: automatically replaces {disk} after selection')
    print(f'Bundle: {output}')
    print('Archive SHA256: '+hashlib.sha256(archive.read_bytes()).hexdigest())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('settings')
    p.add_argument('--nvme-preseed', required=True, type=Path)
    p.add_argument('--sata-preseed', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--default', choices=['menu', 'guided', 'nvme', 'sata'], default='menu')
    p.add_argument('--enable-destructive-profile', action='store_true')
    a = p.parse_args()
    if not a.enable_destructive_profile:
        p.error('Explicit --enable-destructive-profile required: selecting NVMe/SATA erases the configured client disk')
    try:
        build(settings(a.settings), {'nvme': a.nvme_preseed, 'sata': a.sata_preseed}, a.output, a.default)
    except ValueError as error:
        p.error(str(error))


if __name__ == '__main__':
    main()
