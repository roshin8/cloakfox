"""Keep the Chromium parity checklist tied to the pinned Gecko sources."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
ROOT = Path(__file__).resolve().parents[2]

class PrivacyInventory(unittest.TestCase):
    def test_inventory_covers_current_canonical_patches_and_settings(self):
        module = ROOT / 'engines/chromium/update_inventory.py'
        self.assertTrue(module.exists(), 'Gecko inventory generator missing')
        from engines.chromium.update_inventory import collect_inventory
        actual = collect_inventory(ROOT)
        recorded = json.loads((ROOT / ('engines/chromium/gecko' + actual['geckoVersion'].split('.')[0] + '-inventory.json')).read_text())
        self.assertEqual(actual, recorded, 'Refresh the pinned Gecko inventory')
        self.assertIn('patches/canvas-complete-renderer.patch', actual['patches'])
        self.assertIn('patches/cloakfox-audioworklet-privacy.patch', actual['patches'])
        self.assertIn('cloakfox.opt.container_rendering_profiles', actual['preferences'])
        self.assertIn('cfx-generation-clear-overrides', actual['settingsBindings'])
