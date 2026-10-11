import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/stage_ublock.py'


class StageBlockerTests(unittest.TestCase):
    def load(self):
        self.assertTrue(SCRIPT.exists(), 'uBO staging helper is not implemented')
        spec = importlib.util.spec_from_file_location('stage_ublock', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def fixture(self, addon_id='uBlock0@raymondhill.net', signature=True, update_url=None):
        manifest = dict(version='1.74.0', browser_specific_settings={'gecko': {'id': addon_id}})
        if update_url:
            manifest['browser_specific_settings']['gecko']['update_url'] = update_url
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            archive.writestr('manifest.json', json.dumps(manifest))
            if signature:
                for name in ('META-INF/mozilla.rsa', 'META-INF/mozilla.sf', 'META-INF/manifest.mf', 'META-INF/cose.sig'):
                    archive.writestr(name, 'TEST structural placeholder, not a valid signature')
        data = output.getvalue()
        return data, dict(version='1.74.0', size=len(data), sha256=hashlib.sha256(data).hexdigest())

    def test_verified_hash_and_expected_identity(self):
        self.load().verify_xpi(*self.fixture())

    def test_tampered_package(self):
        module = self.load()
        data, pin = self.fixture()
        with self.assertRaisesRegex(ValueError, 'hash|size'):
            module.verify_xpi(data + b'bad', pin)

    def test_wrong_identity_even_when_hash_matches(self):
        with self.assertRaisesRegex(ValueError, 'identity'):
            self.load().verify_xpi(*self.fixture(addon_id='attacker@example.org'))

    def test_missing_signature_envelope(self):
        with self.assertRaisesRegex(ValueError, 'signature'):
            self.load().verify_xpi(*self.fixture(signature=False))

    def test_unexpected_update_endpoint(self):
        with self.assertRaisesRegex(ValueError, 'update'):
            self.load().verify_xpi(*self.fixture(update_url='https://attacker.example/update'))

    def test_corrupt_cached_file_fails_without_network(self):
        module = self.load()
        _, pin = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            cached = Path(directory) / 'cached.xpi'
            cached.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError, 'hash|size'):
                module.get_package(pin, cached)


if __name__ == '__main__':
    unittest.main()
