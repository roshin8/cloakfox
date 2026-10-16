import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class RunnerProbe(unittest.TestCase):
    def api(self):
        path = ROOT / 'scripts/ci/runner_probe.py'
        self.assertTrue(path.exists(), 'Hosted runner measurement is missing')
        spec = importlib.util.spec_from_file_location('runner_probe', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_readiness_uses_measured_space_sdk_architecture_and_gpu(self):
        module = self.api()
        report = {
            'system': 'Darwin', 'architecture': 'arm64',
            'freeBytes': 150 * 1024**3, 'xcodeAvailable': True,
            'sdkVersion': '27.0', 'metalAvailable': True,
        }
        self.assertTrue(module.readiness(report)['sourceBuild'])
        self.assertTrue(module.readiness(report)['metalRuntime'])
        for key, value in [
            ('freeBytes', 14 * 1024**3), ('xcodeAvailable', False),
            ('architecture', 'x86_64'), ('system', 'Linux'),
            ('sdkVersion', '14.0'), ('sdkVersion', ''),
            ('sdkVersion', 'SDK unavailable'),
        ]:
            with self.subTest(key=key, value=value):
                self.assertFalse(module.readiness({**report, key: value})['sourceBuild'])
        self.assertTrue(module.readiness({**report, 'sdkVersion': '26.5'})['sourceBuild'])
        self.assertFalse(module.readiness({**report, 'sdkVersion': '26.4'})['sourceBuild'])
        self.assertFalse(module.readiness({**report, 'metalAvailable': False})['metalRuntime'])
        self.assertTrue(module.readiness({**report, 'freeBytes': 14 * 1024**3})['metalRuntime'])
        self.assertFalse(module.readiness({})['sourceBuild'])
