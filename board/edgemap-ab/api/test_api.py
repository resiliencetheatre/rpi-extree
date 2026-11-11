#!/usr/bin/env python3
"""Host integration tests: real signatures, loopback downloads and Unix RPC.

No test invokes a real installer, block-device operation or reboot.
"""
import base64
import copy
import functools
import http.server
import io
import urllib.parse
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fixture import create
from api_service import Device, Engine, LabDevice, Server, Handler
from api_client import call
from remote_release import APIError, NoRedirect, canonical, loads, require, url_origin, verify_offer


class FakeDevice:
    def __init__(self):
        self.value = dict(slot='a', trial=False, state={}, version='lab-installed')
        self.calls = []
    def status(self):
        return copy.deepcopy(self.value)
    def install(self, path, log):
        self.calls.append(path)
        log.write_text('Simulated baseline call; no hardware touched\n')


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def sockets_available():
    try:
        for family in (socket.AF_INET, socket.AF_UNIX):
            with socket.socket(family, socket.SOCK_STREAM):
                pass
        return True
    except PermissionError:
        return False

NETWORK = sockets_available()

class FileResponse(io.BytesIO):
    def __init__(self, path):
        super().__init__(path.read_bytes())
        self.headers = {'Content-Length': str(path.stat().st_size)}

