"""Run the real DMG entry point with temporary bundles and a fake image writer."""
import os
import importlib.util
import shlex
import sys
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class PackageIdentity(unittest.TestCase):
    def package(self, name, identifier, executable):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contents = root / 'source/obj-test/dist' / name / 'Contents'
            contents.mkdir(parents=True)
            with (contents / 'Info.plist').open('wb') as f:
                plistlib.dump({'CFBundleIdentifier': identifier, 'CFBundleExecutable': executable,
                              'CFBundleName': 'Cloakfox'}, f)
            tools = root / 'tools'; tools.mkdir()
            writer = tools / 'hdiutil'
            writer.write_text('#!/bin/sh\ntouch "$PACKAGE_WRITER_CALLED"\n')
            writer.chmod(0o755)
            called = root / 'writer-called'
            result = subprocess.run(['bash', str(ROOT / 'scripts/package-dmg.sh'), str(root / 'source')],
                cwd=root, env={**os.environ, 'PATH': str(tools)+os.pathsep+os.environ['PATH'],
                              'PACKAGE_WRITER_CALLED': str(called)}, capture_output=True, text=True)
            return result, called.exists()

    def test_firefox_named_bundle_is_refused_before_image_creation(self):
        result, called = self.package('Firefox.app', 'org.mozilla.cloakfox.appearance.firefox', 'firefox')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(called)

    def test_renamed_appearance_bundle_is_still_refused(self):
        result, called = self.package('Cloakfox.app', 'org.mozilla.cloakfox.appearance.firefox', 'firefox')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(called)

    def test_repackaging_cannot_inject_a_profile_binding(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        try:
            spec = importlib.util.spec_from_file_location('appearance_safety_package', ROOT / 'scripts/package.py')
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); archive = root / 'input.dmg'; archive.touch()
                binding = root / 'cloakfox-profile.ini'; binding.write_text('foreign profile')
                written = []
                def tool(command, **kwargs):
                    args = shlex.split(command)
                    if args[1] == 'x':
                        extracted = Path(args[3][2:]) / 'Cloakfox/Cloakfox.app/Contents'
                        extracted.mkdir(parents=True)
                        with (extracted / 'Info.plist').open('wb') as f:
                            plistlib.dump({'CFBundleIdentifier':'org.mozilla.cloakfox',
                                          'CFBundleExecutable':'cloakfox', 'CFBundleName':'Cloakfox'}, f)
                        (extracted / 'Resources').mkdir()
                    else:
                        written.append(command)
                module.run = tool
                with self.assertRaisesRegex(ValueError, 'appearance-mode'):
                    module.add_includes_to_package(str(archive), [str(binding)], [], str(root/'out.zip'), 'macos')
                self.assertFalse(written)
        finally:
            sys.path.pop(0)

    def test_normal_cloakfox_package_is_allowed(self):
        result, called = self.package('Cloakfox.app', 'org.mozilla.cloakfox', 'cloakfox')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(called)

if __name__ == '__main__':
    unittest.main()
