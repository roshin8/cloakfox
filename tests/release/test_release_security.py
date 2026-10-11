import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location('security', Path(__file__).resolve().parents[2] / 'scripts/release_security.py')
security = importlib.util.module_from_spec(spec)
spec.loader.exec_module(security)
class SecurityTests(unittest.TestCase):
    def test_current(self):
        self.assertTrue(security.assess('155.0.1', {'155.0.1':'2026-09-01'}, '2026-09-08')['ready'])
    def test_new_patch_blocks(self):
        self.assertFalse(security.assess('155.0.1', {'155.0.1':'2026-09-01','155.0.2':'2026-09-08'}, '2026-09-08')['ready'])
    def test_stale_blocks(self):
        self.assertFalse(security.assess('155.0.1', {'155.0.1':'2026-07-01'}, '2026-09-08')['ready'])
    def test_unknown_blocks(self):
        self.assertFalse(security.assess('155.0.1', {'154.0':'2026-08-01'}, '2026-09-08')['ready'])
    def test_future_blocks(self):
        self.assertFalse(security.assess('155.0.1', {'155.0.1':'2026-09-09'}, '2026-09-08')['ready'])


class OfflineReceiptTests(unittest.TestCase):
    def test_offline_success_never_authorizes_release(self):
        import datetime
        import json
        import subprocess
        import sys
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / 'feed.json'
            receipt = Path(directory) / 'receipt.json'
            fixture.write_text(json.dumps({'releases': {'firefox-155.0.1': {
                'version': '155.0.1', 'date': datetime.date.today().isoformat(), 'category': 'stability'}}}))
            result = subprocess.run([sys.executable, str(Path(security.__file__)), '--version', '155.0.1',
                                     '--fixture', str(fixture), '--output', str(receipt)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(receipt.read_text())
            self.assertTrue(data['assessed_ready'])
            self.assertTrue(data['testOnly'])
            self.assertTrue(data['offline_fixture'])
            self.assertFalse(data['ready'])
            self.assertTrue(any('cannot authorize' in action for action in data['actions']))

    def test_offline_failed_assessment_keeps_failure_exit_and_receipt(self):
        import datetime
        import json
        import subprocess
        import sys
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / 'feed.json'
            fixture.write_text(json.dumps({'releases': {'firefox-154.0': {
                'version': '154.0', 'date': datetime.date.today().isoformat(), 'category': 'major'}}}))
            result = subprocess.run([sys.executable, str(Path(security.__file__)), '--version', '155.0.1',
                                     '--fixture', str(fixture)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            data = json.loads(result.stdout)
            self.assertFalse(data['assessed_ready'])
            self.assertTrue(data['testOnly'])
            self.assertFalse(data['ready'])


    def test_unreadable_fixture_is_still_marked_test_only(self):
        import json
        from unittest.mock import patch
        with patch('sys.argv', ['release_security.py', '--version', '155.0.1', '--fixture', '/not-a-real-cloakfox-fixture']), \
             patch('builtins.print') as output:
            self.assertEqual(security.main(), 1)
        data = json.loads(output.call_args.args[0])
        self.assertTrue(data['testOnly'])
        self.assertFalse(data['assessed_ready'])
        self.assertFalse(data['ready'])
