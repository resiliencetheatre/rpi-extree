#!/usr/bin/env python3
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import public_release as public


class PublicationTests(unittest.TestCase):
    def test_verified_payload_before_metadata_and_failure_preserves_offer(self):
        for bad in (False, True):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                payload = b'signed bundle fixture'
                (root/'dev-9.swu').write_bytes(payload)
                (root/'SHA256SUMS').write_text('fixture')
                signed = dict(version='dev-9', sequence=9, bundle=dict(
                    url='https://example.com/edgemap/dev-9.swu', size=len(payload),
                    sha256=hashlib.sha256(payload).hexdigest()))
                (root/'latest.json').write_text(json.dumps(dict(signed=signed)))
                snapshot = root/'previous'; snapshot.write_bytes(b'old offer')
                calls=[]
                def remote(*args):
                    calls.append(args)
                    return b'old offer' if args[0]=='cat' else b''
                def opened(url):
                    calls.append(('https',url))
                    if url.endswith('.swu'):
                        return io.BytesIO(b'corrupt' if bad else payload)
                    return io.BytesIO((root/'latest.json').read_bytes())
                with patch.object(public,'inspect',return_value=b'old offer'), \
                     patch.object(public,'verify_offer',return_value=('id',signed)), \
                     patch.object(public,'rclone',side_effect=remote), \
                     patch.object(public.Fetcher,'open',side_effect=opened):
                    if bad:
                        with self.assertRaisesRegex(ValueError,'hash mismatch'):
                            public.upload('web:root','https://example.com/edgemap','dev-9',9,root/'key',snapshot,root)
                        self.assertFalse(any(c[0]=='moveto' for c in calls))
                    else:
                        public.upload('web:root','https://example.com/edgemap','dev-9',9,root/'key',snapshot,root)
                        actions=[c[0] for c in calls]
                        self.assertLess(actions.index('https'), actions.index('moveto'))
                        self.assertEqual(actions.count('moveto'),1)
                        uploads=[c for c in calls if c[0]=='copyto']
                        self.assertEqual([Path(c[1]).name for c in uploads],['dev-9.swu','SHA256SUMS','latest.json'])

    def test_changed_offer_blocks_all_uploads(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot=Path(directory)/'snapshot'; snapshot.write_bytes(b'old')
            with patch.object(public,'inspect',return_value=b'new'), patch.object(public,'rclone') as remote:
                with self.assertRaisesRegex(ValueError,'changed during build'):
                    public.upload('web:root','https://example.com','dev-9',9,Path('key'),snapshot,Path(directory))
                remote.assert_not_called()

    def test_existing_bundle_and_unavailable_remote_fail_closed(self):
        for listing in (json.dumps([dict(Name='dev-9.swu')]).encode(), None):
            with patch.object(public,'rclone',side_effect=[b'{"Features":{"Move":true}}',
                    listing if listing else RuntimeError('remote unavailable')]):
                with self.assertRaises((ValueError,RuntimeError)):
                    public.inspect('web:root','https://example.com','dev-9',9,Path('key'))


if __name__ == '__main__':
    unittest.main()
