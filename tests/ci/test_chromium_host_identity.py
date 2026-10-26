"""Actual host input bytes determine whether a checkpoint may resume."""
import importlib.util
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[2] / 'scripts/ci/chromium_host_identity.py'


def load():
    spec = importlib.util.spec_from_file_location('host_identity', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HostIdentity(unittest.TestCase):
    def test_homebrew_receipt_timestamp_is_provenance_not_runtime_identity(self):
        module = load()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'tool').write_bytes(b'identical installed tool')
            receipt = root / 'INSTALL_RECEIPT.json'
            receipt.write_text('{"time": 100}')
            first = module.tree_identity(root, homebrew_package=True)
            receipt.write_text('{"time": 200}')
            self.assertEqual(module.tree_identity(root, homebrew_package=True), first)
            self.assertEqual(module.install_provenance({'homebrewBuildTools': {'tool': first}}),
                             {'tool': {'time': 200}})
            (root / 'tool').write_bytes(b'changed tool')
            self.assertNotEqual(module.tree_identity(root, homebrew_package=True), first)

    def test_external_python_library_bytes_and_missing_libraries_are_bound(self):
        module = load()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root = base / 'python'
            root.mkdir()
            executable = root / 'python3'
            executable.write_bytes(b'\xcf\xfa\xed\xfeinterpreter fixture')
            library = base / 'external.dylib'
            library.write_bytes(b'\xcf\xfa\xed\xfelibrary fixture')

            def command(args, **kwargs):
                if args[:2] == ['otool', '-l']:
                    if Path(args[2]).resolve() == executable.resolve():
                        return f'cmd LC_LOAD_DYLIB\nname {library} (offset 24)\n'
                    return 'cmd LC_LOAD_DYLIB\nname /usr/lib/libSystem.B.dylib (offset 24)\n'
                raise AssertionError(args)

            with patch.object(module.subprocess, 'check_output', command):
                first = module.python_dependencies(root, executable)
                library.write_bytes(b'\xcf\xfa\xed\xfedifferent library')
                self.assertNotEqual(module.python_dependencies(root, executable), first)
                library.unlink()
                with self.assertRaisesRegex(ValueError, 'Missing host dependency'):
                    module.python_dependencies(root, executable)

    def test_collection_binds_xcode_python_and_union_of_tool_dependencies(self):
        module = load()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            developer = base / 'Xcode.app/Contents/Developer'
            developer.mkdir(parents=True)
            (developer / 'compiler').write_bytes(b'clang')
            python = base / 'python'
            python.mkdir()
            (python / 'python3').write_bytes(b'interpreter')
            metal = base / 'Metal.xctoolchain/usr/bin'
            metal.mkdir(parents=True)
            for tool in ('metal', 'metallib'):
                (metal / tool).write_bytes(tool.encode())
            packages = {}
            for name in ('cmake', 'ninja', 'ccache', 'zstd'):
                packages[name] = base / name
                packages[name].mkdir()
                (packages[name] / 'binary').write_bytes(name.encode())

            def command(args, **kwargs):
                if args[:4] == ['xcrun', '--sdk', 'macosx', '--find']:
                    return str(metal / args[4])
                if args == ['sw_vers', '-productVersion']:
                    return '26.6.2'
                if args == ['sw_vers', '-buildVersion']:
                    return '25G83'
                if args == ['brew', 'deps', '--installed', '--formula', '--union', 'ccache', 'cmake', 'ninja', 'zstd']:
                    return 'zstd\n'
                if args[:2] == ['brew', '--prefix']:
                    return str(packages[args[2]])
                raise AssertionError(args)

            with patch.object(module.platform, 'system', return_value='Darwin'), \
                    patch.object(module.platform, 'machine', return_value='arm64'), \
                    patch.object(module.subprocess, 'check_output', command), \
                    patch('shutil.which', side_effect=lambda name: str(packages[name] / 'binary')), \
                    patch.object(module.sys, 'base_prefix', str(python)):
                first = module.collect(developer)
                with patch.object(module.platform, 'machine', return_value='x86_64'):
                    intel = module.collect(developer)
                self.assertEqual(intel['architecture'], 'x86_64')
                self.assertEqual(intel['xcodeBundle'], first['xcodeBundle'])
                self.assertNotEqual(intel, first)
                self.assertEqual(set(first['homebrewBuildTools']), {'cmake', 'ninja', 'ccache', 'zstd'})
                (metal / 'metallib').write_bytes(b'changed Metal linker')
                self.assertNotEqual(module.collect(developer)['metalToolchains'], first['metalToolchains'])
                (packages['zstd'] / 'binary').write_bytes(b'changed dependency')
                self.assertNotEqual(module.collect(developer), first)
                (developer / 'compiler').write_bytes(b'changed compiler')
                self.assertNotEqual(module.collect(developer)['xcodeBundle'], first['xcodeBundle'])
                with patch('shutil.which', return_value=str(base / 'unbound-tool')):
                    with self.assertRaisesRegex(ValueError, 'outside fingerprinted'):
                        module.collect(developer)

    def test_sdk_byte_change_rejected_even_with_same_version_size_and_mtime(self):
        module = load()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            header = root / 'SDK/usr/include/test.h'
            header.parent.mkdir(parents=True)
            header.write_bytes(b'old ABI')
            first = module.tree_identity(root)
            stamp = header.stat().st_mtime_ns
            header.write_bytes(b'new ABI')
            os.utime(header, ns=(stamp, stamp))
            self.assertNotEqual(module.tree_identity(root), first)

    def test_mtime_change_keeps_content_identity_but_modes_and_links_do_not(self):
        module = load()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            binary = root / 'compiler'
            binary.write_bytes(b'compiler fixture')
            first = module.tree_identity(root)
            os.utime(binary, ns=(1, 1))
            self.assertEqual(module.tree_identity(root), first)
            binary.chmod(0o755)
            self.assertNotEqual(module.tree_identity(root), first)
            first = module.tree_identity(root)
            (root / 'current').symlink_to('compiler')
            self.assertNotEqual(module.tree_identity(root), first)
            (root / 'current').unlink()
            (root / 'outside').symlink_to(root.parent)
            with self.assertRaisesRegex(ValueError, 'external directory'):
                module.tree_identity(root)

    def test_python_cache_exclusion_does_not_exclude_python_sources(self):
        module = load()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'stdlib.py'
            source.write_text('original')
            before = module.tree_identity(root, python_runtime=True)
            cache = root / '__pycache__'
            cache.mkdir()
            (cache / 'stdlib.pyc').write_bytes(b'generated')
            self.assertEqual(module.tree_identity(root, python_runtime=True), before)
            source.write_text('changed')
            self.assertNotEqual(module.tree_identity(root, python_runtime=True), before)
