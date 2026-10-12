"""Manual Pi acquisition engine. No mount/service operations in this module."""
import hashlib
import importlib.util
import ipaddress
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote, urlsplit
from common import confined, digest


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


verifier = module('mirror_verifier', 'verify-mirror.py')
GIB = 1024**3


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.new')
    with tmp.open('w') as f:
        os.chmod(tmp, 0o600)
        json.dump(value, f, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def name_ok(name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', name):
        raise ValueError('Unsafe generation name')
    return name


def relative(name):
    if not re.fullmatch(r'[A-Za-z0-9_+./~%-]+', name) or '%' in name or name.startswith('/') or '..' in Path(name).parts:
        raise ValueError('Unsafe archive filename')
    return name


def valid_release(fields, previous=None, now=None):
    now = now or datetime.now(timezone.utc)
    date = parsedate_to_datetime(fields['Date'])
    if date.tzinfo is None or date > now:
        raise ValueError('Upstream metadata date is in the future; check UTC')
    if fields.get('Valid-Until') and parsedate_to_datetime(fields['Valid-Until']) <= now:
        raise ValueError('Upstream metadata expired; refusing a stale refresh')
    if previous and date < parsedate_to_datetime(previous):
        raise ValueError('Upstream metadata rollback detected')


def space(root, amount, reserve):
    if shutil.disk_usage(root).free < amount + reserve:
        raise ValueError('Insufficient free space; keep current/rollback generations, remove only unneeded generations explicitly')


class Fetcher:
    def __init__(self, roots, storage, reserve=0):
        self.roots = roots
        self.storage = Path(storage)
        self.reserve = reserve
        for root in roots.values():
            url = urlsplit(root)
            if url.scheme != 'https' or url.username or url.password or url.query or url.fragment:
                raise ValueError('Only configured HTTPS archive roots are allowed')

    def fetch(self, archive, name, dest, expected=None, limit=256*1024**2):
        relative(name)
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if expected:
            limit = expected[0]
            if limit < 0 or not re.fullmatch('[a-f0-9]{64}', expected[1]):
                raise ValueError('Invalid signed file expectation')
            if dest.is_file() and dest.stat().st_size == limit and digest(dest) == expected[1]:
                return
            if limit == 0:
                if expected[1] != hashlib.sha256(b'').hexdigest():
                    raise ValueError('Invalid empty signed file')
                dest.write_bytes(b'')
                return
        partial = dest.with_name(dest.name + '.partial')
        state = dest.with_name(dest.name + '.partial.json')
        identity = [archive, name, list(expected) if expected else None]
        if not state.exists() or json.loads(state.read_text()) != identity or not expected:
            partial.unlink(missing_ok=True)
            atomic_json(state, identity)
        url = self.roots[archive].rstrip('/') + '/' + quote(name, safe='/+~')
        for attempt in range(3):
            offset = partial.stat().st_size if partial.exists() else 0
            if offset >= limit:
                if expected and offset == limit and digest(partial) == expected[1]:
                    os.replace(partial, dest)
                    state.unlink(missing_ok=True)
                    return
                partial.unlink(missing_ok=True)
                offset = 0
            space(self.storage, max(0, limit-offset), self.reserve)
            # No redirect following: an unexpected host/path redirect is a failure.
            # -q disables curlrc and --noproxy disables ambient proxy credentials.
            cmd = ['curl', '-q', '--fail', '--silent', '--show-error', '--noproxy', '*',
                   '--proto', '=https', '--interface', 'if!wlan0', '--connect-timeout', '30',
                   '--speed-limit', '1024', '--speed-time', '90', '--max-time', '3600',
                   '--max-filesize', str(limit), '--output', str(partial), '--write-out', '%{http_code}']
            if offset:
                cmd += ['--continue-at', str(offset)]
            result = subprocess.run(cmd + [url], text=True, capture_output=True)
            received = partial.stat().st_size if partial.exists() else 0
            diagnostic = ' '.join(''.join(c for c in result.stderr if c.isprintable() or c.isspace()).split())[:500]
            reason = f'curl exit={result.returncode}, HTTP={result.stdout.strip() or "none"}, partial bytes={received}'
            if diagnostic:
                reason += '; ' + diagnostic
            if result.returncode == 0 and result.stdout in ('200', '206'):
                if partial.stat().st_size <= limit and (not expected or
                        (partial.stat().st_size == limit and digest(partial) == expected[1])):
                    os.replace(partial, dest)
                    state.unlink(missing_ok=True)
                    return
                if expected and received != limit:
                    reason = f'Size mismatch: expected {limit}, received {received}'
                elif expected:
                    reason = f'SHA256 mismatch: expected {expected[1]}, received {digest(partial)}'
                else:
                    reason = f'Download exceeds size limit {limit}: received {received}'
                partial.unlink(missing_ok=True)
            elif result.returncode == 33 or result.stdout == '416' or result.stdout.startswith('3'):
                partial.unlink(missing_ok=True)
            print(f'Download attempt {attempt+1}/3 failed: {archive}/{name}: {reason}', flush=True)
            if attempt < 2:
                time.sleep(2)
        raise ValueError('Download failed: ' + archive + '/' + name + ': ' + reason + '; resume explicitly')


def preferred_index(name, sums):
    """Release may hash uncompressed content which is not published as a file."""
    suffixes = ('.xz', '.gz', '.bz2')
    base = name
    for suffix in suffixes:
        if name.endswith(suffix):
            base = name[:-len(suffix)]
            break
    variants = [base + suffix for suffix in suffixes if base + suffix in sums]
    return name == (variants[0] if variants else base)


def selected(s, name):
    """Retain selected binary/udeb indexes, translations and component metadata."""
    parts = name.split('/')
    if parts[0] not in s['components']:
        return False
    if len(parts) < 2:
        return False
    if parts[1] == 'i18n':
        return True
    if parts[1].startswith('binary-'):
        return parts[1][7:] in s['architectures'] + ['all']
    if parts[1] == 'debian-installer' and len(parts) > 2:
        return parts[2].startswith('binary-') and parts[2][7:] in s['architectures'] + ['all']
    if parts[1] == 'source':
        return s['sources']
    return False


def plan(s, root, fetcher, active=None, check_only=False):
    root = Path(root)
    files = {}
    releases = []
    old = {}
    if active and (active/'manifest.json').is_file():
        old = {r['suite']: r.get('date') for r in json.loads((active/'manifest.json').read_text())['releases']}
    for archive, suites in [('debian', ['trixie', 'trixie-updates']), ('debian-security', ['trixie-security'])]:
        for suite in suites:
            signed = confined(root, f'{archive}/dists/{suite}/InRelease')
            fetcher.fetch(archive, f'dists/{suite}/InRelease', signed, limit=4*1024**2)
            dist, fields, sums, _ = verifier.release(root/archive, suite, s['keyring'])
            valid_release(fields, old.get(suite))
            releases.append({'archive': archive, 'suite': suite, 'sha256': digest(signed), 'date': fields['Date']})
            for name, expected in sums.items():
                if selected(s, name):
                    if check_only and not any(part.startswith(('Packages', 'Sources')) for part in name.split('/')):
                        continue
                    relative(name)
                    # Omit pdiffs, fetch complete current signed indexes instead.
                    if '.diff/' in name:
                        continue
                    # Prefer compressed indexes, avoiding redundant uncompressed copies.
                    if not preferred_index(name, sums):
                        continue
                    remote = f'dists/{suite}/{name}'
                    if fields.get('Acquire-By-Hash') == 'yes' and name.endswith(('.xz', '.gz', '.bz2')):
                        remote = f'dists/{suite}/{str(Path(name).parent)}/by-hash/SHA256/{expected[1]}'
                    fetcher.fetch(archive, remote, confined(dist, name), expected)
            # Use verifier's coverage rules rather than assuming all occurs separately.
            for component in s['components']:
                names = [f'{component}/binary-{arch}/Packages' for arch in s['architectures']]
                for arch in s['architectures'] + ['all']:
                    for section in ('binary-', 'debian-installer/binary-'):
                        name = f'{component}/{section}{arch}/Packages'
                        if name not in names and any(name+x in sums for x in ('', '.gz', '.xz')):
                            names.append(name)
                if s['sources']:
                    names.append(f'{component}/source/Sources')
                for name in names:
                    path, opener = verifier.index(dist, name, sums)
                    with opener(path, 'rt', encoding='utf-8') as stream:
                        for record in verifier.paragraphs(stream):
                            if name.endswith('/Sources'):
                                entries = [(record['Directory']+'/'+n, int(sz), sha)
                                           for sha, sz, n in (x.split() for x in record['Checksums-Sha256'].splitlines() if x.strip())]
                            else:
                                if record['Architecture'] not in s['architectures']+['all']:
                                    raise ValueError('Unexpected package architecture')
                                entries = [(record['Filename'], int(record['Size']), record['SHA256'])]
                            for filename, size, sha in entries:
                                relative(filename)
                                if not filename.startswith('pool/') or size < 0 or not re.fullmatch('[a-f0-9]{64}', sha):
                                    raise ValueError('Invalid signed package record')
                                key = archive+'/'+filename
                                if key in files and files[key] != (size, sha):
                                    raise ValueError('Conflicting package records')
                                files[key] = (size, sha)
            if suite == 'trixie' and not check_only:
                name = 'main/installer-amd64/current/images/SHA256SUMS'
                fetcher.fetch(archive, f'dists/{suite}/{name}', confined(dist, name), sums[name])
                for line in (dist/name).read_text().splitlines():
                    sha, image = line.split(maxsplit=1)
                    image = image.lstrip('*').removeprefix('./')
                    if image == 'netboot/netboot.tar.gz':
                        # SHA256SUMS doesn't include sizes; enforce a bounded download.
                        dest = dist/Path(name).parent/image
                        fetcher.fetch(archive, f'dists/{suite}/{Path(name).parent}/{image}', dest, limit=256*1024**2)
                        if digest(dest) != sha:
                            raise ValueError('Installer tarball hash mismatch')
    return files, releases


def acquire(files, root, active, fetcher, reserve):
    root = Path(root)
    remaining = 0
    for name, expected in files.items():
        dest = confined(root, name)
        if not dest.is_file() or dest.stat().st_size != expected[0] or digest(dest) != expected[1]:
            remaining += expected[0]
    space(root, remaining + GIB, reserve)
    print(f'Package bytes still to materialize: {remaining}; reserve: {reserve}', flush=True)
    for i, (name, expected) in enumerate(files.items(), 1):
        dest = confined(root, name)
        if dest.is_file() and dest.stat().st_size == expected[0] and digest(dest) == expected[1]:
            continue
        source = confined(active, name) if active else None
        if source and source.is_file() and source.stat().st_size == expected[0] and digest(source) == expected[1]:
            space(root, expected[0], reserve)
            dest.parent.mkdir(parents=True, exist_ok=True)
            partial = dest.with_name(dest.name+'.copy')
            shutil.copyfile(source, partial)
            verifier.check(partial, expected)
            os.replace(partial, dest)
        else:
            archive, filename = name.split('/', 1)
            fetcher.fetch(archive, filename, dest, expected)
        if i % 100 == 0 or i == len(files):
            print(f'Packages: {i}/{len(files)}', flush=True)


def check_rotation(s, root, fetcher, releases):
    for r in releases:
        dest = root / (r['suite']+'.latest')
        fetcher.fetch(r['archive'], 'dists/'+r['suite']+'/InRelease', dest, limit=4*1024**2)
        if digest(dest) != r['sha256']:
            raise ValueError('Upstream metadata changed during acquisition; resume to replan consistently')
        dest.unlink()
        _, fields, _, _ = verifier.release(root/r['archive'], r['suite'], s['keyring'])
        valid_release(fields)
