#!/usr/bin/env python3
"""Fail-closed verification of signed Debian indexes and every referenced file.
Run only on an unserved staging generation. A failed run removes its readiness seal.
"""
import argparse
import gzip
import json
import lzma
import os
import re
import subprocess
import tarfile
import tempfile
import hashlib
from archive_inspect import deb_files, initramfs_names
from datetime import datetime, timezone
from pathlib import Path
from common import confined, digest, settings, write, netboot_uefi_links
from render import generation as render_generation


def now():
    return datetime.now(timezone.utc).isoformat()


def paragraphs(lines):
    record={}; key=None
    total=0
    for line in lines:
        total += len(line)
        if len(line) > 1024**2 or total > 1024**3:
            raise ValueError('Metadata exceeds inspection limits')
        line=line.rstrip('\n')
        if not line:
            if record: yield record
            record={}; key=None
        elif line[0].isspace():
            if key is None: raise ValueError('Invalid continuation in index')
            record[key]+='\n'+line[1:]
        else:
            key,value=line.split(':',1)
            if key in record:
                raise ValueError('Duplicate metadata field')
            record[key]=value.strip()
    if record: yield record


def clearsigned_text(raw):
    """Extract only the cleartext of one already-verified OpenPGP message.

    gpgv builds differ in whether --output emits clearsigned plaintext. Keep
    signature verification mandatory, but do not depend on that side effect.
    Reject ambiguous envelopes and undo OpenPGP dash escaping, not arbitrary
    armor-like strings or text outside the authenticated body.
    """
    if len(raw) > 4 * 1024**2:
        raise ValueError('InRelease exceeds metadata limit')
    text = raw.decode('utf-8').replace('\r\n', '\n')
    if '\r' in text:
        raise ValueError('Invalid InRelease line endings')
    lines = text.split('\n')
    if lines.pop(0) != '-----BEGIN PGP SIGNED MESSAGE-----':
        raise ValueError('Expected one clearsigned InRelease')
    while lines and lines[0]:
        if not re.fullmatch(r'Hash: [A-Za-z0-9, -]+', lines.pop(0)):
            raise ValueError('Unexpected clearsign header')
    if not lines:
        raise ValueError('Missing clearsign body')
    lines.pop(0)
    marker = '-----BEGIN PGP SIGNATURE-----'
    if lines.count(marker) != 1:
        raise ValueError('Ambiguous InRelease signature envelope')
    end = lines.index(marker)
    body, signature = lines[:end], lines[end+1:]
    closing = '-----END PGP SIGNATURE-----'
    if signature.count(closing) != 1 or any(signature[signature.index(closing)+1:]):
        raise ValueError('Unexpected trailing InRelease content')
    result = []
    for line in body:
        if line.startswith('- '):
            line = line[2:]
        elif line.startswith('-'):
            raise ValueError('Unescaped dash in clearsigned body')
        result.append(line.rstrip(' \t'))
    return '\n'.join(result)+'\n'


def release(root, suite, keyring):
    path=confined(root, 'dists/'+suite)
    with tempfile.TemporaryDirectory(prefix='offline-gpg-') as tmp:
        cmd=['gpgv','--homedir',tmp,'--keyring',str(Path(keyring).resolve())]
        if (path/'InRelease').exists():
            signed=path/'InRelease'
            raw=signed.read_bytes()
            # Verify the same immutable bytes we parse, avoiding a second read
            # of a file which could be replaced between verification and parsing.
            snapshot=Path(tmp)/'InRelease'
            snapshot.write_bytes(raw)
            subprocess.run(cmd+[str(snapshot)],check=True)
            data=clearsigned_text(raw)
        else:
            subprocess.run(cmd+[str(path/'Release.gpg'),str(path/'Release')],check=True)
            data=(path/'Release').read_text(); signed=path/'Release'
        fields=next(paragraphs(data.splitlines(True)))
        if fields.get('Codename') != suite:
            raise ValueError(f'Wrong codename in {signed}: {fields.get("Codename")}')
        sums={}
        for line in fields['SHA256'].splitlines():
            if not line.strip(): continue
            sha,size,name=line.split()
            if not re.fullmatch('[0-9a-f]{64}',sha): raise ValueError('Invalid SHA256')
            confined(path,name)
            sums[name]=(int(size),sha)
    return path, fields, sums, signed


def check(path, expected):
    size, sha=expected
    if not path.is_file() or path.stat().st_size != size or digest(path) != sha:
        raise ValueError(f'Missing or corrupt file: {path}')


def index(root, name, sums):
    found=[]
    for suffix, opener in [('.xz',lzma.open),('.gz',gzip.open),('',open)]:
        key=name+suffix
        if key in sums and confined(root,key).is_file():
            check(confined(root,key), sums[key]); found.append((confined(root,key),opener))
    if not found: raise ValueError(f'Missing signed index: {root/name}')
    return found[0]


