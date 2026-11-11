import unittest
from unittest.mock import MagicMock, patch
import health


class HealthTests(unittest.TestCase):
    def test_local_services_and_application_required(self):
        with patch.object(health.subprocess, 'run') as run, patch.object(health.urllib.request, 'build_opener') as opener:
            run.return_value.returncode = 1
            self.assertFalse(health.ready())
            opener.assert_not_called()
            run.return_value.returncode = 0
            with patch.object(health.Path, 'is_file', return_value=False):
                self.assertFalse(health.ready())
            opener.assert_not_called()

    def test_exact_readiness_response_and_network_failure(self):
        with patch.object(health.subprocess, 'run') as run, patch.object(health.Path, 'is_file', return_value=True), patch.object(health.Path, 'is_fifo', return_value=True), patch.object(health.urllib.request, 'build_opener') as opener:
            run.return_value.returncode = 0
            response = opener.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b'{"status":"ok","service":"Situation"}' 
            self.assertTrue(health.ready())
            response.read.return_value = b'{"status":"ok","service":"other"}' 
            self.assertFalse(health.ready())
            opener.return_value.open.side_effect = OSError('unavailable')
            self.assertFalse(health.ready())
