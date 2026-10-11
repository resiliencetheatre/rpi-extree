#!/usr/bin/env python3
"""Download and authenticate a small Debian netboot-only diagnostic bundle.
No package mirror, automatic install, disk preparation or service activation.
"""
import argparse
import importlib.util
import json
import shutil
import ssl
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from common import settings, digest, confined, write, netboot_uefi_links

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('mirror_verifier', HERE/'verify-mirror.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class HTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith('https://'):
            raise ValueError('Refusing non-HTTPS redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def prepare(s, output):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Output already exists; choose a new filename')
    if not shutil.which('gpgv'):
        raise ValueError('Install gpgv and debian-archive-keyring on this workstation')
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl.create_default_context()), HTTPSOnly())
    upstream = s['debian_upstream'].rstrip('/')
    with tempfile.TemporaryDirectory(prefix='offline-netboot-') as tmp:
        tmp = Path(tmp)
        def fetch(relative, dest, limit):
            dest.parent.mkdir(parents=True, exist_ok=True)
            print('Fetching '+relative, flush=True)
            with opener.open(upstream+'/'+relative, timeout=60) as response, dest.open('wb') as f:
                total = 0
                while block := response.read(1024*1024):
                    total += len(block)
                    if total > limit:
                        raise ValueError('Download exceeds expected diagnostic size limit')
                    f.write(block)
        dist = f"dists/{s['codename']}"
        fetch(dist+'/InRelease', tmp/'archive'/dist/'InRelease', 4*1024*1024)
        release_dir, fields, sums, signed = verifier.release(tmp/'archive', s['codename'], s['keyring'])
        current = 'main/installer-amd64/current/images/SHA256SUMS'
        expected = sums[current]
        builds = [name for name, value in sums.items()
                  if name.startswith('main/installer-amd64/') and name.endswith('/images/SHA256SUMS')
                  and name.split('/')[2][0].isdigit() and value == expected]
        if len(builds) != 1:
            raise ValueError('Cannot identify unique dated installer from signed Release')
        checksum_name = builds[0]
        checksum = tmp/'SHA256SUMS'
        fetch(dist+'/'+checksum_name, checksum, 4*1024*1024)
        verifier.check(checksum, expected)
        entries = {}
        for line in checksum.read_text().splitlines():
            sha, name = line.split(maxsplit=1)
            name = name.lstrip('*')
            if name.startswith('./'):
                name = name[2:]
            entries[name] = sha
        archive = tmp/'netboot.tar.gz'
        fetch(dist+'/'+checksum_name.rsplit('/',1)[0]+'/netboot/netboot.tar.gz', archive, 256*1024*1024)
        if digest(archive) != entries['netboot/netboot.tar.gz']:
            raise ValueError('Netboot archive SHA256 does not match authenticated checksum manifest')
        bundle = tmp/'netboot-test'
        tftp = bundle/'tftp'
        with tarfile.open(archive) as tf:
            tf.extractall(tftp, filter='data')
        for name in ['pxelinux.0','pxelinux.cfg/default','debian-installer/amd64/linux',
                     'debian-installer/amd64/initrd.gz','debian-installer/amd64/bootnetx64.efi',
                     'debian-installer/amd64/grubx64.efi','debian-installer/amd64/grub/grub.cfg']:
            if not confined(tftp, name).is_file():
                raise ValueError('Missing expected Debian artifact: '+name)
        netboot_uefi_links(tftp)
        # Preserve the complete stock menu, relative links, modules and signed loaders.
        # No preseed, automatic partitioning, or installed-system source changes.
        for file in tftp.rglob('*'):
            if file.is_symlink() and not file.resolve().is_relative_to(tftp.resolve()):
                raise ValueError('Escaping symlink: '+str(file))
        metadata = {'purpose':'netboot-only diagnostic; no offline package mirror',
                    'installer_build': checksum_name.split('/')[2],
                    'upstream': upstream, 'release_sha256':digest(signed),
                    'netboot_sha256':digest(archive), 'keyring_sha256':digest(s['keyring']),
                    'trust':'Debian-signed InRelease -> SHA256SUMS -> netboot.tar.gz',
                    'secure_boot_test':'not performed', 'settings':s}
        write(bundle, 'provenance.json', json.dumps(metadata,indent=2)+'\n')
        write(bundle, 'run-netboot-test.sh', (HERE/'run-netboot-test.sh').read_text(), 0o755)
        config = f'''# Diagnostic only: DHCP/TFTP; no repository or Internet gateway.
port=0
interface={s['interface']}
bind-interfaces
no-resolv
no-hosts
dhcp-authoritative
dhcp-range={s['pool_start']},{s['pool_end']},{s['netmask']},12h
dhcp-option=option:router
dhcp-option=option:dns-server
dhcp-match=set:bios,option:client-arch,0
dhcp-match=set:efi64,option:client-arch,7
dhcp-match=set:efi64,option:client-arch,9
dhcp-boot=tag:bios,pxelinux.0,,{s['address']}
dhcp-boot=tag:efi64,debian-installer/amd64/bootnetx64.efi,,{s['address']}
enable-tftp
log-dhcp
log-facility=-
'''
        write(bundle, 'dnsmasq.conf', config)
        write(bundle, 'network.conf', f"INTERFACE='{s['interface']}'\nADDRESS='{s['server']}'\n")
        # Verify transferred files on the Pi. Authenticity of this inventory comes
        # from comparing the entire bundle SHA256 over the serial/administrative channel.
        files = sorted(p for p in bundle.rglob('*') if p.is_file() and not p.is_symlink())
        write(bundle, 'files.sha256', ''.join(f'{digest(p)}  {p.relative_to(bundle)}\n' for p in files))
        output.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(output, 'w:gz', dereference=False) as tf:
            tf.add(bundle, arcname='netboot-test')
    print(f'\nReady: {output}\nSHA256: {digest(output)}\nBytes: {output.stat().st_size}')
    print('Compare this bundle SHA256 on the Pi BEFORE extraction. Run only on the isolated laptop cable.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('settings'); p.add_argument('output', help='new .tar.gz file outside the repository')
    args = p.parse_args()
    try:
        prepare(settings(args.settings), args.output)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError, tarfile.TarError) as e:
        p.exit(1, f'Netboot preparation FAILED: {e}\n')
