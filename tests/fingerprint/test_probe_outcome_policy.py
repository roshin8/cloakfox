import importlib.util
from pathlib import Path
import datetime
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('probe_policy', HERE / 'run_all.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class ProbeOutcomePolicy(unittest.TestCase):
    def test_inconclusive_is_failure_unless_exact_unexpired_allowance(self):
        today = datetime.date(2026, 10, 15)
        entry = {'probe': 'probe_example.py', 'platform': 'linux',
                 'reason': 'Tracked hardware limitation: fixture issue 123', 'expires': '2026-10-20'}
        self.assertFalse(runner.accept_outcome('probe_example.py', 2, [], 'linux', today))
        self.assertTrue(runner.accept_outcome('probe_example.py', 2, [entry], 'linux', today))
        self.assertFalse(runner.accept_outcome('probe_other.py', 2, [entry], 'linux', today))
        self.assertFalse(runner.accept_outcome('probe_example.py', 2, [entry], 'darwin', today))
        self.assertFalse(runner.accept_outcome('probe_example.py', 2, [entry], 'linux', datetime.date(2026, 10, 21)))
        self.assertFalse(runner.accept_outcome('probe_example.py', 1, [entry], 'linux', today))
        self.assertTrue(runner.accept_outcome('probe_example.py', 0, [], 'linux', today))

    def test_blanket_or_unexplained_allowances_are_rejected(self):
        for entry in [
            {'probe': '*', 'platform': 'linux', 'reason': 'known', 'expires': '2026-10-20'},
            {'probe': 'probe_example.py', 'platform': '*', 'reason': 'known', 'expires': '2026-10-20'},
            {'probe': 'probe_example.py', 'platform': 'linux', 'reason': '', 'expires': '2026-10-20'},
            {'probe': 'probe_example.py', 'platform': 'linux', 'reason': 'known'},
        ]:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                runner.validate_allowances([entry])

    def test_cli_records_and_rejects_inconclusive_then_accepts_exact_allowance(self):
        import contextlib
        import io
        import json
        import os
        import sys
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'probe_example.py').write_text('print("INCONCLUSIVE missing test device"); raise SystemExit(2)')
            policy = root / 'inconclusive-allowances.json'
            policy.write_text(json.dumps({'schemaVersion': 1, 'allowances': []}))
            report = root / 'report.json'
            args = ['runner', '--retries', '0', '--report', str(report)]
            with patch.object(runner, 'HERE', root), patch.object(sys, 'argv', args), patch.dict(os.environ, {'CLOAKFOX_BIN': sys.executable}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(), 1)
                self.assertFalse(json.loads(report.read_text())['results'][0]['accepted'])
                policy.write_text(json.dumps({'schemaVersion': 1, 'allowances': [{
                    'probe': 'probe_example.py', 'platform': sys.platform,
                    'reason': 'Owned fixture explicitly permits absent test device',
                    'expires': (datetime.date.today() + datetime.timedelta(days=1)).isoformat()}]}))
                self.assertEqual(runner.main(), 0)
                result = json.loads(report.read_text())['results'][0]
                self.assertTrue(result['accepted'])
                self.assertEqual(result['exitCode'], 2)
                self.assertTrue(result['allowance']['reason'])

    def test_probe_attempt_cleans_descendants_on_success_and_timeout(self):
        import os
        import signal
        import subprocess
        import sys
        import tempfile
        import time
        for finish in (True, False):
            with self.subTest(finish=finish), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                pidfile = root / 'descendant.pid'
                descendant = 'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)'
                probe = root / 'probe_child.py'
                probe.write_text('import subprocess,sys,time\nfrom pathlib import Path\n'
                    f'child=subprocess.Popen([sys.executable,"-c",{descendant!r}])\n'
                    f'Path({str(pidfile)!r}).write_text(str(child.pid))\n'
                    'print("partial probe output",flush=True)\n' +
                    ('raise SystemExit(0)\n' if finish else 'time.sleep(30)\n'))
                try:
                    code, output = runner.run_probe(probe, timeout=.3)
                    self.assertEqual(code, 0 if finish else 3)
                    self.assertIn('partial probe output', output)
                    pid = int(pidfile.read_text())
                    # A killed orphan can briefly remain a zombie until reaped.
                    deadline = time.monotonic() + 2
                    while True:
                        state = subprocess.run(['ps','-p',str(pid),'-o','stat='], capture_output=True, text=True).stdout.strip()
                        if not state or state.startswith('Z') or time.monotonic() >= deadline:
                            break
                        time.sleep(.01)
                    self.assertTrue(not state or state.startswith('Z'), state)
                finally:
                    if pidfile.exists():
                        try: os.kill(int(pidfile.read_text()), signal.SIGKILL)
                        except ProcessLookupError: pass

    def test_probe_attempt_preserves_failure_code_and_stderr(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            probe = Path(folder) / 'probe_failed.py'
            probe.write_text('import sys;print("failure detail",file=sys.stderr);raise SystemExit(7)')
            code, output = runner.run_probe(probe, timeout=2)
            self.assertEqual(code, 7)
            self.assertIn('failure detail', output)
