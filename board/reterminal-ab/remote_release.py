"""Signed release metadata and bounded network IO for the proposed local API."""
import base64
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import ssl
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from common import PROFILE, LAYOUT, archive_read, metadata, description

MAX_METADATA = 64 * 1024
MAX_BUNDLE = 1100 * 1024**2
RESERVE = 2300 * 1024**2

class APIError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def require(condition, code, message):
    if not condition:
        raise APIError(code, message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def loads(data):
    def pairs(items):
        obj = {}
        for key, value in items:
            require(key not in obj, 'invalid_json', 'Duplicate JSON key')
            obj[key] = value
        return obj
    try:
        return json.loads(data, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))
    except (ValueError, UnicodeError) as error:
        raise APIError('invalid_json', 'Invalid JSON') from error


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected), 'invalid_request', 'Unexpected fields')


def url_origin(url, allow_http=False):
    require(type(url) is str and len(url) <= 4096, 'invalid_url', 'Invalid release URL')
    require(not any(ord(c) <= 32 or ord(c) == 127 for c in url), 'invalid_url', 'Whitespace/control characters in URL')
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise APIError('invalid_url', 'Invalid release URL') from error
    require(port is None or 1 <= port <= 65535, 'invalid_url', 'Invalid port')
    require(parsed.hostname and not parsed.username and not parsed.password and not parsed.fragment,
            'invalid_url', 'URLs cannot contain credentials or fragments')
    local = False
    try:
        local = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        pass
    require(parsed.scheme == 'https' or (allow_http and parsed.scheme == 'http' and local),
            'https_required', 'HTTPS required; lab HTTP is limited to literal loopback')
    return parsed.scheme, parsed.hostname.lower(), port or (443 if parsed.scheme == 'https' else 80)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise APIError('redirect_rejected', 'Release redirects are not allowed')


class Fetcher:
    def __init__(self, manifest_url, allow_http=False, ca_file=None):
        self.origin = url_origin(manifest_url, allow_http)
        self.allow_http = allow_http
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=ca_file)))

    def open(self, url):
        require(url_origin(url, self.allow_http) == self.origin, 'origin_mismatch', 'Cross-origin URL rejected')
        return self.opener.open(urllib.request.Request(url, headers={'Accept-Encoding': 'identity'}), timeout=15)

    def metadata(self, url, cancelled):
        require(not cancelled.is_set(), 'cancelled', 'Check cancelled')
        with self.open(url) as response:
            data = response.read(MAX_METADATA + 1)
        require(len(data) <= MAX_METADATA, 'metadata_too_large', 'Release metadata exceeds limit')
        require(not cancelled.is_set(), 'cancelled', 'Check cancelled')
        return loads(data)

    def download(self, release, path, cancelled, progress):
        bundle = release['bundle']
        digest = hashlib.sha256()
        received = 0
        with self.open(bundle['url']) as source, path.open('xb') as dest:
            length = source.headers.get('Content-Length')
            require(length is None or int(length) == bundle['size'], 'size_mismatch', 'Unexpected download size')
            while True:
                require(not cancelled.is_set(), 'cancelled', 'Download cancelled')
                chunk = source.read(min(1024**2, bundle['size'] - received + 1))
                if not chunk:
                    break
                received += len(chunk)
                require(received <= bundle['size'], 'size_mismatch', 'Download exceeds signed size')
                dest.write(chunk)
                digest.update(chunk)
                progress(received, bundle['size'])
            require(received == bundle['size'], 'size_mismatch', 'Incomplete download')
            require(digest.hexdigest() == bundle['sha256'], 'hash_mismatch', 'Bundle SHA-256 mismatch')
            dest.flush()
            import os
            os.fsync(dest.fileno())


def verify_signature(data, signature, public_key):
    try:
        with tempfile.TemporaryDirectory(prefix='release-signature-') as directory:
            directory = Path(directory)
            (directory / 'data').write_bytes(data)
            (directory / 'signature').write_bytes(signature)
            result = subprocess.run(['openssl', 'dgst', '-sha256', '-verify', str(public_key),
                '-signature', str(directory / 'signature'), str(directory / 'data')],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        require(result.returncode == 0, 'bad_signature', 'Release signature rejected')
    except (OSError, subprocess.TimeoutExpired) as error:
        raise APIError('verification_failed', 'Signature verifier unavailable') from error


def verify_offer(envelope, config, now=None):
    keys(envelope, ('signed', 'signature'))
    value = envelope['signed']
    keys(value, ('schema', 'profile', 'layout', 'version', 'sequence', 'expires', 'notes', 'bundle'))
    require(type(envelope['signature']) is str and len(envelope['signature']) <= 16384,
            'bad_signature', 'Invalid signature encoding')
    try:
        signature = base64.b64decode(envelope['signature'], validate=True)
    except ValueError as error:
        raise APIError('bad_signature', 'Invalid signature encoding') from error
    verify_signature(canonical(value), signature, config['public_key'])
    require(type(value['schema']) is int and value['schema'] == 1, 'incompatible', 'Unsupported metadata schema')
    require(value['profile'] == PROFILE and type(value['layout']) is int and value['layout'] == LAYOUT,
            'incompatible', 'Release profile/layout mismatch')
    require(type(value['version']) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]{0,63}', value['version']),
            'invalid_release', 'Invalid version')
    require(type(value['sequence']) is int and value['sequence'] > 0, 'invalid_release', 'Invalid release sequence')
    require(type(value['expires']) is int and value['expires'] > (time.time() if now is None else now),
            'expired', 'Release metadata expired; check device clock')
    require(type(value['notes']) is str and len(value['notes']) <= 8192, 'invalid_release', 'Release notes too large')
    keys(value['bundle'], ('url', 'size', 'sha256'))
    bundle = value['bundle']
    require(type(bundle['size']) is int and 0 < bundle['size'] <= MAX_BUNDLE, 'invalid_release', 'Invalid bundle size')
    require(type(bundle['sha256']) is str and re.fullmatch('[a-f0-9]{64}', bundle['sha256']),
            'invalid_release', 'Invalid bundle digest')
    allow_http = config.get('allow_http_loopback', False)
    require(url_origin(bundle['url'], allow_http) == url_origin(config['manifest_url'], allow_http),
            'origin_mismatch', 'Bundle must share the metadata origin')
    return hashlib.sha256(canonical(value)).hexdigest(), value


def verify_bundle(path, version, public_key):
    """Bind the offer to the inner signed release before calling the baseline."""
    try:
        with tempfile.TemporaryDirectory(prefix='verify-', dir=path.parent) as directory:
            entries = archive_read(path, directory)
            verify_signature(entries['release.json'], entries['release.sig'], public_key)
            verify_signature(entries['sw-description'], entries['sw-description.sig'], public_key)
            release = loads(entries['release.json'])
            require(release['version'] == version, 'version_mismatch', 'Offer and bundle versions differ')
            images = {name: entries[name] for name in ('boot-a.vfat', 'boot-b.vfat', 'rootfs.ext4')}
            require(release == metadata(version, images) and entries['sw-description'] == description(release),
                    'invalid_bundle', 'Bundle contents do not match signed release')
    except (AssertionError, KeyError, ValueError, UnicodeError) as error:
        raise APIError('invalid_bundle', 'Unsupported bundle structure') from error
