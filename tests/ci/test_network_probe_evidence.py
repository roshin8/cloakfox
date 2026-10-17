"""Failure evidence contracts without a browser or native build."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class NetworkProbeEvidenceTests(unittest.TestCase):
    def test_failed_probe_writes_partial_report_and_persistent_logs(self):
        evidence_module = module('evidence', ROOT / 'tests/network/probe_evidence.py')
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'REPORT_DIR': directory}):
                with self.assertRaisesRegex(AssertionError, 'strict failure'):
                    with evidence_module.ProbeEvidence('alps', 'ALPS_REPORT') as evidence:
                        evidence.report['handshakes'] = [{'alps': True}]
                        (evidence.root / 'driver.log').write_text('driver failure detail')
                        raise AssertionError('strict failure')
            report = json.loads((Path(directory) / 'alps.json').read_text())
            self.assertEqual(report['handshakes'], [{'alps': True}])
            self.assertEqual(report['outcome'], 'fail')
            self.assertIn('strict failure', report['error'])
            self.assertTrue((Path(directory) / 'driver.log').exists())

    def test_fixture_keeps_stdout_and_stderr(self):
        fixture_module = module('fixture', ROOT / 'tests/network/alps_fixture.py')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            server = root / 'fake-server'
            server.write_text('#!' + sys.executable + '\nimport sys,time\nprint("fixture diagnostic",file=sys.stderr,flush=True)\nprint(\'{"port":12345}\',flush=True)\nprint(\'{"alps":true}\',flush=True)\ntime.sleep(30)\n')
            server.chmod(0o755)
            with patch.dict(os.environ, {'REPORT_DIR': directory, 'ALPS_SERVER': str(server)}):
                fixture = fixture_module.ALPSFixture('certificate', 'key')
                fixture.close()
            self.assertIn('fixture diagnostic', ''.join(p.read_text() for p in root.glob('alps-fixture-*.stderr.log')))
            self.assertIn('"port":12345', ''.join(p.read_text() for p in root.glob('alps-fixture-*.stdout.jsonl')))

    def test_startup_failure_preserves_helper_stderr_and_failure_report(self):
        fixture_module = module('fixture', ROOT / 'tests/network/alps_fixture.py')
        evidence_module = module('evidence', ROOT / 'tests/network/probe_evidence.py')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            server = root / 'fake-server'
            server.write_text('#!' + sys.executable + '\nimport sys\nprint("fixture startup failed",file=sys.stderr,flush=True)\nsys.exit(1)\n')
            server.chmod(0o755)
            with patch.dict(os.environ, {'REPORT_DIR': directory, 'ALPS_SERVER': str(server)}):
                with self.assertRaisesRegex(RuntimeError, 'did not start'):
                    with evidence_module.ProbeEvidence('alps', 'ALPS_REPORT'):
                        fixture_module.ALPSFixture('certificate', 'key')
            self.assertEqual(json.loads((root / 'alps.json').read_text())['outcome'], 'fail')
            self.assertIn('fixture startup failed', ''.join(p.read_text() for p in root.glob('alps-fixture-*.stderr.log')))

    def test_all_three_probes_route_driver_and_reports_to_evidence(self):
        for name in ('alps_identity', 'ech_identity', 'signature_selection'):
            source = (ROOT / f'tests/fingerprint/probe_{name}.py').read_text()
            self.assertIn('ProbeEvidence(', source)
            self.assertIn("evidence.root/'driver.log'", source)
            self.assertNotIn("root/'driver.log'", source.replace("evidence.root/'driver.log'", ''))

if __name__ == '__main__': unittest.main()
