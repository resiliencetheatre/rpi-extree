#!/usr/bin/env python3
"""Read-only regression checks; never opens a physical block device."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('migrate', Path(__file__).with_name('migrate-pi5-card.py'))
migrate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migrate)


class MigrationChecks(unittest.TestCase):
    def setUp(self):
        self.image = {'label': 'dos', 'unit': 'sectors', 'sectorsize': 512, 'partitions': [
            {'start': 1, 'size': 262144, 'type': 'c', 'bootable': True},
            {'start': 262145, 'size': 1048576, 'type': '83'}]}
        self.card = copy.deepcopy(self.image)
        self.card['partitions'].append({'start': 1312768, 'size': 900000000, 'type': '83'})

    def test_matching_layout(self):
        migrate.check_geometry(self.card, self.image)

    def test_reject_changed_geometry(self):
        for partition in (0, 1):
            for key, value in [('start', 2048), ('size', 42), ('type', '7'), ('bootable', False)]:
                with self.subTest(partition=partition, key=key):
                    card = copy.deepcopy(self.card)
                    card['partitions'][partition][key] = value
                    with self.assertRaises(ValueError):
                        migrate.check_geometry(card, self.image)

    def test_reject_overlap_and_missing_mirror(self):
        self.card['partitions'][2]['start'] = 1000000
        with self.assertRaises(ValueError):
            migrate.check_geometry(self.card, self.image)
        self.card['partitions'].pop()
        with self.assertRaises(ValueError):
            migrate.check_geometry(self.card, self.image)

    def test_reject_nonstandard_sizes_even_when_matching(self):
        self.card['partitions'][1]['size'] = 100
        self.image['partitions'][1]['size'] = 100
        with self.assertRaises(ValueError):
            migrate.check_geometry(self.card, self.image)

    def test_reject_gpt_and_sector_size(self):
        for key, value in [('label', 'gpt'), ('sectorsize', 4096), ('unit', 'bytes')]:
            with self.subTest(key=key):
                card = copy.deepcopy(self.card)
                card[key] = value
                with self.assertRaises(ValueError):
                    migrate.check_geometry(card, self.image)

    def test_digest_exact_range_and_short_read(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'test.img'
            p.write_bytes(b'boot data' + b'mirror data')
            self.assertEqual(migrate.digest_bytes(p, 9), hashlib.sha256(b'boot data').hexdigest())
            with self.assertRaises(ValueError):
                migrate.digest_bytes(p, 100)


if __name__ == '__main__':
    unittest.main()
