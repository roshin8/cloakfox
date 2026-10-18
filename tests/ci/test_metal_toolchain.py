import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
import signal

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
    def test_timeout_terminates_descendant_process_group(self):
        class Child:
            pid = 12345
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def kill(self): pass
            def wait(self): return -9
            def __init__(self): self.calls = 0
            def communicate(self, *args, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise subprocess.TimeoutExpired(['xcrun'], 120)
                return ('', None)
        child = Child()
        with patch.object(metal.subprocess, 'Popen', return_value=child) as launched, \
                patch.object(metal.os, 'killpg') as killed:
            with self.assertRaises(subprocess.TimeoutExpired):
                metal.command(['xcrun', '--sdk', 'macosx', '--show-sdk-version'])
            self.assertTrue(launched.call_args.kwargs.get('start_new_session', False))
            killed.assert_called_once_with(child.pid, signal.SIGKILL)
            self.assertEqual(child.calls, 2)

    def test_timeout_cleanup_cannot_block_on_an_escaped_descendant_pipe(self):
        class Child:
            pid = 12345
            stdout = None
            def __init__(self): self.deadlines = []
            def communicate(self, **kwargs):
                self.deadlines.append(kwargs.get('timeout'))
                if kwargs.get('timeout') is None:
                    raise AssertionError('unbounded drain after timeout')
                raise subprocess.TimeoutExpired(['xcrun'], kwargs['timeout'])
            def wait(self, **kwargs): return -9
        child = Child()
        with patch.object(metal.subprocess, 'Popen', return_value=child), \
                patch.object(metal.os, 'killpg'):
            with self.assertRaises(subprocess.TimeoutExpired) as raised:
                metal.command(['xcrun'])
            self.assertEqual(raised.exception.timeout, 120)
            self.assertEqual(child.deadlines, [120, 5])

    def test_missing_library_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises((ValueError, FileNotFoundError)):
                metal.verify(Path(directory), lambda argv: '/tool/metal')

if __name__ == '__main__': unittest.main()
