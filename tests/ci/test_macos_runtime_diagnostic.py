"""The focused diagnostic uses a verified existing producer, never builds engines."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]
class MacDiagnosticTests(unittest.TestCase):
    def test_diagnostic_is_mac_only_bounded_and_preserves_failures(self):
        workflow=(ROOT/'.github/workflows/runner-survey.yml').read_text()
        self.assertIn('diagnostic_only:', workflow)
        job=workflow.split('  runtime-diagnostic:',1)[1]
        self.assertIn('runs-on: macos-26',job)
        self.assertIn('timeout-minutes: 20',job)
        self.assertIn('39004787714',job)
        self.assertIn('73b9b4ea95465c374750c4a8ee3798546f1cb738',job)
        self.assertIn('codesign --verify --deep --strict',job)
        self.assertIn('if: always()',job)
        self.assertNotIn('webgl.forbid-software',job)
        self.assertNotIn('make build',job)
if __name__=='__main__': unittest.main()
