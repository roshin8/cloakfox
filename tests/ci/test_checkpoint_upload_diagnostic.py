import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[2] / 'scripts/ci/checkpoint_upload_diagnostic.py'


def load():
    spec = importlib.util.spec_from_file_location('upload_diagnostic', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UploadDiagnostic(unittest.TestCase):
    def test_runner_outside_observer_process_tree_is_measured_without_arguments(self):
        module = load()
        rows = '10 1 123 S /runner/Runner.Worker\n11 10 456 S /node20/bin/node\n12 1 999 S /private/unrelated\n'
        result = module.process_summary(rows)
        self.assertEqual([p['pid'] for p in result['runnerProcesses']], [10, 11])
        self.assertEqual(result['totalRssKiB'], 1578)
        self.assertNotIn('/private', str(result))

    def test_diagnostic_log_never_publishes_raw_urls_or_credentials(self):
        module = load()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            log = root / 'Worker_1.log'
            log.write_text('secret-token https://secret.invalid/?sig=secret\nHttpRequestException OutOfMemoryException\n')
            result = module.runner_log_summary(root)
            self.assertEqual(result[0]['signals']['HttpRequestException'], 1)
            self.assertEqual(result[0]['signals']['OutOfMemoryException'], 1)
            self.assertNotIn('secret', str(result))
            self.assertNotIn('https:', str(result))

    def test_checkpoint_verification_checks_exact_sha_and_archive_digest(self):
        module = load()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / 'workspace.tar.gz'
            archive.write_bytes(b'fixture')
            import hashlib, json
            receipt = {'schemaVersion': 1, 'identity': {'gitSha': module.PRODUCER_SHA},
                       'sha256': hashlib.sha256(b'fixture').hexdigest(), 'bytes': 7}
            archive.with_suffix('.json').write_text(json.dumps(receipt))
            self.assertEqual(module.verify(root)['bytes'], 7)
            archive.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                module.verify(root)
