"""Compile the shared DOM geometry helper and exercise its semantic contract."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class DomGeometry(unittest.TestCase):
    def test_native_geometry(self):
        with tempfile.TemporaryDirectory(prefix='cloakfox-dom-native-') as temp:
            binary = Path(temp) / 'dom-geometry'
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I', str(ROOT / 'additions/cloakcfg'),
                            str(ROOT / 'tests/fingerprint/native/dom_geometry.cpp'),
                            '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

if __name__ == '__main__':
    unittest.main()