class FileOpener:
    """Only the HTTP IO boundary is replaced when sandbox sockets are denied."""
    def __init__(self, root):
        self.root = root
    def open(self, request, **kwargs):
        path = urllib.parse.urlsplit(request.full_url).path
        assert path in ('/latest.json', '/lab-1.swu')
        return FileResponse(self.root / path.lstrip('/'))


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='api-test-')
        self.root = Path(self.temp.name)
        www = self.root / 'www'
        handler = functools.partial(QuietHandler, directory=str(www))
        self.http = None
        self.port = 9080
        if NETWORK:
            self.http = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
            self.port = self.http.server_port
        create(self.root, self.port)
        if self.http:
            self.http_thread = threading.Thread(target=self.http.serve_forever, kwargs={'poll_interval':0.01}, daemon=True)
            self.http_thread.start()
        self.config = loads((self.root / 'lab-config.json').read_bytes())
        self.device = FakeDevice()
        self.engine = Engine(self.config, self.device)
        if not NETWORK:
            self.engine.fetcher.opener = FileOpener(www)
        self.space = patch('api_service.shutil.disk_usage', return_value=type('Space', (), {'free':32*1024**3})())
        self.space.start()

    def tearDown(self):
        if self.engine.worker:
            self.engine.cancelled.set()
            self.engine.worker.join(20)
            self.assertFalse(self.engine.worker.is_alive())
        if self.http:
            self.http.shutdown()
            self.http.server_close()
            self.http_thread.join(2)
        self.space.stop()
        self.temp.cleanup()

    def wait(self):
        self.engine.worker.join(15)
        self.assertFalse(self.engine.worker.is_alive())
        return self.engine.status()

    def check(self):
        self.engine.dispatch('check', {})
        state = self.wait()
        self.assertEqual(state['job']['phase'], 'available', state)
        return state['offer']['offer_id']

    def download(self, identity):
        self.engine.dispatch('download', dict(offer_id=identity, accept=True))
        state = self.wait()
        self.assertEqual(state['job']['phase'], 'downloaded', state)
        return state

    def resign(self, **updates):
        path = self.root / 'www/latest.json'
        envelope = loads(path.read_bytes())
        envelope['signed'].update(updates)
        source = self.root / 'secrets/sign'
        source.write_bytes(canonical(envelope['signed']))
        signature = subprocess.check_output(['openssl','dgst','-sha256','-sign',str(self.root/'secrets/private.pem'),str(source)])
        envelope['signature'] = base64.b64encode(signature).decode()
        path.write_bytes(canonical(envelope))
        return envelope

    @unittest.skipUnless(NETWORK, 'Sandbox denies sockets; run on host for HTTP/Unix integration')
    def test_unix_protocol_check_download_install_and_restart(self):
        path = self.root / 'control.sock'
        with Server(path, self.engine) as server:
            thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval':0.01}, daemon=True)
            thread.start()
            try:
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertTrue(call(path, 'status', {})['ok'])
                result = call(path, 'check', {})
                self.assertTrue(result['ok'])
                identity = self.wait()['offer']['offer_id']
                self.assertFalse(self.engine.bundle().exists(), 'Check must not fetch bundle')
                self.assertFalse(call(path,'download',dict(offer_id=identity,accept=False))['ok'])
                self.assertTrue(call(path,'download',dict(offer_id=identity,accept=True))['ok'])
                self.assertTrue(self.wait()['download_ready'])
                self.assertEqual(self.device.calls, [])
                self.assertTrue(call(path,'install',dict(offer_id=identity,accept=True))['ok'])
                self.assertEqual(self.wait()['job']['phase'], 'installed')
                self.assertEqual(self.device.calls, [self.engine.bundle()])
            finally:
                server.shutdown()
                thread.join(2)
        restarted = Engine(self.config, self.device)
        self.assertTrue(restarted.status()['download_ready'])
        self.assertEqual(self.device.calls, [self.engine.bundle()], 'Restart must never auto-install')

    def test_device_preflight_serializes_with_status_poll(self):
        entered = threading.Event()
        release = threading.Event()
        second_done = threading.Event()
        calls = []
        original = self.device.status
        def slow_status():
            calls.append(True)
            if len(calls) == 1:
                entered.set()
                self.assertTrue(release.wait(2))
            return original()
        self.device.status = slow_status
        first = threading.Thread(target=self.engine._normal)
        second = threading.Thread(target=lambda: (self.engine.status(), second_done.set()))
        first.start()
        self.assertTrue(entered.wait(2))
        second.start()
        try:
            self.assertFalse(second_done.wait(0.05))
            self.assertEqual(len(calls), 1)
        finally:
            release.set()
            first.join(2)
            second.join(2)
        self.assertTrue(second_done.is_set())
        self.assertEqual(len(calls), 2)

    def test_finish_requires_confirmed_trial_and_acceptance(self):
        from unittest.mock import Mock
        self.device.finish = Mock()
        with self.assertRaises(APIError):
            self.engine.dispatch('finish', {'accept': True})
        self.device.value.update(trial=True, state=dict(phase='committed', target='a', version='lab-installed'))
        with self.assertRaises(APIError):
            self.engine.dispatch('finish', {'accept': False})
        self.engine.job['phase'] = 'installing'
        with self.assertRaises(APIError):
            self.engine.dispatch('finish', {'accept': True})
        self.engine.job['phase'] = 'idle'
        self.device.value['state']['target'] = 'b'
        with self.assertRaises(APIError):
            self.engine.dispatch('finish', {'accept': True})
        self.device.finish.assert_not_called()
        self.device.value['state']['target'] = 'a'
        self.assertTrue(self.engine.dispatch('finish', {'accept': True})['restart_requested'])
        self.device.finish.assert_called_once()
        with self.assertRaises(APIError):
            LabDevice().finish()

    def test_bad_signature_profile_expiry_and_duplicate_json(self):
        for field, value, code in [('profile','wrong-profile','incompatible'),
                                    ('layout',2,'incompatible'),('expires',1,'expired')]:
            envelope = self.resign(**{field:value})
            with self.assertRaises(APIError) as caught:
                verify_offer(envelope,self.config)
            self.assertEqual(caught.exception.code,code)
            # Restore valid fields for the next case.
            self.resign(profile='edgemap-lite-situation-rpi4-v1',layout=1,expires=int(time.time())+86400)
        envelope = loads((self.root/'www/latest.json').read_bytes())
        envelope['signed']['notes']='tampered'
        with self.assertRaises(APIError) as caught:
            verify_offer(envelope,self.config)
        self.assertEqual(caught.exception.code,'bad_signature')
        with self.assertRaises(APIError):
            loads(b'{"signed":1,"signed":2}')

    def test_replay_and_changed_offer_consent(self):
        first=self.check()
        self.resign(sequence=2,notes='next offer')
        second=self.check()
        self.assertNotEqual(first,second)
        with self.assertRaises(APIError) as caught:
            self.engine.dispatch('download',dict(offer_id=first,accept=True))
        self.assertEqual(caught.exception.code,'offer_changed')
        self.resign(sequence=1)
        self.engine.dispatch('check',{})
        self.assertEqual(self.wait()['job']['error']['code'],'replay_rejected')
        self.resign(sequence=2,notes='mutated sequence')
        self.engine.dispatch('check',{})
        self.assertEqual(self.wait()['job']['error']['code'],'replay_rejected')

    def test_truncated_and_hash_mismatched_downloads_never_install(self):
        identity=self.check()
        bundle=self.root/'www/lab-1.swu'
        original=bundle.read_bytes()
        bundle.write_bytes(original[:-20])
        self.engine.dispatch('download',dict(offer_id=identity,accept=True))
        state=self.wait()
        self.assertEqual(state['job']['error']['code'],'size_mismatch')
        self.assertFalse(state['download_ready'])
        self.assertFalse((self.engine.directory/'download.part').exists())
        bundle.write_bytes(original)
        envelope=loads((self.root/'www/latest.json').read_bytes())
        envelope['signed']['bundle']['sha256']='0'*64
        self.resign(sequence=2,bundle=envelope['signed']['bundle'])
        identity=self.check()
        self.engine.dispatch('download',dict(offer_id=identity,accept=True))
        self.assertEqual(self.wait()['job']['error']['code'],'hash_mismatch')
        self.assertEqual(self.device.calls,[])

    def test_tampering_after_download_and_version_binding(self):
        identity=self.check()
        self.download(identity)
        self.engine.bundle().write_bytes(b'tampered')
        self.engine.dispatch('install',dict(offer_id=identity,accept=True))
        self.assertEqual(self.wait()['job']['error']['code'],'hash_mismatch')
        self.resign(sequence=2,version='lab-2')
        identity=self.check()
        self.download(identity)
        self.engine.dispatch('install',dict(offer_id=identity,accept=True))
        self.assertEqual(self.wait()['job']['error']['code'],'version_mismatch')
        self.assertEqual(self.device.calls,[])

    def test_trial_space_and_expiry_reject_without_install(self):
        identity=self.check()
        self.device.value['trial']=True
        with self.assertRaises(APIError) as caught:
            self.engine.dispatch('download',dict(offer_id=identity,accept=True))
        self.assertEqual(caught.exception.code,'trial_outstanding')
        self.device.value['trial']=False
        with patch('api_service.shutil.disk_usage',return_value=type('Space',(),{'free':1})()):
            with self.assertRaises(APIError) as caught:
                self.engine.dispatch('download',dict(offer_id=identity,accept=True))
        self.assertEqual(caught.exception.code,'insufficient_space')
        self.download(identity)
        with patch('remote_release.time.time',return_value=time.time()+172800):
            with self.assertRaises(APIError) as caught:
                self.engine.dispatch('install',dict(offer_id=identity,accept=True))
        self.assertEqual(caught.exception.code,'expired')
        self.assertEqual(self.device.calls,[])

    def test_busy_cancel_and_interrupted_restart(self):
        entered=threading.Event()
        def blocked(url,cancelled):
            entered.set()
            require(cancelled.wait(5),'test_timeout','Timed out')
            raise APIError('cancelled','Check cancelled')
        self.engine.fetcher.metadata=blocked
        self.engine.dispatch('check',{})
        self.assertTrue(entered.wait(2))
        with self.assertRaises(APIError) as caught:
            self.engine.dispatch('check',{})
        self.assertEqual(caught.exception.code,'busy')
        self.engine.dispatch('cancel',{})
        self.assertEqual(self.wait()['job']['phase'],'cancelled')
        self.engine.job=dict(phase='downloading',operation='download',job_id='interrupted')
        self.engine._save()
        (self.engine.directory/'download.part').write_bytes(b'partial')
        restarted=Engine(self.config,self.device)
        self.assertEqual(restarted.status()['job']['phase'],'interrupted')
        self.assertFalse((self.engine.directory/'download.part').exists())
        self.assertEqual(self.device.calls,[])

    def test_install_job_rejects_competing_actions_and_cancellation(self):
        identity=self.check()
        self.download(identity)
        entered,release=threading.Event(),threading.Event()
        def installing(path,log):
            entered.set()
            require(release.wait(5),'test_timeout','Install test timeout')
        with patch.object(self.device,'install',side_effect=installing):
            self.engine.dispatch('install',dict(offer_id=identity,accept=True))
            try:
                self.assertTrue(entered.wait(3))
                # UI polling must not invoke the controller while installation
                # owns (or is about to acquire) its nonblocking process lock.
                with patch.object(self.device, 'status', side_effect=AssertionError('status raced installer')):
                    self.assertIsNone(self.engine.status()['device_error'])
                    self.assertTrue(self.engine.installing_baseline)
                with self.assertRaises(APIError) as caught:
                    self.engine.dispatch('check',{})
                self.assertEqual(caught.exception.code,'busy')
                with self.assertRaises(APIError) as caught:
                    self.engine.dispatch('cancel',{})
                self.assertEqual(caught.exception.code,'not_cancellable')
            finally:
                release.set()
            self.assertEqual(self.wait()['job']['phase'],'installed')
            self.assertFalse(self.engine.installing_baseline)

    def test_url_policy_redirect_and_request_validation(self):
        for url in ('http://192.0.2.1/latest.json','http://localhost/latest.json','file:///etc/passwd',
                    'https://user:password@example.com/latest.json','https://example.com/path#fragment'):
            with self.assertRaises(APIError):
                url_origin(url,True)
        self.assertEqual(url_origin('http://127.0.0.1:9080/latest.json',True)[0],'http')
        envelope=loads((self.root/'www/latest.json').read_bytes())
        bundle=dict(envelope['signed']['bundle'],url='https://other.example/bundle.swu')
        envelope=self.resign(bundle=bundle)
        with self.assertRaises(APIError) as caught:
            verify_offer(envelope,self.config)
        self.assertEqual(caught.exception.code,'origin_mismatch')
        for method,params in [('status',{'extra':1}),('shell',{}),('check',{'url':'https://evil.example'})]:
            with self.assertRaises(APIError):
                self.engine.dispatch(method,params)
        from types import SimpleNamespace
        from unittest.mock import Mock
        request = Handler.__new__(Handler)
        request.request = Mock()
        request.server = SimpleNamespace(engine=self.engine)
        request.rfile = io.BytesIO(b'{"api":1,"id":"a","method":"status","params":{},"extra":1}\n')
        request.wfile = io.BytesIO()
        request.handle()
        self.assertFalse(json.loads(request.wfile.getvalue())['ok'])
        request.rfile = io.BytesIO(b'{"api":1,"id":"a","method":"status","params":{}}\n')
        request.wfile = io.BytesIO()
        request.handle()
        self.assertTrue(json.loads(request.wfile.getvalue())['ok'])
        with self.assertRaises(APIError) as caught:
            NoRedirect().redirect_request(None, None, None, None, None, None)
        self.assertEqual(caught.exception.code, 'redirect_rejected')

    def test_engine_positive_install_and_restart_requires_new_acceptance(self):
        identity=self.check()
        self.assertFalse(self.engine.bundle().exists())
        self.download(identity)
        self.assertEqual(self.device.calls, [])
        self.engine.dispatch('install',dict(offer_id=identity,accept=True))
        self.assertEqual(self.wait()['job']['phase'],'installed')
        self.assertEqual(self.device.calls,[self.engine.bundle()])
        restarted=Engine(self.config,self.device)
        self.assertTrue(restarted.status()['download_ready'])
        self.assertEqual(self.device.calls,[self.engine.bundle()])

    def test_lab_backend_and_baseline_cli_delegation(self):
        with self.assertRaises(APIError) as caught:
            LabDevice().install(Path('/not-used'),Path('/not-used'))
        self.assertEqual(caught.exception.code,'lab_install_disabled')
        log=self.root/'baseline.log'
        with patch('api_service.subprocess.run') as run:
            run.return_value.returncode=0
            Device().install(self.root/'bundle.swu',log)
            self.assertEqual(run.call_args.args[0],['/usr/sbin/edgemap-update','install',str(self.root/'bundle.swu')])
            self.assertTrue(run.call_args.kwargs['start_new_session'])


if __name__ == '__main__':
    unittest.main()
