import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('metal_toolchain', ROOT / 'scripts/ci/metal_toolchain.py')
metal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metal)

class MetalToolchainTests(unittest.TestCase):
    def test_compile_then_link_and_check_output(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            def run(argv):
                calls.append(argv)
                if '-o' in argv:
                    Path(argv[argv.index('-o') + 1]).write_bytes(b'compiled')
                return '/tool/' + argv[-1] if '--find' in argv else 'version'
            report = metal.verify(Path(directory), run)
            compile_call = next(c for c in calls if '-c' in c)
            self.assertIn('air64-apple-macos26.0', compile_call)
            self.assertLess(calls.index(compile_call), next(i for i,c in enumerate(calls) if 'metallib' in c and '--find' not in c))
            self.assertTrue(report['shaderCompileAndLink'])
            self.assertTrue(any('--std=macos-metal2.1' in c and '-mmacosx-version-min=10.14' in c for c in calls))
            self.assertEqual(len([c for c in calls if 'metallib' in c and '--find' not in c]), 2)
    def test_missing_library_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises((ValueError, FileNotFoundError)):
                metal.verify(Path(directory), lambda argv: '/tool/metal')

if __name__ == '__main__': unittest.main()
