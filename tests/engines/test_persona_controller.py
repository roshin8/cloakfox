"""Shared snapshots through the actual production controller/CEF pipes."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engines.shared.persona_config import PersonaStore

class PersonaController(unittest.TestCase):
    def test_controller_opens_only_after_config_ack_and_rejects_live_mutation(self):
        if not os.environ.get('CLOAKFOX_CHROMIUM_BIN'):
            self.skipTest('Set CLOAKFOX_CHROMIUM_BIN for controller runtime')
        module = Path(__file__).resolve().parents[2] / 'engines/chromium/controller.py'
        self.assertTrue(module.exists(), 'Production config controller missing')
        from engines.chromium.controller import ChromiumController
        with tempfile.TemporaryDirectory() as root:
            store = PersonaStore(Path(root) / 'personas')
            config = store.get('1', 'chromium')
            with ChromiumController(Path(os.environ['CLOAKFOX_CHROMIUM_BIN']), Path(root)) as controller:
                opened = controller.open(config, 'about:blank')
                self.assertEqual(opened['configRevision'], config['revision'])
                self.assertEqual(controller.applied[('1', False)], config['revision'])
                changed = store.update(config, enabled=False)
                with self.assertRaisesRegex(RuntimeError, 'restart'):
                    controller.open(changed, 'about:blank')
                self.assertEqual(controller.applied[('1', False)], config['revision'])
                opened = controller.open(config, 'about:blank')
                self.assertTrue(opened['canvasEnabled'])
            with ChromiumController(Path(os.environ['CLOAKFOX_CHROMIUM_BIN']), Path(root)) as controller:
                opened = controller.open(changed, 'about:blank')
                self.assertFalse(opened['canvasEnabled'])
                self.assertEqual(opened['configRevision'], changed['revision'])

    def test_private_store_ownership_retires_on_context_or_process_shutdown(self):
        if not os.environ.get('CLOAKFOX_CHROMIUM_BIN'):
            self.skipTest('Set CLOAKFOX_CHROMIUM_BIN for controller runtime')
        from engines.chromium.controller import ChromiumController
        with tempfile.TemporaryDirectory() as root:
            store = PersonaStore(Path(root) / 'personas')
            config = store.get('1', 'chromium', private=True)
            with ChromiumController(Path(os.environ['CLOAKFOX_CHROMIUM_BIN']), Path(root)) as controller:
                self.assertIsInstance(getattr(controller, 'store', None), PersonaStore,
                                      'Controller does not own persona lifecycle')
            # Use that same controller store across sessions; old seed must retire.
            with ChromiumController(Path(os.environ['CLOAKFOX_CHROMIUM_BIN']), Path(root), store=store) as controller:
                keep = store.get('2', 'chromium'); controller.open(keep, 'about:blank')
                browser = controller.open(config, 'about:blank')['browser']
                controller.close_browser(browser)
                fresh = store.get('1', 'chromium', private=True)
                self.assertNotEqual(fresh['persona']['seed'], config['persona']['seed'])
                controller.open(fresh, 'about:blank')
            self.assertNotEqual(store.get('1', 'chromium', private=True)['persona']['seed'], fresh['persona']['seed'])
