#!/usr/bin/env python3
"""Hosted-only shutdown reproduction against previously verified app bytes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / 'tests/engines'))
import probe_cef_isolation

OUTPUT = Path(os.environ['SHUTDOWN_EVIDENCE'])
OUTPUT.mkdir(parents=True, exist_ok=True)
original = probe_cef_isolation.Companion.close
counter = 0

def close_with_diagnostics(self):
    global counter
    counter += 1
    folder = OUTPUT / str(counter)
    folder.mkdir()
    done = threading.Event()
    def sample():
        if done.wait(3) or self.process.poll() is not None:
            return
        listing = subprocess.run(['ps', '-axo', 'pid,ppid,command'], capture_output=True, text=True)
        (folder / 'processes.txt').write_text(listing.stdout)
        # Capture the browser and its direct helpers while the original close
        # deadline/watchdog remain unchanged. Sampling never decides test success.
        pids = [self.process.pid]
        for line in listing.stdout.splitlines()[1:]:
            parts = line.split(None, 2)
            if len(parts) == 3 and parts[1] == str(self.process.pid):
                pids.append(int(parts[0]))
        workers = []
        def one(pid):
            try:
                subprocess.run(['sample', str(pid), '1', '-file', str(folder / f'{pid}.sample.txt')],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            except subprocess.TimeoutExpired:
                pass
        for pid in pids:
            thread = threading.Thread(target=one, args=(pid,))
            thread.start()
            workers.append(thread)
        for thread in workers:
            thread.join()
    thread = threading.Thread(target=sample)
    thread.start()
    try:
        return original(self)
    finally:
        done.set()
        thread.join(timeout=7)

probe_cef_isolation.Companion.close = close_with_diagnostics
full_suite = os.environ.get('SHUTDOWN_FULL_SUITE') == '1'
if full_suite:
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests/engines'), pattern='test_*.py')
else:
    suite = unittest.TestSuite()
    for _ in range(10):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(
            'test_webgpu_pixel_privacy.WebGPUPixelPrivacy.test_private_pixels_regenerate_after_last_private_window'))
if full_suite:
    sys.path.insert(0, str(ROOT / 'scripts/ci'))
    import run_engine_tests
    raise SystemExit(0 if run_engine_tests.run_suite(suite, sys.stderr) else 1)
result = unittest.TextTestRunner(verbosity=2).run(suite)
(OUTPUT / 'result.json').write_text(json.dumps({'tests': result.testsRun,
    'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped)}, indent=2))
raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
