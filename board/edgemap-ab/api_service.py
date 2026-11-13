#!/usr/bin/env python3
"""Opt-in Unix-socket API. The existing CLI remains the sole slot installer."""
import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socketserver
import stat
import subprocess
import sys
import threading
import time
import uuid
from remote_release import (APIError, Fetcher, RESERVE, canonical, keys, loads,
                            require, verify_bundle, verify_offer, url_origin)

ACTIVE = {'checking', 'downloading', 'installing'}


def atomic(path, value):
    stage = path.with_name(path.name + '.new')
    with stage.open('wb') as out:
        out.write(canonical(value))
        out.flush()
        os.fsync(out.fileno())
    os.replace(stage, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def provision_sources(config):
    """Seed new persistent settings on existing images without replacing edits."""
    path = Path(config.get('sources_file', '/etc/default/edgemap-update-sources.json'))
    require(path.is_absolute(), 'invalid_config', 'Source configuration path must be absolute')
    if path.exists():
        return
    template = Path('/usr/share/edgemap-update-api/sources.example.json')
    sources = loads(template.read_bytes())
    # Carry an already-configured private-CA local source forward from older
    # images. Never copy private keys or replace the release verification key.
    if config.get('ca_file') and config.get('manifest_url') != sources['remote']['manifest_url']:
        sources['local'] = dict(manifest_url=config['manifest_url'], ca_file=config['ca_file'])
    atomic(path, sources)
    path.chmod(0o600)


class Device:
    def status(self):
        result = subprocess.run(['/usr/sbin/edgemap-update', 'status'], capture_output=True, timeout=15)
        require(result.returncode == 0, 'device_unavailable', 'Baseline status failed or another CLI operation holds its lock')
        value = loads(result.stdout)
        value['version'] = Path('/etc/edgemap-ab/version').read_text().strip()
        return value

    def install(self, bundle, log):
        with log.open('wb') as output:
            result = subprocess.run(['/usr/sbin/edgemap-update', 'install', str(bundle)],
                stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        require(result.returncode == 0, 'installation_failed', 'Baseline installation failed; inspect install.log and device state')

    def finish(self):
        # Serialize the reboot request against the independent baseline CLI.
        with open('/run/edgemap-update.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = subprocess.run(['systemctl', '--no-block', 'reboot'], capture_output=True, timeout=10)
            require(result.returncode == 0, 'reboot_failed', 'Normal restart request failed')


class LabDevice:
    def status(self):
        return dict(slot='a', trial=False, state={}, version='lab-installed')

    def install(self, bundle, log):
        raise APIError('lab_install_disabled', 'Lab backend never invokes SWUpdate or reboots')

    def finish(self):
        raise APIError('lab_install_disabled', 'Lab backend never invokes SWUpdate or reboots')


class Engine:
    def __init__(self, config, device, fetcher=None):
        allowed = {'manifest_url', 'public_key', 'data_dir', 'allow_http_loopback', 'ca_file', 'sources_file'}
        require(type(config) is dict and set(config) <= allowed and {'manifest_url', 'public_key'} <= set(config),
                'invalid_config', 'Unsupported configuration fields')
        require(type(config.get('allow_http_loopback', False)) is bool, 'invalid_config', 'Invalid HTTP lab setting')
        self.base_config = dict(config)
        self.config = dict(config)
        self.device = device
        self.directory = Path(config.get('data_dir', '/data/update-api'))
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        require(not self.directory.is_symlink() and self.directory.is_dir(), 'invalid_config', 'Data directory must be private')
        self.directory.chmod(0o700)
        self.file = self.directory / 'service.json'
        self.saved = loads(self.file.read_bytes()) if self.file.exists() else {}
        self.source = self.saved.get('source')
        if self.source:
            self.config, self.fetcher = self._source_config(self.source)
        else:
            self.fetcher = fetcher or Fetcher(config['manifest_url'], config.get('allow_http_loopback', False), config.get('ca_file'))
        self.job = self.saved.get('job', dict(phase='idle', operation=None))
        if self.job.get('phase') in ACTIVE:
            self.job = dict(self.job, phase='interrupted', error=dict(code='interrupted', message='Service restarted; inspect device state before retrying'))
        self.lock = threading.RLock()
        self.cancelled = threading.Event()
        self.worker = None
        self.cached_device = None
        self.installing_baseline = False
        # Only known temporary payloads owned by this service are discarded.
        (self.directory / 'download.part').unlink(missing_ok=True)
        self._save()

    def _source_config(self, source):
        require(source in ('remote', 'local'), 'invalid_source', 'Select remote or local')
        path = Path(self.base_config.get('sources_file', '/etc/default/edgemap-update-sources.json'))
        require(path.is_absolute(), 'invalid_config', 'Source configuration path must be absolute')
        try:
            sources = loads(path.read_bytes())
        except (OSError, ValueError) as error:
            raise APIError('invalid_config', f'Cannot read source configuration: {path}') from error
        require(type(sources) is dict and set(sources) <= {'remote', 'local'},
                'invalid_config', 'Only remote and local source names are supported')
        entry = sources.get(source)
        require(type(entry) is dict and set(entry) <= {'manifest_url', 'ca_file'} and
                type(entry.get('manifest_url')) is str and bool(entry['manifest_url']),
                'source_unconfigured', f'Configure {source} in {path}')
        url_origin(entry['manifest_url'])  # Named production sources always require HTTPS.
        if entry.get('ca_file') is not None:
            require(type(entry['ca_file']) is str and Path(entry['ca_file']).is_absolute(),
                    'invalid_config', 'Source CA path must be absolute')
        config = dict(self.base_config)
        config.pop('ca_file', None)
        config.update(entry, allow_http_loopback=False)
        # Source files cannot change the verifier key or persistent state directory.
        try:
            fetcher = Fetcher(config['manifest_url'], ca_file=config.get('ca_file'))
        except (OSError, ValueError) as error:
            raise APIError('invalid_config', f'Cannot initialize {source} HTTPS trust: {error}') from error
        return config, fetcher

    def select_source(self, source):
        require(self.job['phase'] not in ACTIVE, 'busy', 'An update job is already running')
        self._normal()
        config, fetcher = self._source_config(source)
        if self.source != source or config != self.config:
            saved = dict(self.saved, source=source)
            saved.pop('offer', None)
            saved.pop('downloaded', None)
            job = dict(phase='idle', operation=None)
            saved['job'] = job
            atomic(self.file, saved)  # Keep global highest sequence/offer identity.
            self.saved, self.job = saved, job
            self.source, self.config, self.fetcher = source, config, fetcher
            self.bundle().unlink(missing_ok=True)
            (self.directory / 'download.part').unlink(missing_ok=True)
        else:
            self.fetcher = fetcher  # Reload CA contents even if their path is unchanged.
        return dict(source=source, manifest_url=config['manifest_url'])

    def _save(self):
        self.saved['job'] = self.job
        atomic(self.file, self.saved)

    def _set(self, **value):
        with self.lock:
            self.job.update(value)
            self._save()

    def _offer(self, offer_id=None):
        require('offer' in self.saved, 'no_offer', 'Check for an update first')
        identity, value = verify_offer(self.saved['offer'], self.config)
        require(offer_id is None or offer_id == identity, 'offer_changed', 'Acceptance does not match the verified offer')
        return identity, value

    def _device_status(self):
        # Polling and worker preflight must not contend on the baseline CLI lock.
        with self.lock:
            # The delegated controller owns the process lock during installation.
            # Keep polling responsive without racing it at process startup.
            if self.installing_baseline:
                require(self.cached_device is not None, 'device_unavailable', 'No pre-install status available')
                return copy.deepcopy(self.cached_device)
            value = self.device.status()
            self.cached_device = value
            return value

    def _install_baseline(self):
        # Wait for any in-flight status call before delegating; subsequent polls
        # use the cached preflight state until the installer has exited.
        with self.lock:
            self.installing_baseline = True
        try:
            self.device.install(self.bundle(), self.directory / 'install.log')
        finally:
            with self.lock:
                self.installing_baseline = False

    def _normal(self):
        value = self._device_status()
        require(not value['trial'] and value['state'].get('phase') not in ('installing', 'pending', 'trial', 'committing'),
                'trial_outstanding', 'Finish the current update and ordinary reboot first')
        return value

    def status(self):
        with self.lock:
            device_error = None
            try:
                device = self._device_status()
            except (APIError, OSError, subprocess.TimeoutExpired) as error:
                device = self.cached_device
                device_error = str(error)
            offer = None
            offer_error = None
            try:
                identity, value = self._offer()
                offer = dict(value, offer_id=identity)
            except APIError as error:
                if error.code != 'no_offer':
                    offer_error = dict(code=error.code, message=str(error))
            job = copy.deepcopy(self.job)
            # Baseline records, not transfer job state, determine post-reboot result.
            if device and job.get('operation') == 'install' and offer:
                state = device['state']
                if state.get('version') == offer['version'] and state.get('phase') in ('pending', 'trial', 'committing', 'committed', 'fallback', 'failed'):
                    job['device_outcome'] = state['phase']
            ready = bool(offer and self.saved.get('downloaded') == offer['offer_id'] and self.bundle().is_file())
            return dict(source=self.source, manifest_url=self.config['manifest_url'],
                        device=device, device_error=device_error, job=job, offer=offer,
                        offer_error=offer_error, download_ready=ready)

    def bundle(self):
        return self.directory / 'download.swu'

    def dispatch(self, method, params):
        require(type(params) is dict, 'invalid_request', 'Params must be an object')
        if method == 'status':
            keys(params, ())
            return self.status()
        with self.lock:
            if method == 'select-source':
                keys(params, ('source',))
                require(type(params['source']) is str, 'invalid_source', 'Source must be a name')
                return self.select_source(params['source'])
            if method == 'cancel':
                keys(params, ())
                require(self.job['phase'] in ('checking', 'downloading'), 'not_cancellable', 'Only check/download jobs can be cancelled')
                self.cancelled.set()
                return dict(job_id=self.job['job_id'], cancellation_requested=True)
            if method == 'finish':
                keys(params, ('accept',))
                require(params['accept'] is True, 'acceptance_required', 'Explicit restart acceptance required')
                require(self.job['phase'] not in ACTIVE, 'busy', 'An update job is already running')
                current = self._device_status()
                state = current['state']
                require(current['trial'] is True and state.get('phase') == 'committed' and
                        state.get('target') == current['slot'] and state.get('version') == current['version'],
                        'not_committed_trial', 'Only a confirmed trial can be finished')
                self.device.finish()
                return dict(restart_requested=True)
            require(method in ('check', 'download', 'install'), 'unknown_method', 'Unknown API method')
            require(self.job['phase'] not in ACTIVE, 'busy', 'An update job is already running')
            offer = None
            if method == 'check':
                keys(params, ())
            else:
                keys(params, ('offer_id', 'accept'))
                require(type(params['offer_id']) is str and params['accept'] is True,
                        'acceptance_required', 'Explicit acceptance of an offer_id is required')
                identity, offer = self._offer(params['offer_id'])
                current = self._normal()
                require(offer['version'] != current['version'], 'already_installed', 'Offered version is already running')
                if method == 'download':
                    require(shutil.disk_usage(self.directory).free > offer['bundle']['size'] + RESERVE,
                            'insufficient_space', 'Not enough space for download plus baseline staging reserve')
                else:
                    require(self.saved.get('downloaded') == identity and self.bundle().is_file(),
                            'not_downloaded', 'Download this exact offer first')
            self.cancelled.clear()
            self.job = dict(job_id=uuid.uuid4().hex, operation=method,
                phase={'check':'checking', 'download':'downloading', 'install':'installing'}[method],
                offer_id=params.get('offer_id'), bytes_received=0,
                bytes_total=offer['bundle']['size'] if offer else None, error=None, started=int(time.time()))
            self._save()
            self.worker = threading.Thread(target=self._work, args=(method, offer), daemon=True)
            self.worker.start()
            return dict(job_id=self.job['job_id'])

    def _work(self, method, offer):
        try:
            if method == 'check':
                envelope = self.fetcher.metadata(self.config['manifest_url'], self.cancelled)
                identity, value = verify_offer(envelope, self.config)
                with self.lock:
                    require(not self.cancelled.is_set(), 'cancelled', 'Check cancelled')
                    high = self.saved.get('highest', {})
                    require(value['sequence'] >= high.get('sequence', 0), 'replay_rejected', 'Older metadata sequence rejected')
                    require(value['sequence'] != high.get('sequence') or identity == high['offer_id'],
                            'replay_rejected', 'Sequence was reused for a different offer')
                    device = self._device_status()
                    self.saved['offer'] = envelope
                    self.saved['highest'] = dict(sequence=value['sequence'], offer_id=identity)
                    self._set(phase='no_update' if value['version'] == device['version'] else 'available', offer_id=identity)
            elif method == 'download':
                temporary = self.directory / 'download.part'
                temporary.unlink(missing_ok=True)
                try:
                    def progress(done, total):
                        with self.lock:
                            self.job.update(bytes_received=done, bytes_total=total)
                    self.fetcher.download(offer, temporary, self.cancelled, progress)
                    with self.lock:
                        require(not self.cancelled.is_set(), 'cancelled', 'Download cancelled')
                        self._offer(self.job['offer_id'])  # Recheck expiry before promoting.
                        os.replace(temporary, self.bundle())
                        self.saved['downloaded'] = self.job['offer_id']
                        self._set(phase='downloaded')
                finally:
                    temporary.unlink(missing_ok=True)
            else:
                self._set(stage='verifying_bundle')
                self._offer(self.job['offer_id'])
                current = self._normal()
                require(current['version'] != offer['version'], 'already_installed', 'Offered release is already running')
                require(shutil.disk_usage(self.directory).free > RESERVE, 'insufficient_space', 'Baseline staging reserve unavailable')
                with self.bundle().open('rb') as source:
                    digest = hashlib.file_digest(source, 'sha256').hexdigest()
                require(self.bundle().stat().st_size == offer['bundle']['size'] and digest == offer['bundle']['sha256'],
                        'hash_mismatch', 'Downloaded bundle changed')
                verify_bundle(self.bundle(), offer['version'], self.config['public_key'])
                self._offer(self.job['offer_id'])  # Expiry may have passed during verification.
                self._set(stage='installing_slots')
                if isinstance(self.device, Device):
                    from swupdate_progress import Monitor
                    def progress(value):
                        with self.lock:
                            self.job['swupdate'] = value
                    with Monitor(progress):
                        self._install_baseline()
                else:
                    self._install_baseline()
                self._set(phase='installed')
        except Exception as error:
            code = error.code if isinstance(error, APIError) else 'operation_failed'
            message = str(error) if isinstance(error, APIError) else 'Operation failed; inspect service journal'
            if not isinstance(error, APIError):
                import traceback
                traceback.print_exc()
            self._set(phase='cancelled' if code == 'cancelled' else 'failed', error=dict(code=code, message=message))


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        identity = None
        try:
            raw = self.rfile.readline(16385)
            require(len(raw) <= 16384 and raw.endswith(b'\n'), 'invalid_request', 'Request too large or missing newline')
            request = loads(raw)
            keys(request, ('api', 'id', 'method', 'params'))
            require(type(request['api']) is int and request['api'] == 1, 'unsupported_api', 'API version 1 required')
            require(type(request['id']) is str and len(request['id']) <= 128 and type(request['method']) is str,
                    'invalid_request', 'Invalid request ID or method')
            identity = request['id']
            value = self.server.engine.dispatch(request['method'], request['params'])
            response = dict(api=1, id=identity, ok=True, result=value)
        except APIError as error:
            response = dict(api=1, id=identity, ok=False, error=dict(code=error.code, message=str(error)))
        except Exception:
            response = dict(api=1, id=identity, ok=False, error=dict(code='internal_error', message='Request failed; inspect service journal'))
        self.wfile.write(canonical(response) + b'\n')


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True

    def __init__(self, socket_path, engine):
        self.engine = engine
        super().__init__(str(socket_path), Handler)
        os.chmod(socket_path, 0o600)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=Path('/etc/default/edgemap-updates.json'))
    parser.add_argument('--socket', type=Path, default=Path('/run/edgemap-update-api/control.sock'))
    parser.add_argument('--lab', action='store_true', help='Simulated status; NEVER installs or reboots')
    args = parser.parse_args()
    require(args.lab or os.geteuid() == 0, 'permission_denied', 'Target service must run as root')
    device = LabDevice() if args.lab else Device()
    device.status()  # Validate mounted Data before opening a persistent directory.
    args.socket.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    args.socket.parent.chmod(0o700)
    with (args.socket.parent / 'service.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config = loads(args.config.read_bytes())
        provision_sources(config)
        engine = Engine(config, device)
        if args.socket.exists():
            require(stat.S_ISSOCK(args.socket.lstat().st_mode), 'invalid_config', 'Socket path contains a non-socket file')
            args.socket.unlink()
        with Server(args.socket, engine) as server:
            def stop(*_):
                engine.cancelled.set()
                threading.Thread(target=server.shutdown, daemon=True).start()
            signal.signal(signal.SIGTERM, stop)
            signal.signal(signal.SIGINT, stop)
            try:
                server.serve_forever(poll_interval=0.2)
            finally:
                args.socket.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
