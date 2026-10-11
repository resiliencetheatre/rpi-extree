#!/usr/bin/env python3
"""Connected Debian 13 workstation only; downloads require an explicit flag."""
import argparse
import fcntl
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from common import settings, write
import importlib.util

spec = importlib.util.spec_from_file_location('offline_preflight', Path(__file__).with_name('host-preflight.py'))
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)
spec = importlib.util.spec_from_file_location('mirror_verifier', Path(__file__).with_name('verify-mirror.py'))
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def installer_sections(components):
    # Udebs also exist outside main, including in the security archive.
    # These sections are independent of --di-dist/--di-arch image mirroring.
    return components + [component+'/debian-installer' for component in components]


def fetch_updates_installer_indexes(root, s):
    # debmirror 2.47 deliberately skips all *-updates installer sections.
    # Retain the actual signed empty indexes; never synthesize archive metadata.
    suite=s['codename']+'-updates'
    dist, fields, sums, signed=verifier.release(root/'debian',suite,s['keyring'])
    opener=urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=preflight.tls_environment()),preflight.HTTPSOnly())
    empty_sha='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    for component in s['components']:
        for arch in s['architectures']+['all']:
            name=f'{component}/debian-installer/binary-{arch}/Packages'
            variants=[name+suffix for suffix in ('.xz','.gz','') if name+suffix in sums]
            if not variants:
                continue
            if sums.get(name)!=(0,empty_sha):
                raise ValueError(f'{suite}/{name} is no longer empty: review debmirror updates-udeb handling before continuing')
            relative=variants[0]
            destination=dist/relative
            if destination.exists():
                verifier.check(destination,sums[relative])
                continue
            destination.parent.mkdir(parents=True,exist_ok=True)
            temporary=destination.with_name(destination.name+'.download')
            url=s['debian_upstream'].rstrip('/')+'/dists/'+suite+'/'+relative
            with opener.open(url,timeout=60) as response:
                data=response.read(sums[relative][0]+1)
            temporary.write_bytes(data)
            verifier.check(temporary,sums[relative])
            temporary.replace(destination)

p=argparse.ArgumentParser()
p.add_argument('settings'); p.add_argument('staging_root')
p.add_argument('--allow-download',action='store_true',help='authorize a complete, potentially TB-scale mirror download')
p.add_argument('--attempts',type=int,default=3)
args=p.parse_args(); s=settings(args.settings)
base=Path(args.staging_root).resolve(); repo=Path(__file__).resolve().parents[2]
if base.is_relative_to(repo.parent) or repo.parent.is_relative_to(base):
    p.error('Mirror data must live outside the workspace/repository')
if not args.allow_download: p.error('Read README and pass --allow-download to authorize archive acquisition')
if args.attempts<1: p.error('attempts must be positive')
preflight.check(s, online=True)
for tool in ('debmirror','gpgv','rsync','dpkg-deb','lsinitramfs'):
    if not shutil.which(tool): p.error(f'Missing host prerequisite: {tool}')
version=subprocess.check_output(['debmirror','--version'],text=True)
# Debian debmirror 2.47 exits 1 for --help and prints only a usage synopsis.
# Inspect its actual GetOptions declarations instead of treating help as a
# successful capability probe. Do not invoke a mirror run to discover options.
source=Path(shutil.which('debmirror')).read_text()
option_blocks=re.findall(r'\bGetOptions\((.*?)\)\s*(?:or\s+usage)?;',source,re.S)
options=set()
for block in option_blocks:
    for declaration in re.findall(r"'([^']+)'\s*=>",block):
        options.update(re.split(r'[=!:]',declaration,maxsplit=1)[0].split('|'))
for flag in ('config-file','method','arch','source','check-gpg','checksums','keyring',
             'rsync-extra','diff','postcleanup','omit-suite-symlinks','host','root',
             'dist','section','di-dist','di-arch'):
    if flag not in options: p.error(f'Installed debmirror lacks required option --{flag}')
# Review Architecture: all handling rather than assuming a default architecture.
if '(@arches, "all")' not in source:
    p.error('Unreviewed debmirror Architecture: all handling; inspect this version')
print('Validated options and Architecture: all handling for '+version.strip(),flush=True)
base.mkdir(parents=True,exist_ok=True)
with (base/'.offline-acquisition.lock').open('w') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    root=base/s['generation']; root.mkdir(exist_ok=True)
    if (root/'ready.sha256').exists(): p.error('Already verified: use a new generation name for refresh')
    write(root,'acquisition.json',json.dumps({'started':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'debmirror_version':version.strip(),'debian_upstream':s['debian_upstream'],'security_upstream':s['security_upstream']},indent=2)+'\n')
    config=str(Path(__file__).with_name('debmirror.conf'))
    common=['debmirror','--config-file='+config,'--method=https','--arch='+','.join(s['architectures']),
            '--source' if s['sources'] else '--nosource','--check-gpg','--checksums',
            '--keyring='+str(Path(s['keyring']).resolve()),'--rsync-extra=none','--diff=none','--postcleanup','--omit-suite-symlinks']
    env=os.environ.copy(); env['GNUPGHOME']=str(base/'.unused-gnupg')
    env['PERL_LWP_SSL_VERIFY_HOSTNAME']='1'
    env['PERL_LWP_SSL_CA_FILE']=preflight.CA_BUNDLE
    if Path(env['GNUPGHOME']).exists(): p.error('Reserved GNUPGHOME exists; refuse additional trusted keys')
    for attempt in range(args.attempts):
        try:
            for archive,suites,upstream in [('debian',s['codename']+','+s['codename']+'-updates',s['debian_upstream']),('debian-security',s['codename']+'-security',s['security_upstream'])]:
                if shutil.disk_usage(base).free < int(s['minimum_free_gib'])*1024**3:
                    raise ValueError('Free-space reserve reached; add storage before retrying')
                url=urlsplit(upstream)
                if url.scheme!='https' or url.query or url.fragment or url.username:
                    raise ValueError('Use an HTTPS upstream archive root without credentials/query')
                sections=installer_sections(s['components'])
                cmd=common+['--host='+url.netloc,'--root='+url.path.lstrip('/'),'--dist='+suites,'--section='+','.join(sections)]
                if archive=='debian': cmd+=['--di-dist='+s['codename'],'--di-arch=amd64']
                subprocess.run(cmd+[str(root/archive)],env=env,check=True)
            fetch_updates_installer_indexes(root,s)
            # debmirror's installer path uses MD5; obtain SHA256SUMS separately.
            # Its trust is established against the signed Release by the verifier.
            relative=f"dists/{s['codename']}/main/installer-amd64/current/images/SHA256SUMS"
            dest=root/'debian'/relative; dest.parent.mkdir(parents=True,exist_ok=True)
            opener=urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=preflight.tls_environment()), preflight.HTTPSOnly())
            with opener.open(s['debian_upstream'].rstrip('/')+'/'+relative,timeout=120) as response:
                data=response.read(4*1024*1024)
            dest.write_bytes(data)
            subprocess.run(['python3',str(Path(__file__).with_name('verify-mirror.py')),args.settings,str(root)],check=True)
            print(f'Verified staging generation: {root}'); break
        except (subprocess.CalledProcessError,ValueError,OSError) as e:
            if attempt+1==args.attempts: raise
            print(f'Attempt {attempt+1} failed: {e}; repeating both mirrors for consistency',flush=True)
