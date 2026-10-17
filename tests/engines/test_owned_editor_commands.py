"""Native editor commands use the owned browser, without clipboard access."""
import http.server
import os
from pathlib import Path
import tempfile
import threading
import unittest
from engines.shared.persona_config import PersonaStore
from test_offscreen_rendering import Fixture, Windowless


@unittest.skipUnless(os.environ.get('CLOAKFOX_CHROMIUM_BIN'), 'Set CLOAKFOX_CHROMIUM_BIN')
class OwnedEditorCommands(unittest.TestCase):
    def test_select_all_targets_the_focused_editor_without_changing_other_browsers(self):
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Fixture)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with tempfile.TemporaryDirectory(prefix='cloakfox-editor-command-') as folder:
                root=Path(folder);app=Windowless(Path(os.environ['CLOAKFOX_CHROMIUM_BIN']),root)
                try:
                    config=PersonaStore(root/'personas').get('1','chromium')
                    self.assertTrue(app.rpc('applyConfig',config=config)['ok'])
                    url=f'http://127.0.0.1:{server.server_port}/'
                    first=app.open('1',url,configRevision=1)
                    other=app.open('1',url,configRevision=1)
                    for browser in (first,other):
                        app.evaluate(browser,"field.value='owned editor';field.focus();field.setSelectionRange(3,3);true")
                    for extra in ({'text':'private'}, {'character':65}, {'x':0}, {'keyCode':65}, {'shift':False}):
                        self.assertFalse(app.rpc('input',browser=first,configRevision=1,kind='selectAll',**extra)['ok'])
                    self.assertEqual(app.evaluate(first,'[field.selectionStart,field.selectionEnd]'),[3,3])
                    self.assertFalse(app.rpc('input',browser=first,configRevision=2,kind='selectAll')['ok'])
                    reply=app.rpc('input',browser=first,configRevision=1,kind='selectAll')
                    self.assertTrue(reply['ok'],reply)
                    selected=app.evaluate(first,"new Promise(resolve=>{const end=Date.now()+2000;const check=()=>{field.selectionEnd===12||Date.now()>end?resolve([field.selectionStart,field.selectionEnd]):setTimeout(check,10)};check()})")
                    self.assertEqual(selected,[0,12])
                    self.assertEqual(app.evaluate(other,'[field.value,field.selectionStart,field.selectionEnd]'),['owned editor',3,3])
                finally:app.close()
        finally:server.shutdown();server.server_close()
