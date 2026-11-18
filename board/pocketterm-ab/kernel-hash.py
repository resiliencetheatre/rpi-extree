#!/usr/bin/env python3
"""Cache and record a configured PocketTerm kernel archive; never run make."""
import argparse
import fcntl
import gzip
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile


class HashError(ValueError):
    pass


def expand(value, variables):
    # Interpret only these literal path variables, never evaluate Make/shell code.
    for name, replacement in variables.items():
        value = value.replace('${' + name + '}', str(replacement))
        value = value.replace('$(' + name + ')', str(replacement))
    if '$' in value or '\\' in value or '\n' in value:
        raise HashError(f'Unsupported variable/expression: {value}')
    return value


def plan(workspace, output, environment):
    workspace, output = workspace.resolve(), output.resolve()
    buildroot, external = workspace / 'buildroot', workspace / 'rpi-extree'
    if not (buildroot / 'Makefile').is_file() or not (external / 'external.desc').is_file():
        raise HashError('Cannot identify Buildroot and external tree from script location')
    if output == workspace or output in workspace.parents or any(
            output == source or source in output.parents for source in (buildroot, external, workspace / 'lvgl-console')):
        raise HashError('Select a separate configured build output')
    external_record = output / '.br2-external.mk'
    if external_record.exists():
        match = re.search(r'^export BR2_EXTERNAL_rpi_PATH = (.+)$', external_record.read_text(), re.M)
        if not match or Path(match[1]).resolve() != external:
            raise HashError('Configured output belongs to another external tree')
    config_file = output / '.config'
    text = config_file.read_text()
    config = {}
    for line in text.splitlines():
        match = re.fullmatch(r'(BR2_\w+)=(.*)', line)
        if match:
            value = match[2]
            config[match[1]] = value[1:-1] if value.startswith('"') and value.endswith('"') else value
    if 'pocketterm-ab/post-build.sh' not in config.get('BR2_ROOTFS_POST_BUILD_SCRIPT', ''):
        raise HashError('Output is not configured for PocketTerm A/B')
    if config.get('BR2_LINUX_KERNEL_CUSTOM_TARBALL') != 'y':
        raise HashError('Only pinned custom Raspberry Pi kernel tarballs are supported')
    if config.get('BR2_KERNEL_HEADERS_CUSTOM_TARBALL') == 'y' or config.get('BR2_KERNEL_HEADERS_CUSTOM_GIT') == 'y':
        raise HashError('Separate custom headers require their own source/hash review')
    url = config.get('BR2_LINUX_KERNEL_CUSTOM_TARBALL_LOCATION', '')
    url = re.sub(r'\$\(call github,raspberrypi,linux,([a-f0-9]{40})\)',
                 r'https://github.com/raspberrypi/linux/archive/\1', url)
    match = re.fullmatch(r'https://github\.com/raspberrypi/linux/archive/([a-f0-9]{40})/(linux-\1\.tar\.gz)', url)
    if not match:
        raise HashError('Expected Raspberry Pi GitHub archive URL with one full 40-character commit and matching filename')
    commit, filename = match.groups()
    variables = dict(TOPDIR=buildroot, BASE_DIR=output, BR2_EXTERNAL=external,
                     BR2_EXTERNAL_rpi_PATH=external, CONFIG_DIR=output)
    cache = Path(expand(environment.get('DL_DIR') or config.get('BR2_DL_DIR') or '$(TOPDIR)/dl', variables))
    if not cache.is_absolute():
        raise HashError('Download cache must resolve to an absolute path (or set absolute DL_DIR)')
    cache = cache.resolve()
    roots = [Path(value).resolve() for value in expand(config.get('BR2_GLOBAL_PATCH_DIR', ''), variables).split()]
    if any(not root.is_dir() for root in roots):
        raise HashError('Every active global patch directory must exist')
    writable, checked = [], []
    for package, package_dir in [('linux', buildroot / 'linux'), ('linux-headers', buildroot / 'package/linux-headers')]:
        found = []
        for directory in [package_dir, *(root / package for root in roots)]:
            specific = directory / 'custom' / (package + '.hash')
            path = specific if specific.is_file() else directory / (package + '.hash')
            if path.is_file():
                resolved = path.resolve()
                checked.append(resolved)
                if external in resolved.parents and directory != package_dir:
                    found.append(resolved)
        if not found:
            raise HashError(f'No existing active external {package}.hash file; configure BR2_GLOBAL_PATCH_DIR first')
        writable.extend(found)
    return dict(url=url, filename=filename, commit=commit, archive=cache / 'linux' / filename,
                writable=list(dict.fromkeys(writable)), checked=list(dict.fromkeys(checked)),
                config_file=config_file, config_text=text)


