"""Environment helper checks: source only; no make, signing or publication."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().with_name('set-build-variables.sh')
WORKSPACE = SCRIPT.parents[3]


class BuildVariableTests(unittest.TestCase):
    def run_shell(self, command, *args, overrides=None):
        environment = dict(PATH=os.environ['PATH'])
        environment.update(overrides or {})
        return subprocess.run(['bash', '--noprofile', '--norc', '-c', command, 'test', str(SCRIPT), *args],
                              cwd='/tmp', env=environment, text=True, capture_output=True)

    def test_sourced_exports_and_relative_path_resolution(self):
        result = self.run_shell('source "$1" "$2" "$3" >/dev/null || exit; printf "%s\\n" "$WORKSPACE" "$AB_OUTPUT" "$RELEASE_OUTPUT" "$RELEASE_LOCAL_URL" "$AB_PROFILE" "$RELEASE_JOBS"',
                                '192.168.178.41', 'output-env-example')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(WORKSPACE), str(WORKSPACE/'output-env-example'),
                         str(WORKSPACE/'output-env-example'), 'https://192.168.178.41:9443',
                         str(WORKSPACE/'rpi-extree/configs/raspberrypi4_edgemap_lite_ab_defconfig'), '32'])
        self.assertFalse((WORKSPACE/'output-env-example').exists())

    def test_absolute_output_spaces_and_custom_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'output with spaces'
            result = self.run_shell('source "$1" "$2" "$3" >/dev/null || exit; printf "%s\\n" "$AB_OUTPUT" "$RELEASE_LOCAL_URL" "$RELEASE_JOBS" "$AB_SIGN_KEY"',
                                    '10.0.0.2', str(output), overrides=dict(RELEASE_LOCAL_PORT='9444', RELEASE_JOBS='12', AB_SIGN_KEY='/tmp/external-sign.pem'))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), [str(output), 'https://10.0.0.2:9444', '12', '/tmp/external-sign.pem'])
            self.assertFalse(output.exists())

    def test_invalid_arguments_do_not_change_existing_variables(self):
        for address, output, overrides in [('999.1.1.1', 'out', {}), ('192.168.01.1','out',{}),
                                          ('127.0.0.1', '/', {}), ('127.0.0.1','rpi-extree',{}),
                                          ('127.0.0.1','out',dict(AB_SIGN_KEY='relative.pem')),
                                          ('127.0.0.1','out',dict(RELEASE_JOBS='0'))]:
            with self.subTest(address=address, output=output, overrides=overrides):
                result = self.run_shell('export WORKSPACE=unchanged; source "$1" "$2" "$3" >/dev/null; result=$?; printf "%s\\n" "$WORKSPACE"; exit "$result"', address, output, overrides=overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout.strip(), 'unchanged')

    def test_help_and_execution_explain_sourcing(self):
        result = self.run_shell('source "$1" --help; test -z "${WORKSPACE+x}"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('source ./set-build-variables.sh', result.stdout)
        result = subprocess.run(['bash', str(SCRIPT), '192.168.178.41', 'out'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Source this script', result.stdout)
