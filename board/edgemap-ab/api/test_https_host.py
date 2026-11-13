#!/usr/bin/env python3
import io
import json
from pathlib import Path
import socket
import ssl
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from types import SimpleNamespace
from unittest.mock import Mock
from https_host import Handler, Server, initialize


def handshake(server_context, client_context, hostname):
    ci, co, si, so = (ssl.MemoryBIO() for _ in range(4))
    client = client_context.wrap_bio(ci, co, server_hostname=hostname)
    server = server_context.wrap_bio(si, so, server_side=True)
    done = [False, False]
    for _ in range(100):
        for i, connection in enumerate((client, server)):
            if not done[i]:
                try:
                    connection.do_handshake()
                    done[i] = True
                except ssl.SSLWantReadError:
                    pass
        for source, target in ((co, si), (so, ci)):
            data = source.read()
            if data:
                target.write(data)
        if all(done):
            return client.version()
    raise RuntimeError('TLS handshake did not complete')


def sockets_available():
    try:
        with socket.socket() as connection:
            connection.bind(('127.0.0.1', 0))
        return True
    except OSError:
        return False


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='https-host-test-')
        cls.root = Path(cls.temp.name) / 'host'
        initialize(cls.root, '192.0.2.10')
        cls.server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cls.server_context.minimum_version = ssl.TLSVersion.TLSv1_2
        cls.server_context.load_cert_chain(cls.root/'tls/server.pem', cls.root/'tls/server-key.pem')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_trusted_tls_and_correct_ip(self):
        context = ssl.create_default_context(cafile=self.root/'tls/ca.pem')
        self.assertIn(handshake(self.server_context, context, '192.0.2.10'), ('TLSv1.2','TLSv1.3'))
        self.assertEqual((self.root/'tls/ca-key.pem').stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.root/'tls/server-key.pem').stat().st_mode & 0o777, 0o600)

    def test_wrong_ip_and_untrusted_ca_are_rejected(self):
        for context, address in [(ssl.create_default_context(cafile=self.root/'tls/ca.pem'),'192.0.2.11'),
                                 (ssl.create_default_context(),'192.0.2.10')]:
            with self.assertRaises(ssl.SSLCertVerificationError):
                handshake(self.server_context,context,address)

    def test_private_files_listing_and_symlinks_are_not_served(self):
        alias = self.root/'www/secret.swu'
        alias.symlink_to(self.root/'tls/server-key.pem')
        try:
            for path in ('/','/tls/ca-key.pem','/ca.pem','/%2e%2e/tls/server-key.pem','/secret.swu','//health.json'):
                handler = Handler.__new__(Handler)
                handler.path = path
                handler.server = SimpleNamespace(www=self.root/'www')
                handler.send_error = Mock()
                handler.send_file(head=False)
                handler.send_error.assert_called_once_with(404)
            handler = Handler.__new__(Handler)
            handler.path = '/health.json'
            handler.server = SimpleNamespace(www=self.root/'www')
            handler.send_response = Mock()
            handler.send_header = Mock()
            handler.end_headers = Mock()
            handler.wfile = io.BytesIO()
            handler.send_file(head=False)
            handler.send_response.assert_called_once_with(200)
            self.assertTrue(json.loads(handler.wfile.getvalue())['https'])
        finally:
            alias.unlink()

    def test_initialization_does_not_overwrite_trust(self):
        certificate=(self.root/'tls/ca.pem').read_bytes()
        with self.assertRaises(ValueError):
            initialize(self.root,'192.0.2.10')
        self.assertEqual((self.root/'tls/ca.pem').read_bytes(),certificate)

    @unittest.skipUnless(sockets_available(), 'Sandbox denies sockets; run on PC for real HTTPS test')
    def test_actual_https_health_and_private_path_denial(self):
        class Quiet(Handler):
            def log_message(self,*args):
                pass
        with Server(('127.0.0.1',0),Quiet) as server:
            server.context=self.server_context
            server.www=self.root/'www'
            thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.01},daemon=True)
            thread.start()
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),
                urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=self.root/'tls/ca.pem')))
            try:
                url=f'https://127.0.0.1:{server.server_port}'
                with opener.open(url+'/health.json',timeout=5) as response:
                    self.assertTrue(json.load(response)['https'])
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    opener.open(url+'/tls/ca-key.pem',timeout=5)
                self.assertEqual(caught.exception.code,404)
            finally:
                server.shutdown()
                thread.join(2)


if __name__=='__main__':
    unittest.main()
