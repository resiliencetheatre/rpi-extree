"""Controller completion guards; no reboots or target filesystem access."""
import copy
import unittest
from pathlib import Path
from unittest.mock import patch
import control


class FinishTests(unittest.TestCase):
    def test_only_exact_committed_trial_can_reboot(self):
        expected = dict(profile=control.PROFILE, layout=control.LAYOUT,
                        version='dev-20', previous='a', target='b')
        state = dict(expected, phase='committed')
        cases = [('valid', 'b', True, state, expected, True),
                 ('normal', 'b', False, state, expected, False),
                 ('wrong-slot', 'a', True, state, expected, False)]
        for key, value in [('version', 'dev-19'), ('profile', 'other'),
                           ('layout', 2), ('phase', 'trial'), ('previous', 'b')]:
            changed = dict(state, **{key: value})
            cases.append((key, 'b', True, changed, expected, False))
        for name, slot, trial, saved, accepted, allowed in cases:
            with self.subTest(name=name), patch.object(Path, 'read_text', return_value='dev-20'), patch.object(control, 'run') as run:
                if allowed:
                    control.finish(slot, trial, saved, accepted)
                    run.assert_called_once_with('systemctl', '--no-block', 'reboot')
                else:
                    with self.assertRaises(AssertionError):
                        control.finish(slot, trial, saved, accepted)
                    run.assert_not_called()

    def test_manual_finish_requires_committed_matching_profile(self):
        state = dict(profile=control.PROFILE, layout=control.LAYOUT,
                     version='dev-20', target='b', phase='committed')
        with patch.object(Path, 'read_text', return_value='dev-20'), patch.object(control, 'run') as run:
            control.finish('b', True, state)
            run.assert_called_once()
