"""Compile exact-owner canonical layout admission and irreversible revocation."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]
class CanonicalGeometry(unittest.TestCase):
    def test_native_policy(self):
        with tempfile.TemporaryDirectory(prefix='cloakfox-canonical-geometry-') as temp:
            binary = Path(temp) / 'policy'
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I', str(ROOT / 'additions/cloakcfg'),
                            str(ROOT / 'tests/fingerprint/native/canonical_geometry.cpp'),
                            '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
