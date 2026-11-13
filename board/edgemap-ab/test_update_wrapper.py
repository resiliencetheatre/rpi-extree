import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import update_wrapper as wrapper


def status(version='dev-6', slot='b', trial=False, phase='committed'):
    previous = 'a' if slot == 'b' else 'b'
    return dict(device=dict(version=version, slot=slot, trial=trial,
                            state=dict(version=version, target=slot, previous=previous, phase=phase,
                                       profile=wrapper.PROFILE, layout=wrapper.LAYOUT)),
                device_error=None, job=dict(phase='available'), offer_error=None,
                offer=dict(version='dev-8', offer_id='signed-offer', sequence=8, notes='test',
                           bundle=dict(size=100, url='https://example.com/dev-8.swu')))


class WrapperTests(unittest.TestCase):
    def test_decline_does_not_download_install_or_arm_reboot(self):
        calls = []
        def rpc(method, params=None, **kwargs):
            calls.append(method)
            return status() if method == 'status' else dict(job_id='check')
        with patch.object(wrapper, 'rpc', side_effect=rpc), patch.object(wrapper, 'wait_job', return_value=status()), patch('builtins.input', return_value='n'), patch.object(wrapper, 'save_pending') as pending, patch.object(wrapper, 'say'):
            wrapper.update('remote')
        self.assertEqual(calls, ['status', 'select-source', 'check'])
        pending.assert_not_called()

    def test_accept_pins_offer_and_arms_only_after_download(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory)/'pending.json'
            calls = []
            def rpc(method, params=None, **kwargs):
                calls.append((method, params))
                if method == 'status': return status()
                if method == 'install':
                    self.assertTrue(marker.is_file())
                    self.assertEqual(json.loads(marker.read_text())['target'], 'a')
                return dict(job_id=method)
            def wait(job, operation):
                value = status()
                if operation == 'download': value['download_ready'] = True
                if operation == 'install': value['job']['phase'] = 'installed'
                return value
            with patch.object(wrapper, 'PENDING', marker), patch.object(wrapper, 'rpc', side_effect=rpc), patch.object(wrapper, 'wait_job', side_effect=wait), patch('builtins.input', return_value='y'), patch.object(wrapper, 'say'):
                wrapper.update('local')
            self.assertIn(('download', dict(offer_id='signed-offer', accept=True)), calls)
            self.assertIn(('install', dict(offer_id='signed-offer', accept=True)), calls)
            self.assertEqual(json.loads(marker.read_text())['previous'], 'b')

    def test_changed_offer_after_download_blocks_install(self):
        value = status(); value['download_ready'] = True
        changed = copy.deepcopy(value); changed['offer']['offer_id'] = 'changed'
        with patch.object(wrapper, 'rpc', return_value=dict(job_id='job')) as rpc, patch.object(wrapper, 'summary'), patch.object(wrapper, 'device', return_value=value['device']), patch.object(wrapper, 'wait_job', side_effect=[value, changed]), patch('builtins.input', return_value='y'), patch.object(wrapper, 'save_pending') as pending, patch.object(wrapper, 'say'):
            # Initial status needs a terminal job, separate from start-job responses.
            rpc.side_effect = [value, {}, {'job_id':'check'}, {'job_id':'download'}]
            with self.assertRaisesRegex(RuntimeError, 'not ready'):
                wrapper.update('remote')
            pending.assert_not_called()
            self.assertFalse(any(c.args[0] == 'install' for c in rpc.call_args_list))

    def test_final_reboot_requires_exact_committed_trial_and_idle_job(self):
        cases = [('good', status('dev-8', 'a', True), True),
                 ('wrong-version', status('dev-7', 'a', True), False),
                 ('wrong-slot', status('dev-8', 'b', True), False),
                 ('unconfirmed', status('dev-8', 'a', True, 'trial'), False),
                 ('fallback', status('dev-6', 'b', False, 'fallback'), False),
                 ('normal-complete', status('dev-8', 'a', False), False)]
        busy = status('dev-8', 'a', True); busy['job']['phase'] = 'installing'
        cases.append(('busy', busy, False))
        for name, value, reboot in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                marker = Path(directory)/'pending'
                marker.write_text(json.dumps(dict(version='dev-8', target='a', previous='b', profile=wrapper.PROFILE, layout=wrapper.LAYOUT)))
                with patch.object(wrapper, 'PENDING', marker), patch.object(wrapper, 'rpc', return_value=value) as rpc, patch.object(wrapper, 'say'):
                    try: wrapper.finish_pending()
                    except RuntimeError:
                        self.assertFalse(reboot)
                    finishes = [c for c in rpc.call_args_list if c.args[0] == 'finish']
                    self.assertEqual(bool(finishes), reboot)
                    if reboot:
                        self.assertEqual(finishes[0].args[1], dict(accept=True))
                        self.assertFalse(marker.exists())

    def test_monitor_rejects_competing_job_and_reports_errors(self):
        value = status(); value['job'] = dict(job_id='other', operation='download', phase='downloading')
        with patch.object(wrapper, 'rpc', return_value=value):
            with self.assertRaisesRegex(RuntimeError, 'job changed'):
                wrapper.wait_job('expected', 'download')
        value['job'].update(job_id='expected', phase='failed', error=dict(code='hash_mismatch'))
        with patch.object(wrapper, 'rpc', return_value=value), patch.object(wrapper, 'say'):
            with self.assertRaisesRegex(RuntimeError, 'hash_mismatch'):
                wrapper.wait_job('expected', 'download')
