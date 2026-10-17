"""Real CEF config acknowledgement, seed ownership and rejection behavior."""
import copy
import http.server
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engines.shared.persona_config import PersonaStore
from probe_cef_isolation import Companion
from test_canvas_privacy import DRAW, READ
from test_worker_privacy import Fixture as WorkerFixture, WORKER_READ

class Fixture(WorkerFixture):
    def do_GET(self):
        if self.path == "/worker.js":
            body = DRAW + "const first=pixels(draw(new OffscreenCanvas(32,24)));onmessage=()=>postMessage(first);"
        elif self.path == "/":
            body = "<!doctype html><script>" + DRAW + "globalThis.initialPixels=pixels(draw(document.createElement('canvas')));</script>"
        else:
            return super().do_GET()
        raw = body.encode(); self.send_response(200)
        self.send_header("Content-Type", "application/javascript" if self.path.endswith(".js") else "text/html")
        self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

class PersonaBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('CLOAKFOX_CHROMIUM_BIN'):
            raise unittest.SkipTest('Set CLOAKFOX_CHROMIUM_BIN for native config tests')
        cls.binary = Path(os.environ['CLOAKFOX_CHROMIUM_BIN'])
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()
    def setUp(self):
        self.root = tempfile.TemporaryDirectory(prefix='cloakfox-config-')
        self.store = PersonaStore(Path(self.root.name) / 'personas')
        self.app = Companion(self.binary, Path(self.root.name))
    def tearDown(self):
        self.app.close(); self.root.cleanup()
    def apply(self, snapshot):
        result = self.app.rpc('applyConfig', config=snapshot)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['event'], 'configApplied')
        self.assertEqual(result['configRevision'], snapshot['revision'])
        self.assertNotIn(snapshot['persona']['seed'], str(result))
        return result
    def open(self, snapshot):
        result = self.app.rpc('open', container=snapshot['containerId'], private=snapshot['private'],
                              configRevision=snapshot['revision'], url=self.url)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['configRevision'], snapshot['revision'])
        browser = result['browser']
        for _ in range(100):
            if self.app.evaluate(browser, 'document.readyState') == 'complete': break
            __import__('time').sleep(.03)
        return browser

    def test_complete_policy_capabilities_do_not_claim_partial_hooks_as_parity(self):
        from engines.shared.engine_policy import POLICY_GROUPS
        self.assertEqual(self.app.ready.get('requiredPolicySchemaVersion'),2)
        self.assertEqual(self.app.ready.get('nativePolicyGroups'),dict.fromkeys(POLICY_GROUPS,0))
        self.assertIs(self.app.ready.get('releaseEligible'),False)
        # The v1 development protocol is not silently relabeled as schema2.
        self.assertEqual(self.app.ready.get('configSchemaVersion'),1)

    def test_applied_seed_reaches_document_and_worker_before_script(self):
        self.assertEqual(self.app.ready.get('configSchemaVersion'), 1)
        a = self.store.get('11', 'chromium'); self.apply(a); first = self.open(a)
        b = self.store.get('12', 'chromium'); b['persona']['seed'] = a['persona']['seed']
        self.apply(b); second = self.open(b)
        pixels = self.app.evaluate(first, READ)
        self.assertEqual(pixels, self.app.evaluate(second, READ), 'Snapshot seed not used by native canvas')
        self.assertEqual(pixels, self.app.evaluate(first, 'initialPixels'))
        self.assertEqual(pixels, self.app.evaluate(first, "new Promise(r=>{const f=document.createElement('iframe');f.src='/';f.onload=()=>r(f.contentWindow.initialPixels);document.body.append(f)})"))
        for kind in ('shared', 'service'):
            result = self.app.evaluate(first, '(async()=>{' + WORKER_READ + 'return workerRead("' + kind + '")})()')
            self.assertEqual(pixels, result['first'], kind)
            self.assertEqual(pixels, result['current'], kind)
        self.assertEqual(pixels, self.app.evaluate(first, "new Promise(r=>{const w=new Worker('/worker.js');w.onmessage=e=>{w.terminate();r(e.data)};w.postMessage(1)})"))
        again = self.app.rpc('applyConfig', config=a)
        self.assertTrue(again['ok'], again)
        missing = self.app.rpc('open', container='11', url=self.url)
        self.assertFalse(missing['ok'], missing)
        wrong = self.app.rpc('open', container='11', configRevision=2, url=self.url)
        self.assertFalse(wrong['ok'], wrong)
        mixed = self.app.rpc('open', container='11', configRevision=1, privacy={'canvas': True}, url=self.url)
        self.assertFalse(mixed['ok'], mixed)

    def test_rejections_do_not_mutate_accepted_snapshot(self):
        a = self.store.get('11', 'chromium')
        self.assertFalse(self.app.rpc('open', container='11', configRevision=1, url=self.url)['ok'])
        self.apply(a)
        for mutate in (lambda v: v.update(schemaVersion=2), lambda v: v.update(engine='gecko'),
                       lambda v: v.update(revision=0), lambda v: v.update(revision=True),
                       lambda v: v['persona'].update(seed='X'*64),
                       lambda v: v['persona']['overrides'].update(unsupportedFuture=True),
                       lambda v: v['persona']['options'].update(canvas=1),
                       lambda v: v.update(enabled=False, revision=2)):
            bad = copy.deepcopy(a); mutate(bad)
            result = self.app.rpc('applyConfig', config=bad)
            self.assertFalse(result['ok'], result)
        browser = self.open(a)
        self.assertIsInstance(self.app.evaluate(browser, READ), list)
        stale = copy.deepcopy(a); stale['persona']['seed'] = '0'*64
        self.assertFalse(self.app.rpc('applyConfig', config=stale)['ok'])

    def test_master_switch_overrides_and_persistent_restart_generation(self):
        a = self.store.get('11', 'chromium'); self.apply(a)
        first = self.app.evaluate(self.open(a), READ)
        disabled = self.store.get('12', 'chromium'); disabled['enabled'] = False
        disabled['persona']['overrides']['blockWebGPUReadback'] = True
        result = self.apply(disabled)
        self.assertFalse(result['canvasEnabled']); self.assertFalse(result['webgpuReadbackBlocked'])
        raw = self.app.evaluate(self.open(disabled), READ)
        self.assertNotEqual(first, raw)
        overridden = self.store.get('13', 'chromium'); overridden['persona']['overrides']['canvas'] = False
        self.apply(overridden)
        self.assertEqual(self.app.evaluate(self.open(overridden), READ), raw)
        self.app.close(); self.app = Companion(self.binary, Path(self.root.name))
        self.apply(self.store.get('11', 'chromium'))
        self.assertEqual(self.app.evaluate(self.open(a), READ), first)
        self.app.close(); self.app = Companion(self.binary, Path(self.root.name))
        regenerated = self.store.regenerate(a)
        self.apply(regenerated)
        self.assertNotEqual(self.app.evaluate(self.open(regenerated), READ), first)

    def test_private_ownership_never_uses_persistent_config(self):
        a = self.store.get('11', 'chromium', private=True); self.apply(a)
        first = self.open(a)
        self.assertTrue(self.app.evaluate(first, 'typeof navigator.userAgent === "string"'))
        public = self.store.get('11', 'chromium'); self.apply(public)
        second = self.open(public)
        self.assertNotEqual(self.app.evaluate(first, READ), self.app.evaluate(second, READ))

    def test_private_close_discards_config_and_accepts_new_session(self):
        keep = self.store.get('12', 'chromium'); self.apply(keep); self.open(keep)
        a = self.store.get('11', 'chromium', private=True); self.apply(a)
        browser = self.open(a); first = self.app.evaluate(browser, READ)
        self.app.rpc('close', browser=browser)
        self.app.wait(lambda v: v.get('event') == 'closed' and v.get('browser') == browser)
        self.store.forget_private('11', 'chromium')
        fresh = self.store.get('11', 'chromium', private=True); self.apply(fresh)
        self.assertNotEqual(self.app.evaluate(self.open(fresh), READ), first)

    def test_retired_private_snapshot_cannot_be_replayed_in_new_context(self):
        keep = self.store.get('12', 'chromium'); self.apply(keep); self.open(keep)
        private = self.store.get('11', 'chromium', private=True); self.apply(private)
        browser = self.open(private)
        self.app.rpc('close', browser=browser)
        self.app.wait(lambda v: v.get('event') == 'closed' and v.get('browser') == browser)
        result = self.app.rpc('applyConfig', config=private)
        self.assertFalse(result['ok'], 'Retired private seed was accepted again')

    def test_private_popup_holds_config_until_actual_context_discard(self):
        from test_popup_isolation import PopupIsolation
        keep = self.store.get('12', 'chromium'); self.apply(keep); self.open(keep)
        private = self.store.get('11', 'chromium', private=True); self.apply(private)
        browser = self.open(private)
        popup = PopupIsolation.popup(self, browser)
        self.assertEqual(popup['configRevision'], private['revision'])
        self.app.rpc('close', browser=browser)
        self.app.wait(lambda v: v.get('event') == 'closed' and v.get('browser') == browser)
        self.assertTrue(self.app.rpc('applyConfig', config=private)['ok'], 'Popup lost its live config')
        self.app.rpc('close', browser=popup['browser'])
        discarded = self.app.wait(lambda v: v.get('event') == 'configDiscarded')
        self.assertEqual(discarded['container'], private['containerId'])
        self.app.wait(lambda v: v.get('event') == 'closed' and v.get('browser') == popup['browser'])
        self.assertFalse(self.app.rpc('applyConfig', config=private)['ok'])

    def test_unpatched_sdk_rejects_portable_persona_options(self):
        binary = os.environ.get('CLOAKFOX_UNPATCHED_CHROMIUM_BIN')
        if not binary: self.skipTest('Set CLOAKFOX_UNPATCHED_CHROMIUM_BIN for negative SDK check')
        with tempfile.TemporaryDirectory(prefix='cloakfox-legacy-config-') as folder:
            legacy = Companion(Path(binary), Path(folder))
            try:
                self.assertEqual(legacy.ready['supportedPersonaOptions'], [])
                config = self.store.get('11', 'chromium')
                result = legacy.rpc('applyConfig', config=config)
                self.assertFalse(result['ok'], result)
                self.assertIn('does not support', result['error'])
            finally: legacy.close()
