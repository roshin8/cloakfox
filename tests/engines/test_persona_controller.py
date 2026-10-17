"""Shared snapshots through the development controller and real CEF pipes."""
import os
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engines.shared.persona_config import PersonaStore

class PersonaController(unittest.TestCase):
    def test_initial_snapshot_acknowledgement_is_strict_and_owner_bound(self):
        from engines.chromium.controller import ChromiumController
        with tempfile.TemporaryDirectory() as folder:
            config=PersonaStore(Path(folder)).get('1','chromium')
            expected={'schemaVersion':1,'appliedBeforeServices':True,'container':'1','private':False,'revision':1}
            cases=[None,{},*({**expected,**change} for change in (
                {'schemaVersion':True},{'appliedBeforeServices':1},{'appliedBeforeServices':False},
                {'container':'2'},{'private':0},{'revision':True},{'revision':2},{'seed':'private-data'}))]
            for status in cases:
                with self.subTest(status=status):
                    controller=object.__new__(ChromiumController)
                    controller.ready={'identityPrivacyVersion':2,'initialSnapshotVersion':1,
                        'supportedPersonaOptions':['canvas','blockWebGPUReadback','navigator','language','timezone','display']}
                    controller.applied={}
                    controller._request=lambda *args,**kwargs:{'event':'configApplied','engine':'chromium',
                        'container':'1','private':False,'configRevision':1,'initialSnapshotStatus':copy.deepcopy(status)}
                    with self.assertRaisesRegex(RuntimeError,'initial native snapshot'):controller._apply(config)
                    self.assertEqual(controller.applied,{})

    def test_unsupported_initial_snapshot_capability_rejects_before_rpc(self):
        from engines.chromium.controller import ChromiumController
        with tempfile.TemporaryDirectory() as folder:
            config=PersonaStore(Path(folder)).get('1','chromium')
            for version in (-1,2,True,'1',None):
                controller=object.__new__(ChromiumController)
                controller.ready={'identityPrivacyVersion':2,'initialSnapshotVersion':version,
                    'supportedPersonaOptions':['canvas','blockWebGPUReadback','navigator','language','timezone','display']}
                writes=[];controller._request=lambda *args,**kwargs:writes.append((args,kwargs))
                with self.assertRaisesRegex(RuntimeError,'initial native snapshot'):controller._apply(config)
                self.assertEqual(writes,[])

    def test_v1_helper_refuses_extended_processor_counts_before_any_rpc(self):
        from engines.chromium.controller import ChromiumController
        with tempfile.TemporaryDirectory() as folder:
            config=PersonaStore(Path(folder)).get('1','chromium')
            config['persona']['presentation']['hardwareConcurrency']=2
            controller=object.__new__(ChromiumController)
            controller.ready={'identityPrivacyVersion':1,'supportedPersonaOptions':['canvas','blockWebGPUReadback','navigator','language','timezone','display']}
            writes=[];controller._request=lambda *args,**kwargs:writes.append((args,kwargs))
            with self.assertRaisesRegex(RuntimeError,'processor count'):controller._apply(config)
            self.assertEqual(writes,[])

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
