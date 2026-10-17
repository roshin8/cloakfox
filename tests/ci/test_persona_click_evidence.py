"""Failure evidence survives a real UI click error; no browser is launched."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class ClickEvidenceTests(unittest.TestCase):
    def test_records_failed_click_without_swallowing_or_repeating_it(self):
        spec = importlib.util.spec_from_file_location('click_evidence', ROOT / 'tests/fingerprint/click_evidence.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        error = RuntimeError('could not be scrolled into view')
        class Element:
            calls = 0
            def click(self):
                self.calls += 1
                raise error
        class Driver:
            def execute_script(self, script, element):
                return {'rect': {'height': 0}, 'ancestors': [{'hidden': True}]}
            def save_screenshot(self, path):
                Path(path).write_bytes(b'screenshot')
        element = Element()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError) as caught:
                module.click_with_evidence(Driver(), element, Path(directory), 'generate-2')
            self.assertIs(caught.exception, error)
            self.assertEqual(element.calls, 1)
            self.assertIn('ancestors', (Path(directory) / 'generate-2.json').read_text())
            self.assertTrue((Path(directory) / 'generate-2.png').exists())

    def test_evidence_error_does_not_replace_original_click_failure(self):
        spec = importlib.util.spec_from_file_location('click_evidence', ROOT / 'tests/fingerprint/click_evidence.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        class Element:
            def click(self): raise ValueError('original click')
        class Driver:
            def execute_script(self, *args): raise RuntimeError('driver unavailable')
            def save_screenshot(self, *args): raise RuntimeError('driver unavailable')
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'original click'):
                module.click_with_evidence(Driver(), Element(), Path(directory), 'generate-1')
            self.assertIn('driver unavailable', (Path(directory) / 'generate-1.json').read_text())

if __name__ == '__main__': unittest.main()
