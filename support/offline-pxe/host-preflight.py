#!/usr/bin/env python3
"""Check Debian workstation prerequisites and, optionally, signed HTTPS metadata.
--online fetches only three InRelease files, never package pools.
"""
import argparse
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import urllib.request
from urllib.parse import urlsplit
from common import settings

CA_BUNDLE = '/etc/ssl/certs/ca-certificates.crt'


class HTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != 'https':
            raise ValueError('Refusing HTTPS downgrade redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def tls_environment():
    # Perl LWP honours environment overrides. Do not inherit a verification bypass.
    if os.environ.get('PERL_LWP_SSL_VERIFY_HOSTNAME', '1') != '1':
        raise ValueError('Remove PERL_LWP_SSL_VERIFY_HOSTNAME override; TLS verification is required')
    context = ssl.create_default_context(cafile=CA_BUNDLE)
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise ValueError('Python TLS validation is disabled')
    return context


def check(s, online=False, tls_only=False):
    context = tls_environment()
    keyring = Path(s['keyring'])
    if not keyring.is_file() or not keyring.stat().st_size:
        raise ValueError('Missing Debian archive keyring: '+str(keyring))
    required = ['gpgv', 'perl']
    if not tls_only:
        required += ['debmirror', 'rsync', 'dpkg-deb', 'lsinitramfs', 'xz', 'gzip', 'tar']
    missing = [name for name in required if not shutil.which(name)]
    if missing:
        raise ValueError('Missing host tools: '+', '.join(missing)+'; see README host prerequisites')
    subprocess.run(['perl', '-MLWP::UserAgent', '-MLWP::Protocol::https', '-MIO::Socket::SSL', '-e',
                    'print "Perl HTTPS modules available\n";'], check=True)
    print(f'Python: {ssl.OPENSSL_VERSION}; CA bundle: {CA_BUNDLE}', flush=True)
    print(f'Debian signature keyring: {keyring}', flush=True)
    if not online:
        return
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), HTTPSOnly())
    urls = [s['debian_upstream'].rstrip('/')+'/dists/'+s['codename']+'/InRelease',
            s['debian_upstream'].rstrip('/')+'/dists/'+s['codename']+'-updates/InRelease',
            s['security_upstream'].rstrip('/')+'/dists/'+s['codename']+'-security/InRelease']
    with tempfile.TemporaryDirectory(prefix='offline-tls-') as tmp:
        for i, url in enumerate(urls):
            print('Checking Python HTTPS, Perl HTTPS and Debian signature: '+url, flush=True)
            with opener.open(url, timeout=30) as response:
                data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError('Unexpectedly large InRelease')
            path = Path(tmp)/f'{i}.InRelease'; path.write_bytes(data)
            subprocess.run(['gpgv', '--homedir', tmp, '--keyring', str(keyring.resolve()), str(path)], check=True)
            # Exercise the same TLS stack that debmirror uses, with explicit trust.
            subprocess.run(['perl', '-MLWP::UserAgent', '-e',
                            'my $u=LWP::UserAgent->new(timeout=>30, max_redirect=>0, '
                            'ssl_opts=>{verify_hostname=>1, SSL_verify_mode=>1, SSL_ca_file=>$ARGV[1]}); '
                            'my $r=$u->get($ARGV[0]); die $r->status_line unless $r->is_success;',
                            url, CA_BUNDLE], check=True)
    print('PASS: all three signed upstream metadata files verified over HTTPS', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('settings'); p.add_argument('--online', action='store_true')
    p.add_argument('--tls-only', action='store_true', help='skip mirror-tool presence checks')
    args = p.parse_args()
    try:
        check(settings(args.settings), args.online, args.tls_only)
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        p.exit(1, f'Preflight FAILED: {e}\n')
