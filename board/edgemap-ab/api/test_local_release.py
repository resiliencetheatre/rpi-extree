import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import public_release as public
from local_release import LocalBackend


class LocalPublicationTests(unittest.TestCase):
    def host(self, root):
        host = root/'host'
        (host/'www').mkdir(parents=True)
        (host/'host.json').write_text('{}')
        return host

    def test_same_engine_local_publication_and_failed_verification(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                host = self.host(root)
                backend = LocalBackend(host)
                release = root/'release'; release.mkdir()
                payload = b'signed fixture'
                (release/'dev-9.swu').write_bytes(payload)
                (release/'SHA256SUMS').write_text('checksum')
                signed = dict(version='dev-9', sequence=9, bundle=dict(url='https://example.com/dev-9.swu', size=len(payload), sha256=hashlib.sha256(payload).hexdigest()))
                (release/'latest.json').write_text(json.dumps(dict(signed=signed)))
                snapshot = root/'previous'; snapshot.write_bytes(b'')
                class Fetcher:
                    def __init__(self, url): pass
                    def open(self, url):
                        name = url.rsplit('/', 1)[-1]
                        data = (host/'www'/name).read_bytes()
                        return io.BytesIO(b'corrupt' if corrupt and name.endswith('.swu') else data)
                with patch.object(public, 'verify_offer', return_value=('id', signed)):
                    self.assertEqual(public.inspect('local:root', 'https://example.com', 'dev-9', 9, root/'key', backend=backend, fetcher=Fetcher), b'')
                    if corrupt:
                        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                            public.upload('local:root', 'https://example.com', 'dev-9', 9, root/'key', snapshot, release, backend=backend, fetcher=Fetcher)
                        self.assertFalse((host/'www/latest.json').exists())
                    else:
                        public.upload('local:root', 'https://example.com', 'dev-9', 9, root/'key', snapshot, release, backend=backend, fetcher=Fetcher)
                        self.assertEqual((host/'www/latest.json').read_bytes(), (release/'latest.json').read_bytes())
                        with self.assertRaisesRegex(ValueError, 'already exists'):
                            public.inspect('local:root', 'https://example.com', 'dev-9', 9, root/'key', backend=backend, fetcher=Fetcher)
                    self.assertEqual((host/'www/dev-9.swu').read_bytes(), payload)

    def test_immutable_copy_and_path_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backend = LocalBackend(self.host(root))
            source = root/'source'; source.write_bytes(b'first')
            backend('copyto', source, 'local:root/dev-1.swu', '--immutable')
            source.write_bytes(b'changed')
            with self.assertRaises(FileExistsError):
                backend('copyto', source, 'local:root/dev-1.swu', '--immutable')
            self.assertEqual((backend.root/'dev-1.swu').read_bytes(), b'first')
            for name in ('local:root/../escape', 'local:root/', 'other:file'):
                with self.assertRaises(ValueError): backend.path(name)
            (backend.root/'link').symlink_to(source)
            with self.assertRaises(ValueError): backend.path('local:root/link')
            with self.assertRaises(ValueError): backend('moveto', 'local:root/dev-1.swu', 'local:root/latest.json')
            self.assertFalse(list(backend.root.glob('.copy-*')))
