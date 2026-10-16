import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('canonical_checkout', ROOT / 'scripts/build-canonical-gpu.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class CheckoutRecovery(unittest.TestCase):
    def test_transient_fetch_recovers_and_keeps_exact_pin(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'source'
            source.mkdir()
            build.run(['git', 'init', '-q'], source)
            build.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'fixture'], source)
            revision = build.output(['git', 'rev-parse', 'HEAD'], source)
            target = Path(temp) / 'target'
            real_run = build.run
            failures = [True]

            def flaky(command, cwd, **kwargs):
                if command[:2] == ['git', 'fetch'] and failures:
                    failures.pop()
                    raise subprocess.CalledProcessError(128, command, stderr='error: RPC failed; HTTP 503 curl 22')
                return real_run(command, cwd, **kwargs)

            # Sleep is the only wall-clock dependency; Git operations remain real.
            with patch.object(build, 'run', flaky), patch('time.sleep'):
                build.checkout(target, str(source), revision)
            self.assertEqual(build.output(['git', 'rev-parse', 'HEAD'], target), revision)
            # A completed checkout must not reset caller changes or fetch again.
            (target / 'preserved').write_text('keep')
            build.checkout(target, str(source), revision)
            self.assertEqual((target / 'preserved').read_text(), 'keep')
            with self.assertRaises(ValueError):
                build.checkout(target, str(source), '0' * 40)

    def test_empty_checkout_resumes_after_previous_fetch_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'source'
            source.mkdir()
            build.run(['git', 'init', '-q'], source)
            build.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'fixture'], source)
            revision = build.output(['git', 'rev-parse', 'HEAD'], source)
            target = Path(temp) / 'target'
            target.mkdir()
            build.run(['git', 'init', '-q'], target)
            build.run(['git', 'remote', 'add', 'origin', str(source)], target)
            build.checkout(target, str(source), revision)
            self.assertEqual(build.output(['git', 'rev-parse', 'HEAD'], target), revision)

    def test_fetch_failure_is_bounded_and_does_not_checkout(self):
        for message in ('HTTP 503', 'fatal: remote error: upload-pack: not our ref'):
            with self.subTest(message=message), tempfile.TemporaryDirectory() as temp:
                target = Path(temp) / 'target'
                real_run = build.run
                attempts = []

                def failed(command, cwd, **kwargs):
                    if command[:2] == ['git', 'fetch']:
                        attempts.append(command)
                        raise subprocess.CalledProcessError(128, command, stderr=message)
                    return real_run(command, cwd, **kwargs)

                with patch.object(build, 'run', failed), patch('time.sleep'):
                    with self.assertRaises(subprocess.CalledProcessError):
                        build.checkout(target, 'https://example.invalid/source', 'a' * 40)
                self.assertEqual(len(attempts), 3 if message == 'HTTP 503' else 1)
                self.assertNotEqual(subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=target, capture_output=True).returncode, 0)