def records(text, filename):
    result = []
    for line in text.splitlines():
        fields = line.split()
        if not fields or fields[0].startswith('#'):
            continue
        if len(fields) >= 3 and fields[2] == filename:
            if len(fields) != 3 or fields[0] not in ('md5', 'sha1', 'sha224', 'sha256', 'sha384', 'sha512'):
                raise HashError(f'Unsupported hash entry for {filename}: {line}')
            result.append((fields[0], fields[1]))
    return result


def download(url, destination):
    print('Downloading archive over verified HTTPS (curl progress follows)', flush=True)
    subprocess.run(['curl', '--fail', '--location', '--proto', '=https', '--proto-redir', '=https',
                    '--retry', '3', '--connect-timeout', '15', '--output', str(destination), url], check=True)


def validate_archive(path, commit):
    # No extraction. Require the expected source tree and a complete gzip stream.
    with tarfile.open(path, 'r|gz') as archive:
        for member in archive:
            if member.name == f'linux-{commit}/Makefile':
                if not member.isfile() or member.size > 1024 * 1024:
                    raise HashError('Unexpected kernel Makefile in source archive')
                break
        else:
            raise HashError('Archive does not contain the configured kernel source tree')
    with gzip.open(path, 'rb') as stream:
        while stream.read(1024 * 1024):
            pass


def digests(path, algorithms):
    values = {name: hashlib.new(name) for name in algorithms}
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            for value in values.values():
                value.update(block)
    return {name: value.hexdigest() for name, value in values.items()}


def flush_directory(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_text(path, text):
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    stage = Path(name)
    try:
        with os.fdopen(fd, 'w') as stream:
            os.fchmod(stream.fileno(), path.stat().st_mode & 0o777)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(stage, path)
        flush_directory(path.parent)
    finally:
        stage.unlink(missing_ok=True)


def prepare(selected, downloader=download):
    archive = selected['archive']
    archive.parent.mkdir(parents=True, exist_ok=True)
    # Same per-package cache lock used by Buildroot's download wrapper.
    with (archive.parent / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        originals = {path: path.read_text() for path in selected['checked']}
        known = [(algorithm, digest, path) for path, text in originals.items()
                 for algorithm, digest in records(text, selected['filename'])]
        algorithms = {'sha256', *(algorithm for algorithm, _, _ in known)}
        temporary = None
        try:
            if archive.is_symlink():
                raise HashError('Refusing a symlinked cache archive')
            if archive.exists():
                print(f'Reusing cache: {archive}', flush=True)
                source = archive
            else:
                fd, name = tempfile.mkstemp(prefix='.kernel-hash-', dir=archive.parent)
                os.close(fd)
                temporary = Path(name)
                downloader(selected['url'], temporary)
                source = temporary
            validate_archive(source, selected['commit'])
            values = digests(source, algorithms)
            for algorithm, digest, path in known:
                if values[algorithm] != digest:
                    raise HashError(f'Checksum conflict in {path}: {algorithm} for {selected["filename"]}; nothing replaced')
            if selected['config_file'].read_text() != selected['config_text']:
                raise HashError('Output configuration changed during hashing; rerun when idle')
            if any(path.read_text() != text for path, text in originals.items()):
                raise HashError('Hash files changed during hashing; rerun when idle')
            if temporary:
                with temporary.open('rb') as stream:
                    os.fsync(stream.fileno())
                os.replace(temporary, archive)
                flush_directory(archive.parent)
            line = f'sha256  {values["sha256"]}  {selected["filename"]}\n'
            print(line.rstrip(), flush=True)
            for path in selected['writable']:
                text = originals[path]
                if ('sha256', values['sha256']) in records(text, selected['filename']):
                    print(f'Already recorded: {path}', flush=True)
                else:
                    atomic_text(path, text + ('' if not text or text.endswith('\n') else '\n') + line)
                    print(f'Added: {path}', flush=True)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='Configured Buildroot output; relative paths resolve from workspace')
    parser.add_argument('--dry-run', action='store_true', help='Show URL/cache/hash paths without downloading or writing')
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[3]
    output = args.output if args.output.is_absolute() else workspace / args.output
    try:
        selected = plan(workspace, output, os.environ)
        print(f'Configuration: {selected["config_file"]}\nURL: {selected["url"]}\nCache: {selected["archive"]}', flush=True)
        for path in selected['writable']:
            print(f'Hash file: {path}', flush=True)
        print('This records the downloaded bytes; review the upstream commit independently.', flush=True)
        if not args.dry_run:
            with Path(__file__).with_name('.kernel-hash.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                prepare(selected)
            print('Done. Review the hash diff, then refresh kernel/modules and build separately.', flush=True)
        return 0
    except (OSError, ValueError, KeyError, EOFError, tarfile.TarError, subprocess.CalledProcessError) as error:
        print(f'kernel-hash: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
