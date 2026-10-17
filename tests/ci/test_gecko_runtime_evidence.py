"""Hosted GPU provisioning/evidence contracts; never launches a browser."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

class RuntimeEvidenceTests(unittest.TestCase):
    def test_each_probe_gets_distinct_persistent_report_directory(self):
        spec = importlib.util.spec_from_file_location('probe_runner', ROOT / 'tests/fingerprint/run_all.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            first = module.probe_environment(Path('probe_first.py'), {'PROBE_REPORT_ROOT': directory, 'KEEP': 'yes'})
            second = module.probe_environment(Path('probe_second.py'), {'PROBE_REPORT_ROOT': directory})
            self.assertNotEqual(first['REPORT_DIR'], second['REPORT_DIR'])
            self.assertTrue(Path(first['REPORT_DIR']).is_dir())
            self.assertEqual(first['KEEP'], 'yes')
        self.assertEqual(module.probe_environment(Path('probe_first.py'), {'REPORT_DIR': 'existing'}), {'REPORT_DIR': 'existing'})

    def test_failed_probe_preserves_raw_log_and_output(self):
        spec = importlib.util.spec_from_file_location('probe_runner', ROOT / 'tests/fingerprint/run_all.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            probe = root / 'probe_fixture.py'
            probe.write_text("import os, pathlib; pathlib.Path(os.environ['REPORT_DIR'], 'gecko.log').write_text('raw CGL error'); print('failed context'); raise SystemExit(1)")
            with patch.dict(module.os.environ, {'PROBE_REPORT_ROOT': str(root / 'reports')}):
                code, output = module.run_probe(probe, 10)
            self.assertEqual(code, 1)
            evidence = root / 'reports' / 'probe_fixture'
            self.assertEqual((evidence / 'gecko.log').read_text(), 'raw CGL error')
            self.assertEqual((evidence / 'probe-output.txt').read_text(), output)
            self.assertIn('failed context', output)

    def test_hosted_headful_and_always_uploaded_raw_evidence(self):
        workflow = (ROOT / '.github/workflows/build-macos.yml').read_text()
        self.assertIn("CLOAKFOX_HEADFUL: '1'", workflow)
        self.assertIn('PROBE_REPORT_ROOT: ${{ runner.temp }}/gecko-probe-evidence', workflow)
        upload = workflow.split('name: Preserve required library and strict probe evidence', 1)[1].split('name: Fail if', 1)[0]
        self.assertIn('if: always()', upload)
        self.assertIn('${{ runner.temp }}/gecko-probe-evidence/', upload)
        self.assertIn('${{ runner.temp }}/native-cgl-diagnostic/', upload)

if __name__ == '__main__':
    unittest.main()
