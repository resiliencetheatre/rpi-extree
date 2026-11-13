"""Wrapper orchestration with stub tools; no real builds or network calls."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BOARD = Path(__file__).resolve().parent.parent
WORKSPACE = BOARD.parents[2]


class ReleaseCLITests(unittest.TestCase):
    def test_both_destinations_build_once_and_publish_only_skips_make(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root/'output'
            (output/'images').mkdir(parents=True)
            (output/'target/etc/edgemap-ab').mkdir(parents=True)
            for name in ('boot-a.vfat', 'boot-b.vfat', 'rootfs.ext4'):
                (output/'images'/name).write_bytes(b'fixture')
            (output/'target/etc/edgemap-ab/public.pem').write_text('fixture')
            (output/'.config').write_text('BR2_PACKAGE_SITUATION_MAP=y\nBR2_ROOTFS_POST_BUILD_SCRIPT="edgemap-ab/post-build.sh"\n')
            host = root/'host'; (host/'www').mkdir(parents=True); (host/'tls').mkdir()
            (host/'tls/ca.pem').write_text('fixture')
            for name in ('private.pem', 'public.pem'): (root/name).write_text('fixture')
            binary = root/'bin'; binary.mkdir()
            tool = r'''#!/bin/bash
set -eu
name=$(basename "$0")
printf '%s %s\n' "$name" "$*" >> "$TEST_RELEASE_LOG"
if [[ $name == openssl || $name == python3 ]]; then
    target=''
    previous=''
    for argument in "$@"; do
        case "$previous" in -out|--output|--snapshot) target=$argument;; esac
        previous=$argument
    done
    if [[ -n $target ]]; then printf fixture > "$target"; fi
fi
'''
            for name in ('make', 'openssl', 'python3', 'rclone'):
                script = binary/name; script.write_text(tool); script.chmod(0o755)
            log = root/'calls'
            env = dict(os.environ, PATH=str(binary)+':'+os.environ['PATH'], TEST_RELEASE_LOG=str(log),
                       RELEASE_WORKSPACE=str(WORKSPACE), RELEASE_OUTPUT=str(output), RELEASE_DIR=str(root/'releases'),
                       AB_SIGN_KEY=str(root/'private.pem'), AB_VERIFY_KEY=str(root/'public.pem'),
                       RELEASE_HOST=str(host), RELEASE_LOCAL_URL='https://192.0.2.1:9443', RELEASE_REMOTE='web:root')
            subprocess.run(['bash', str(BOARD/'release.sh'), '--public', '--local', 'dev-999'], env=env, check=True, stdout=subprocess.DEVNULL)
            calls = log.read_text().splitlines()
            makes = [line for line in calls if line.startswith('make ')]
            self.assertEqual(len(makes), 2)  # one dirclean and one full image build
            uploads = [line for line in calls if 'public_release.py upload ' in line]
            self.assertEqual(len(uploads), 2)
            self.assertTrue(any('--local-host ' in line for line in uploads))
            self.assertTrue(any('--remote ' in line for line in uploads))
            log.write_text('')
            # Different already-built version for the publish-only branch.
            release = root/'releases/dev-998'; release.mkdir()
            (release/'dev-998.swu').write_bytes(b'fixture')
            (release/'SHA256SUMS').write_text('fixture')
            subprocess.run(['bash', str(BOARD/'release.sh'), '--local', '--publish-only', 'dev-998'], env=env, check=True, stdout=subprocess.DEVNULL)
            self.assertFalse(any(line.startswith('make ') for line in log.read_text().splitlines()))
