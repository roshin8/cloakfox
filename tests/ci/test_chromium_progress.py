"""Exercise CI progress with real children that wait for the observer to release them."""
import importlib.util
import contextlib
import io
from types import SimpleNamespace
from unittest.mock import patch
import json
from pathlib import Path
import selectors
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/ci/chromium_source.py'


class ChromiumProgress(unittest.TestCase):
    def test_blocked_actions_console_cannot_block_compiler_deadline(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            child = "import sys,time;sys.stdout.write('x'*4000000);sys.stdout.flush();time.sleep(10)"
            driver = ("import importlib.util,os,sys\nfrom pathlib import Path\n"
                      f"s=importlib.util.spec_from_file_location('pipeline',{str(SCRIPT)!r})\n"
                      "m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
                      "os.environ['GITHUB_ACTIONS']='true'\n"
                      "m.POLL_INTERVAL=.01;m.PROGRESS_INTERVAL=.05\n"
                      "from types import SimpleNamespace\n"
                      "m.shutil.disk_usage=lambda _:SimpleNamespace(free=20*m.GIB)\n"
                      f"m.Pipeline(Path({folder!r})).run('fixture',[sys.executable,'-u','-c',{child!r}],time_budget_seconds=.2)\n")
            process = subprocess.Popen([sys.executable, '-u', '-c', driver], stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL)
            status = {}
            try:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    try:
                        status = json.loads((root / 'evidence/stage.json').read_text())
                    except (FileNotFoundError, json.JSONDecodeError):
                        pass
                    if status.get('state') == 'checkpoint':
                        break
                    time.sleep(.02)
                # Intentionally never drain the Actions console pipe until after
                # the deadline decision: the evidence file must remain exact.
                self.assertEqual(status.get('state'), 'checkpoint')
                self.assertGreater(status['consoleDroppedBytes'], 0)
                self.assertTrue((root / 'evidence/fixture.log').read_bytes().startswith(b'x' * 4000000))
            finally:
                if process.poll() is None:
                    process.kill()
                if status.get('childPid'):
                    try:
                        os.killpg(status['childPid'], signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.communicate(timeout=3)

    def observe_running(self, child_output, expected):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            gate = root / 'release'
            child = ("import pathlib,sys,time; " + child_output +
                     f"\ngate=pathlib.Path({str(gate)!r})\n"
                     "deadline=time.monotonic()+10\n"
                     "while not gate.exists() and time.monotonic()<deadline: time.sleep(.02)\n")
            driver = (f"import importlib.util,sys\nfrom pathlib import Path\n"
                      f"s=importlib.util.spec_from_file_location('pipeline',{str(SCRIPT)!r})\n"
                      "m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
                      "m.PROGRESS_INTERVAL=.1;m.POLL_INTERVAL=.02\n"
                      "from types import SimpleNamespace\n"
                      "m.shutil.disk_usage=lambda _:SimpleNamespace(free=20*m.GIB)\n"
                      f"m.Pipeline(Path({folder!r})).run('fixture',[sys.executable,'-u','-c',{child!r}])\n")
            process = subprocess.Popen([sys.executable, '-u', '-c', driver], stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)
            data = b''
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    deadline = time.monotonic() + 3
                    while expected not in data and time.monotonic() < deadline:
                        if selector.select(.1):
                            data += process.stdout.read1(65536)
                        if process.poll() is not None:
                            break
                self.assertIn(expected, data, 'Progress must be visible before child exits')
                self.assertIsNone(process.poll())
                status = json.loads((root / 'evidence/stage.json').read_text())
                self.assertEqual(status['state'], 'running')
                return status
            finally:
                gate.touch()
                rest, _ = process.communicate(timeout=8)
                self.assertEqual(process.returncode, 0, (data + rest).decode(errors='replace'))
                if child_output:
                    self.assertEqual((root / 'evidence/fixture.log').read_bytes(), 'live ✓\nerror\n'.encode())

    def test_stdout_and_stderr_stream_before_exit_and_keep_exact_log(self):
        self.observe_running("print('live ✓',flush=True); print('error',file=sys.stderr,flush=True)", b'live ')

    def test_quiet_child_reports_elapsed_output_age_and_disk_space(self):
        status = self.observe_running('', b'PROGRESS ')
        self.assertGreaterEqual(status['elapsedSeconds'], .05)
        self.assertGreaterEqual(status['outputIdleSeconds'], .05)
        self.assertEqual(status['outputBytes'], 0)
        self.assertGreater(status['freeBytes'], 0)
        self.assertGreater(status['childPid'], 0)

    def test_failure_keeps_output_and_nonzero_status(self):
        spec = importlib.util.spec_from_file_location('pipeline', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaisesRegex(RuntimeError, 'fixture failed: 7'):
                module.Pipeline(root).run('fixture', [sys.executable, '-c', "print('failure detail'); raise SystemExit(7)"])
            self.assertEqual((root / 'evidence/fixture.log').read_text(), 'failure detail\n')
            status = json.loads((root / 'evidence/stage.json').read_text())
            self.assertEqual(status['state'], 'failed')
            self.assertEqual(status['exitCode'], 7)

    def test_inherited_log_does_not_hide_direct_child_failure(self):
        spec = importlib.util.spec_from_file_location('pipeline', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.POLL_INTERVAL = .02
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            gate = root / 'release'
            descendant = (f"from pathlib import Path;import time;g=Path({str(gate)!r})\n"
                          "deadline=time.monotonic()+5\n"
                          "while not g.exists() and time.monotonic()<deadline:time.sleep(.02)\n")
            child = ("import subprocess,sys;"
                     f"subprocess.Popen([sys.executable,'-c',{descendant!r}],stdout=sys.stdout,stderr=sys.stderr);"
                     "print('direct child failed',flush=True);raise SystemExit(7)")
            started = time.monotonic()
            try:
                with self.assertRaisesRegex(RuntimeError, 'fixture failed: 7'):
                    module.Pipeline(root).run('fixture', [sys.executable, '-c', child])
                self.assertLess(time.monotonic() - started, 2)
            finally:
                gate.touch()

    def test_reserve_shutdown_preserves_large_final_output_and_failure(self):
        spec = importlib.util.spec_from_file_location('pipeline', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.POLL_INTERVAL = .02
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            log = root / 'evidence/fixture.log'
            def disk_usage(_):
                ready = log.exists() and log.stat().st_size > 0
                return SimpleNamespace(free=(9 if ready else 20) * module.GIB)
            child = ("import signal,sys,time\n"
                     "def stop(*args):\n"
                     " sys.stdout.buffer.write(b'x'*2000000);sys.stdout.flush();raise SystemExit(0)\n"
                     "signal.signal(signal.SIGTERM,stop)\n"
                     "print('ready',flush=True)\n"
                     "while True:time.sleep(.02)\n")
            with patch.object(module.shutil, 'disk_usage', side_effect=disk_usage), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, '10 GiB storage reserve'):
                    module.Pipeline(root).run('fixture', [sys.executable, '-u', '-c', child])
            self.assertEqual(log.read_bytes(), b'ready\n' + b'x' * 2000000)
            status = json.loads((root / 'evidence/stage.json').read_text())
            self.assertEqual(status['state'], 'failed')
            self.assertEqual(status['exitCode'], 0)
            self.assertIn('storage reserve', status['error'])

    def test_budget_interrupt_is_checkpoint_not_build_success(self):
        spec = importlib.util.spec_from_file_location('pipeline', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.POLL_INTERVAL = .02
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            complete = module.Pipeline(root).run('fixture', [sys.executable, '-u', '-c',
                "import time;print('compiling',flush=True);time.sleep(10)"], time_budget_seconds=.1)
            self.assertFalse(complete)
            status = json.loads((root / 'evidence/stage.json').read_text())
            self.assertEqual(status['state'], 'checkpoint')
            self.assertNotEqual(status['exitCode'], 0)
