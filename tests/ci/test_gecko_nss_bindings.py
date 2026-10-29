"""Keep Firefox159's validated NSS binding lists ordered without losing flags."""
from pathlib import Path
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NssBindings(unittest.TestCase):
    def test_native_binding_variables_keep_both_privacy_flags_in_order(self):
        path=ROOT/'firefox-src/third_party/rust/nss-rs/bindings/bindings.toml'
        if not path.exists():self.skipTest('Requires patched Firefox source')
        names=tomllib.loads(path.read_text())['nss_sslopt']['variables']
        self.assertEqual(names,sorted(set(names)))
        self.assertIn('SSL_CLOAKFOX_APPLICATION_SETTINGS',names)
        self.assertIn('SSL_CLOAKFOX_CHROME_PROFILE',names)
        self.assertIn('SSL_ENABLE_CH_EXTENSION_PERMUTATION',names)
