"""Native context snapshot acceptance before profile services initialize."""
import copy
import http.server
import json
import os
import shutil
import subprocess
from pathlib import Path
import tempfile
import threading
import unittest

from engines.shared.persona_config import PersonaStore
from probe_cef_isolation import Companion
import test_identity_privacy as identity
from test_canvas_privacy import READ as CANVAS_READ


@unittest.skipUnless(os.environ.get('CLOAKFOX_CHROMIUM_BIN'),'Set CLOAKFOX_CHROMIUM_BIN')
class InitialSnapshotPrivacy(unittest.TestCase):
    def test_new_sdk_refuses_an_older_embedded_framework(self):
        legacy=os.environ.get('CLOAKFOX_UNPATCHED_CHROMIUM_BIN')
        if not legacy:self.skipTest('Set CLOAKFOX_UNPATCHED_CHROMIUM_BIN for SDK/framework mismatch acceptance')
        binary=Path(os.environ['CLOAKFOX_CHROMIUM_BIN']).resolve()
        source_bundle=binary.parents[2]
        legacy_framework=Path(legacy).resolve().parents[1]/'Frameworks/Chromium Embedded Framework.framework'
        # Same-volume APFS clone retains every helper/resource; only this
        # disposable app's framework is deliberately replaced.
        with tempfile.TemporaryDirectory(prefix='cloakfox-sdk-mismatch-',dir=source_bundle.parent) as folder:
            root=Path(folder);bundle=root/'Mismatch.app'
            subprocess.run(['cp','-cR',str(source_bundle),str(bundle)],check=True,capture_output=True)
            framework=bundle/'Contents/Frameworks/Chromium Embedded Framework.framework'
            shutil.rmtree(framework)
            subprocess.run(['cp','-cR',str(legacy_framework),str(framework)],check=True,capture_output=True)
            profile=root/'profile';profile.mkdir(mode=0o700)
            result=subprocess.run([str(bundle/'Contents/MacOS'/binary.name),'--profile-root='+str(profile),'--enable-probe','--test-keychain'],input='',capture_output=True,text=True,timeout=20)
            self.assertNotEqual(result.returncode,0,result.stderr)
            self.assertNotIn('"event":"ready"',result.stdout)
            # The generated loader can encounter either required native API first.
            # Both failures must occur before ready/profile creation.
            self.assertRegex(result.stderr,r'dlsym[^\n]*(?:initial_privacy_status|cef_get_owned_input_state)')
            self.assertIn('Failed to load the CEF framework.',result.stderr)
            self.assertFalse(any(profile.iterdir()),'Mismatched framework created profile state')

    def test_native_snapshot_precedes_services_and_survives_restart(self):
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),identity.Fixture)
        server.headers_by_path={}
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with tempfile.TemporaryDirectory(prefix='cloakfox-initial-snapshot-') as folder:
                root=Path(folder);store=PersonaStore(root/'personas')
                app=Companion(Path(os.environ['CLOAKFOX_CHROMIUM_BIN']),root)
                try:
                    self.assertEqual(app.ready.get('initialSnapshotVersion'),1,'Initial native snapshot hook is not built')
                    config=store.get('1','chromium')
                    config['persona']['presentation']=copy.deepcopy(identity.PRESET)
                    config['persona']['presentation']['hardwareConcurrency']=12
                    pixels=[]
                    for private,container in ((False,'1'),(True,'2')):
                        snapshot=store.get(container,'chromium',private=private)
                        snapshot['persona']['presentation']=copy.deepcopy(config['persona']['presentation'])
                        ack=app.rpc('applyConfig',config=snapshot)
                        self.assertTrue(ack['ok'],ack)
                        self.assertEqual(ack['initialSnapshotStatus'],{'schemaVersion':1,
                            'appliedBeforeServices':True,'container':container,'private':private,'revision':1})
                        self.assertNotIn(snapshot['persona']['seed'],json.dumps(ack))
                        browser=app.open(container,f'http://127.0.0.1:{server.server_port}/',private=private,configRevision=1)
                        first=app.evaluate(browser,'firstIdentity')
                        self.assertEqual(first['cpu'],12);self.assertEqual(first['languages'],['fr-FR','fr'])
                        self.assertEqual(first['timezone'],'Europe/Paris')
                        pixels.append(app.evaluate(browser,CANVAS_READ))
                    self.assertNotEqual(pixels[0],pixels[1],'Persistent/private owners shared the canvas identity')
                    app.close();app=Companion(Path(os.environ['CLOAKFOX_CHROMIUM_BIN']),root)
                    config['enabled']=False;config['revision']=2
                    ack=app.rpc('applyConfig',config=config);self.assertTrue(ack['ok'],ack)
                    self.assertEqual(ack['initialSnapshotStatus'],{'schemaVersion':1,
                        'appliedBeforeServices':True,'container':'1','private':False,'revision':2})
                    browser=app.open('1',f'http://127.0.0.1:{server.server_port}/',configRevision=2)
                    baseline=store.get('99','chromium');baseline['enabled']=False
                    self.assertTrue(app.rpc('applyConfig',config=baseline)['ok'])
                    other=app.open('99',f'http://127.0.0.1:{server.server_port}/',configRevision=1)
                    self.assertEqual(app.evaluate(browser,'firstIdentity'),app.evaluate(other,'firstIdentity'))
                finally:app.close()
        finally:server.shutdown();server.server_close()
