"""A last-used user profile cannot become the unconfigured bootstrap profile."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from engines.shared.persona_config import PersonaStore
from test_offscreen_rendering import Windowless


@unittest.skipUnless(os.environ.get('CLOAKFOX_CHROMIUM_BIN'), 'Set CLOAKFOX_CHROMIUM_BIN')
class SnapshotBootstrap(unittest.TestCase):
    def test_last_used_container_stays_unopened_until_its_new_snapshot_is_applied(self):
        binary=Path(os.environ['CLOAKFOX_CHROMIUM_BIN'])
        with tempfile.TemporaryDirectory(prefix='cloakfox-bootstrap-') as folder:
            root=Path(folder);config=PersonaStore(root/'personas').get('1','chromium')
            app=Windowless(binary,root)
            try:
                self.assertTrue(app.rpc('applyConfig',config=config)['ok'])
                app.open('1','about:blank',configRevision=1)
            finally:app.close()
            local=root/'containers/Local State'
            state=json.loads(local.read_text());state.setdefault('profile',{})['last_used']='1'
            state['profile']['last_active_profiles']=['1'];local.write_text(json.dumps(state))
            changed=copy.deepcopy(config);changed['enabled']=False;changed['revision']=2
            app=Windowless(binary,root)
            try:
                ack=app.rpc('applyConfig',config=changed)
                self.assertTrue(ack['ok'],ack)
                self.assertEqual(ack['initialSnapshotStatus'],{'schemaVersion':1,
                    'appliedBeforeServices':True,'container':'1','private':False,'revision':2})
                self.assertNotIn(changed['persona']['seed'],json.dumps(ack))
                browser=app.open('1','about:blank',configRevision=2)
                self.assertEqual(app.evaluate(browser,'location.href'),'about:blank')
            finally:app.close()
