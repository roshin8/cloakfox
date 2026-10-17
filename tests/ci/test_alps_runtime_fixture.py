"""Provisioning contract tests; no compiler or browser is invoked."""
import importlib.util
import subprocess
import sys
import time
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('alps_runtime_fixture', ROOT / 'scripts/ci/alps_runtime_fixture.py')


class AlpsRuntimeFixtureTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(self.module)

    def test_build_verifies_pin_before_configuring_and_records_current_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            calls = []
            def run(argv, **kwargs):
                calls.append(argv)
                if argv[:2] == ['git', 'rev-parse']:
                    return self.module.BORINGSSL_COMMIT
                if argv[0] == 'c++':
                    (work / 'alps-server').write_bytes(b'fixture executable')
                return ''
            with patch.object(self.module, 'run', side_effect=run):
                self.module.build(work, 'current-commit')
            self.assertLess(next(i for i,c in enumerate(calls) if c[:2] == ['git','rev-parse']), next(i for i,c in enumerate(calls) if c[0] == 'cmake'))
            self.assertTrue(any(self.module.BORINGSSL_COMMIT in c for c in calls))
            self.module.verify(work, 'current-commit')
            with self.assertRaisesRegex(ValueError, 'commit'):
                self.module.verify(work, 'different-commit')
            (work / 'alps-server').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'hash'):
                self.module.verify(work, 'current-commit')

    def test_wrong_upstream_checkout_stops_before_compiler(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(self.module, 'run', return_value='wrong') as run:
                with self.assertRaisesRegex(ValueError, 'BoringSSL'):
                    self.module.build(Path(directory), 'commit')
            self.assertFalse(any(c.args[0][0] in ('cmake', 'c++') for c in run.call_args_list))

    def test_verification_rejects_changed_fixture_and_upstream_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            fixture = work / 'fixture.cc'
            fixture.write_text('original fixture')
            def run(argv, **kwargs):
                if argv[:2] == ['git', 'rev-parse']:
                    return self.module.BORINGSSL_COMMIT
                if argv[0] == 'c++':
                    (work / 'alps-server').write_bytes(b'executable')
                return ''
            with patch.object(self.module, 'FIXTURE', fixture), patch.object(self.module, 'run', side_effect=run):
                self.module.build(work, 'commit')
                fixture.write_text('changed fixture')
                with self.assertRaisesRegex(ValueError, 'hash'):
                    self.module.verify(work, 'commit')
                fixture.write_text('original fixture')
                with patch.object(self.module, 'BORINGSSL_COMMIT', 'different-pin'):
                    with self.assertRaisesRegex(ValueError, 'commit'):
                        self.module.verify(work, 'commit')

    def test_command_timeout_terminates_owned_descendants(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'child-terminated'
            child = "import signal,time,sys; signal.signal(signal.SIGTERM,lambda *_: (open(sys.argv[1],'w').write('terminated'),sys.exit(0))); print('ready',flush=True); time.sleep(30)"
            parent = "import signal,subprocess,sys,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); p=subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]],stdout=subprocess.PIPE); p.stdout.readline(); time.sleep(30)"
            started = time.monotonic()
            with self.assertRaises(subprocess.TimeoutExpired):
                self.module.run([sys.executable, '-c', parent, child, str(marker)], timeout=1, terminate_grace=0.2)
            self.assertLess(time.monotonic() - started, 5)
            self.assertEqual(marker.read_text(), 'terminated')

    def test_workflow_requires_verified_fixture_before_probes(self):
        workflow = (ROOT / '.github/workflows/build-macos.yml').read_text()
        self.assertIn('alps_runtime_fixture.py build', workflow)
        self.assertIn('alps_runtime_fixture.py verify', workflow)
        self.assertIn('ALPS_SERVER=', workflow)
        self.assertIn('Build and verify pinned same-run ALPS TLS fixture\n        timeout-minutes: 20', workflow)
        self.assertLess(workflow.index('alps_runtime_fixture.py verify'), workflow.index('name: Run fingerprint probe suite'))

if __name__ == '__main__':
    unittest.main()
