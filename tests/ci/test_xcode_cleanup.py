import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location('prepare', Path(__file__).resolve().parents[2]/'scripts/ci/prepare_macos.py')
prepare = importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
class Cleanup(unittest.TestCase):
    def test_preserve_active_installation_excludes_its_platforms_and_simulator_state(self):
        developer=Path('/Applications/Xcode.app/Contents/Developer')
        unused=Path('/Applications/Xcode_old.app')
        self.assertEqual(prepare.cleanup_targets([unused],developer,Path('/Users/runner'),preserve_active=True),[unused])
        legacy=prepare.cleanup_targets([unused],developer,Path('/Users/runner'),preserve_active=False)
        self.assertIn(developer/'Platforms/iPhoneOS.platform',legacy)
        self.assertIn(Path('/Users/runner/Library/Developer/CoreSimulator'),legacy)
if __name__=='__main__':unittest.main()
