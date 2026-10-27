"""Gecko builds use their own source-matched compiler without shared CEF setup."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
class GeckoToolchainJob(unittest.TestCase):
 def test_native_build_uses_source_selected_mozilla_compiler(self):
  source=(ROOT/'.github/workflows/gecko-engine.yml').read_text()
  self.assertIn('--from-build macosx64-aarch64-clang',source)
  self.assertIn('--artifact-manifest gecko-clang-artifact.json',source)
  self.assertIn('echo "CC=$PWD/clang/bin/clang"',source)
  self.assertIn('echo "CXX=$PWD/clang/bin/clang++"',source)
  self.assertIn('echo "LIBCLANG_PATH=$PWD/clang/lib"',source)
  self.assertIn('ac_add_options --enable-linker=ld64',source)
  self.assertLess(source.index('--from-build macosx64-aarch64-clang'),source.index('      - name: Build\n'))
