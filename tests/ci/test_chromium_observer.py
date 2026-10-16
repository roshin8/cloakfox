import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import io
import os
import threading

PATH = Path(__file__).resolve().parents[2] / 'scripts/ci/chromium_observer.py'


def load():
    spec = importlib.util.spec_from_file_location('observer', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Observer(unittest.TestCase):
    def test_independent_thread_reports_stale_stage_and_finishes_neutrally(self):
        module = load()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'build'
            (root / 'evidence').mkdir(parents=True)
            state = root / 'evidence/stage.json'
            state.write_text('{"stage":"framework","state":"running"}')
            os.utime(state, (1, 1))
            observer = module.Observer(root, Path(folder) / 'observer')
            reports, ready = [], threading.Event()

            class Sink:
                def publish(self, data, finished=False):
                    reports.append((data, finished))
                    if len(reports) >= 2:
                        ready.set()

            observer.publisher = Sink()
            original_wait = observer.stopped.wait
            with patch.object(observer.stopped, 'wait', side_effect=lambda _: original_wait(.03)):
                observer.start()
                try:
                    self.assertTrue(ready.wait(3), 'Independent telemetry must publish while the stage stays unchanged')
                finally:
                    observer.stop()
            self.assertGreater(reports[0][0]['stageAgeSeconds'], 100)
            self.assertNotEqual(reports[0][0]['observedAt'], reports[1][0]['observedAt'])
            self.assertTrue(reports[-1][1])
            self.assertTrue(json.loads((Path(folder) / 'observer/runner-telemetry.json').read_text())['finished'])

    def test_diagnostic_token_is_removed_before_child_environment_copy(self):
        module = load()
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {
                'CHROMIUM_TELEMETRY_TOKEN': 'private-token', 'GITHUB_REPOSITORY': 'owner/repo',
                'GITHUB_SHA': 'commit'}):
            observer = module.Observer(Path(folder) / 'build', Path(folder) / 'evidence')
            self.assertIsNotNone(observer.publisher)
            self.assertNotIn('CHROMIUM_TELEMETRY_TOKEN', dict(os.environ))

    def test_snapshot_observes_real_child_without_command_arguments(self):
        module = load()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            evidence = root / 'evidence'
            evidence.mkdir()
            child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(10)', 'private-argument'])
            try:
                (evidence / 'stage.json').write_text(json.dumps({'stage': 'framework', 'childPid': child.pid, 'state': 'running'}))
                (evidence / 'framework.log').write_bytes(b'compiler output')
                snapshot = module.snapshot(root)
                self.assertEqual(snapshot['logBytes'], 15)
                self.assertIn(child.pid, [p['pid'] for p in snapshot['processes']])
                self.assertNotIn('private-argument', json.dumps(snapshot))
                self.assertGreater(snapshot['rssKiB'], 0)
            finally:
                child.terminate()
                child.wait(timeout=3)

    def test_check_run_updates_independently_and_remains_telemetry_only(self):
        module = load()
        requests = []

        def response(request, **kwargs):
            requests.append((request.method, json.loads(request.data)))
            return io.BytesIO(b'{"id": 123}')

        with patch.object(module.urllib.request, 'urlopen', response):
            publisher = module.Publisher('owner/repo', 'commit', 'token', '1')
            publisher.publish({'observedAt': 'now', 'logBytes': 42})
            publisher.publish({'observedAt': 'later', 'logBytes': 43}, finished=True)
        self.assertEqual([method for method, _ in requests], ['POST', 'PATCH'])
        self.assertEqual(requests[0][1]['head_sha'], 'commit')
        self.assertEqual(requests[0][1]['conclusion'], 'neutral')
        self.assertEqual(requests[1][1]['conclusion'], 'neutral')
        self.assertIn('later', requests[1][1]['output']['summary'])
        self.assertNotIn('token', json.dumps(requests))