def verify(root, s, publish=True):
    root=Path(root).resolve()
    if root.name != s['generation']: raise ValueError('Generation directory name must match settings')
    seal=root/'ready.sha256'
    seal.unlink(missing_ok=True)
    (root/'manifest.json').unlink(missing_ok=True)
    packages={}; all_count=0; source_count=0; releases=[]; installer_release=None
    versions={}; selected_indexes=[]; required_small=[]
    for archive,suites in [('debian',[s['codename'],s['codename']+'-updates']),('debian-security',[s['codename']+'-security'])]:
        archive_root=root/archive
        for suite in suites:
            dist, fields, sums, signed=release(archive_root,suite,s['keyring'])
            releases.append({'archive':archive,'suite':suite,'sha256':digest(signed),'date':fields.get('Date'),'valid_until':fields.get('Valid-Until')})
            required_small.append(signed)
            if signed.name=='Release': required_small.append(dist/'Release.gpg')
            if suite==s['codename']: installer_release=(dist,sums)
            names=[]
            for component in s['components']:
                for arch in s['architectures']:
                    names.append(f'{component}/binary-{arch}/Packages')
                # Some releases split Architecture: all, others include it in amd64.
                if any(f'{component}/binary-all/Packages'+suf in sums for suf in ('','.gz','.xz')):
                    names.append(f'{component}/binary-all/Packages')
                for arch in s['architectures']+['all']:
                    name=f'{component}/debian-installer/binary-{arch}/Packages'
                    if any(name+suf in sums for suf in ('','.gz','.xz')):
                        names.append(name)
                    elif component=='main' and arch=='amd64' and suite==s['codename']:
                        raise ValueError('Missing main installer udeb index')
                if s['sources']: names.append(f'{component}/source/Sources')
            for name in names:
                path,opener=index(dist,name,sums)
                selected_indexes.append({'path':str(path.relative_to(root)),'sha256':digest(path)})
                with opener(path,'rt',encoding='utf-8') as stream:
                    for rec in paragraphs(stream):
                        if name.endswith('/Sources'):
                            source_count+=1
                            for line in rec['Checksums-Sha256'].splitlines():
                                if line.strip():
                                    sha,size,filename=line.split()
                                    file=confined(archive_root,rec['Directory']+'/'+filename)
                                    expected=(int(size),sha)
                                    if file in packages and packages[file]!=expected: raise ValueError('Conflicting source checksums')
                                    packages[file]=expected
                            continue
                        arch=rec['Architecture']
                        if arch not in s['architectures']+['all']: raise ValueError(f'Unexpected package architecture {arch}')
                        if arch=='all': all_count+=1
                        file=confined(archive_root,rec['Filename'])
                        if not file.suffix in ('.deb','.udeb') or not rec['Filename'].startswith('pool/'):
                            raise ValueError('Invalid package filename')
                        expected=(int(rec['Size']),rec['SHA256'])
                        if not re.fullmatch('[0-9a-f]{64}',expected[1]): raise ValueError('Invalid package SHA256')
                        if file in packages and packages[file]!=expected: raise ValueError('Conflicting package checksums')
                        packages[file]=expected
                        if suite==s['codename'] and rec['Package'] in ('apt-setup-udeb','apt-mirror-setup','debootstrap-udeb'):
                            versions[rec['Package']]={'version':rec['Version'],'file':file}
            # Verify all retained signed metadata, including translations and by-hash
            # when present. Clients explicitly disable by-hash for this private mirror.
            for name,expected in sums.items():
                path=confined(dist,name)
                if path.is_file(): check(path,expected)
                bh=path.parent/'by-hash/SHA256'/expected[1]
                if bh.exists(): check(bh,expected)
    if all_count==0: raise ValueError('No Architecture: all package coverage')
    total=0
    for file,expected in packages.items():
        check(file,expected); total+=expected[0]
    for name in ('apt-setup-udeb','apt-mirror-setup'):
        if versions.get(name,{}).get('version')!='1:0.198' and versions.get(name,{}).get('version')!='0.198':
            raise ValueError(f'{name}: unreviewed installer version: {versions.get(name)}')
    # Inspect the actual signed packages, not just a version string.
    wanted = {'usr/lib/apt-setup/generators/60local',
              'usr/lib/apt-setup/generators/50mirror', 'usr/share/debootstrap/functions'}
    policy = {}
    for info in versions.values():
        for name, data in deb_files(info['file'], wanted).items():
            if name in policy:
                raise ValueError('Duplicate installer policy file')
            policy[name] = data
    if b'apt-setup/$repo_name/options' not in policy.get('usr/lib/apt-setup/generators/60local', b''):
        raise ValueError('Installer lacks per-source APT options')
    if hashlib.sha256(policy.get('usr/lib/apt-setup/generators/50mirror', b'')).hexdigest() != '75c441b672f42d91225dc81f729b20cf73d5c5916393e037fda40c85337d8d60':
        raise ValueError('Review changed apt-setup 50mirror before applying offline policy')
    functions = policy.get('usr/share/debootstrap/functions', b'')
    if not functions or re.search(rb'Valid-Until|Check-Valid-Until', functions):
        raise ValueError('Review changed debootstrap metadata expiry handling')
    dist,sums=installer_release
    checksum_name='main/installer-amd64/current/images/SHA256SUMS'
    checksum=confined(dist,checksum_name)
    check(checksum,sums[checksum_name])
    dated=[name.split('/')[2] for name,value in sums.items() if re.fullmatch(r'main/installer-amd64/[0-9][^/]+/images/SHA256SUMS',name) and value==sums[checksum_name]]
    if len(dated)!=1: raise ValueError('Cannot pin unique dated installer build from signed Release')
    installer_sums={}
    for line in checksum.read_text().splitlines():
        sha,name=line.split(maxsplit=1); name=name.lstrip('*')
        if name.startswith('./'): name=name[2:]
        installer_sums[name]=sha
    tar=checksum.parent/'netboot/netboot.tar.gz'
    if digest(tar)!=installer_sums['netboot/netboot.tar.gz']: raise ValueError('Untrusted netboot tarball')
    # Extraction into a clean directory avoids stale loader/module files.
    if (root/'tftp').exists():
        raise ValueError('Remove or move the previous staging tftp directory before re-verifying')
    with tarfile.open(tar) as tf:
        members=tf.getmembers()
        if len(members)>200000 or sum(max(0,m.size) for m in members)>1024**3:
            raise ValueError('Netboot archive exceeds extraction limits')
        tf.extractall(root/'tftp',members=members,filter='data')
    netboot_uefi_links(root/'tftp')
    needed=['pxelinux.0','debian-installer/amd64/pxelinux.0','debian-installer/amd64/boot-screens/ldlinux.c32','debian-installer/amd64/linux','debian-installer/amd64/initrd.gz','debian-installer/amd64/bootnetx64.efi','debian-installer/amd64/grubx64.efi','debian-installer/amd64/grub/grub.cfg','debian-installer/amd64/boot-screens/menu.cfg']
    for name in needed:
        p=confined(root/'tftp',name)
        if not p.is_file() or not p.stat().st_size: raise ValueError(f'Missing Debian boot artifact: {name}')
    initrd=root/'tftp/debian-installer/amd64/initrd.gz'
    # lsinitramfs lists concatenated/compressed initramfs safely without unpacking.
    firmware=[name for name in initramfs_names(initrd) if '/firmware/' in name]
    render_generation(s,root)
    # Never expose symlinks outside a published generation.
    for p in root.rglob('*'):
        if p.is_symlink() and not p.resolve().is_relative_to(root): raise ValueError(f'Escaping symlink: {p}')
    manifest={'schema':1,'generation':s['generation'],'outcome':'verified','verification_time':now(),
              'acquisition':json.loads((root/'acquisition.json').read_text()),
              'suites':[r['suite'] for r in releases],'components':s['components'],
              'architectures':s['architectures']+['all'],'sources':s['sources'],
              'package_files':len(packages),'package_bytes':total,'architecture_all_records':all_count,
              'source_records':source_count,'releases':releases,'indexes':selected_indexes,
              'keyring_sha256':digest(s['keyring']),
              'installer':{'build':dated[0],'netboot_sha256':digest(tar),'checksum_trust':'signed Release -> SHA256SUMS -> netboot.tar.gz',
                           'packages':{k:v['version'] for k,v in versions.items()},'firmware_paths':firmware,
                           'secure_boot_test':'not performed','nic_firmware_test':'not performed'},
              'by_hash':'disabled per local APT source; upstream signed metadata unchanged'}
    if publish:
        write(root,'manifest.json',json.dumps(manifest,indent=2)+'\n')
        # Small control files only. Boot payload provenance was checked above;
        # no pool scan is needed on Pi startup.
        small=[root/'manifest.json',root/'settings.json']+required_small
        small += [p for p in (root/'www').rglob('*') if p.is_file()]
        small += [p for p in (root/'tftp').rglob('*') if p.is_file() and p.suffix in ('.cfg','.0','.c32','.efi')]
        write(root,'ready.sha256',''.join(f'{digest(p)}  {p.relative_to(root)}\n' for p in sorted(set(small))))
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('settings'); parser.add_argument('generation')
    args=parser.parse_args()
    try:
        m=verify(args.generation,settings(args.settings)); print(f"Verified {m['package_files']} files, {m['package_bytes']} bytes")
    except (ValueError,KeyError,OSError,subprocess.CalledProcessError,tarfile.TarError) as e:
        parser.exit(1,f'Verification FAILED: {e}\n')
