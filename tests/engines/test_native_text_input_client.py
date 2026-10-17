"""Compile and execute the AppKit input boundary without a CEF/page wrapper."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(sys.platform == 'darwin', 'Native AppKit acceptance requires macOS')
class NativeTextInputClient(unittest.TestCase):
    def test_composition_metadata_and_retirement_boundary(self):
        with tempfile.TemporaryDirectory(prefix='cloakfox-appkit-input-') as directory:
            binary = Path(directory) / 'text_input_client_test'
            compile_result = subprocess.run([
                'clang++', '-std=c++20', '-fno-objc-arc', '-fno-exceptions',
                '-I', str(ROOT / 'additions/widget/cocoa'),
                str(ROOT / 'tests/engines/text_input_client_test.mm'),
                str(ROOT / 'additions/widget/cocoa/CloakfoxTextInputClient.mm'),
                '-framework', 'Cocoa', '-framework', 'Carbon', '-o', str(binary),
            ], capture_output=True, text=True, timeout=60)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
