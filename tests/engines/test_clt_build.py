"""Exercise the optional CLT configuration against pinned upstream GN input."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).parents[2]
PREPARE = ROOT / 'engines/chromium/prepare_clt_build.py'
HELPER = ROOT / 'engines/chromium/clt_sdk_info.py'
UPSTREAM = Path(__file__).with_name('fixtures') / 'mac_sdk_154.gni'


class CltPatch(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.gni = self.root / 'build/config/mac/mac_sdk.gni'
        self.gni.parent.mkdir(parents=True)
        shutil.copyfile(UPSTREAM, self.gni)

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self):
        return subprocess.run([sys.executable, str(PREPARE), '--source-root', str(self.root)],
                              text=True, capture_output=True)

    def test_pinned_patch_is_repeatable_and_preserves_upstream_backup(self):
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(self.gni.read_bytes(), UPSTREAM.read_bytes())
        self.assertEqual(self.gni.with_suffix('.gni.cloakfox-original').read_bytes(), UPSTREAM.read_bytes())
        self.assertEqual((self.root / 'build/config/apple/clt_sdk_info.py').read_bytes(), HELPER.read_bytes())
        applied = self.gni.read_bytes()
        self.assertEqual(self.prepare().returncode, 0)
        self.assertEqual(self.gni.read_bytes(), applied)

    def test_changed_upstream_is_rejected_without_writing_anything(self):
        self.gni.write_text(self.gni.read_text() + '\n# changed upstream\n')
        before = self.gni.read_bytes()
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unsupported Chromium GN input', result.stderr)
        self.assertEqual(self.gni.read_bytes(), before)
        self.assertFalse((self.root / 'build/config/apple/clt_sdk_info.py').exists())


@unittest.skipUnless(sys.platform == 'darwin', 'requires actual installed Apple tools')
class NativeCltSdk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        active = subprocess.check_output(['xcode-select', '-p'], text=True).strip()
        if Path(active).name != 'CommandLineTools':
            raise unittest.SkipTest('native CLT characterization requires CLT selected')

    def test_discovery_uses_installed_receipt_and_real_sdk_paths(self):
        result = subprocess.run([sys.executable, str(HELPER), 'macosx'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        values = {key: json.loads(value) for key, value in
                  (line.split('=', 1) for line in result.stdout.splitlines())}
        self.assertEqual(values['apple_toolchain_type'], 'command_line_tools')
        receipt = subprocess.check_output(['pkgutil', '--pkg-info-plist', 'com.apple.pkg.CLTools_Executables'])
        import plistlib
        self.assertEqual(values['apple_toolchain_version'], plistlib.loads(receipt)['pkg-version'])
        sdk = subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-path'], text=True).strip()
        self.assertEqual(Path(values['sdk_path']).resolve(), Path(sdk).resolve())
        self.assertTrue((Path(values['mac_bin_path']) / 'clang').is_file())
        self.assertEqual(values['sdk_version'], subprocess.check_output(
            ['xcrun', '--sdk', 'macosx', '--show-sdk-version'], text=True).strip())

    def test_ios_is_not_treated_as_supported_by_clt(self):
        result = subprocess.run([sys.executable, str(HELPER), 'iphoneos'], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('invalid choice', result.stderr)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
