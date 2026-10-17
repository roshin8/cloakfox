"""Owned native editing keys; browser shortcuts are outside this protocol."""
import http.server
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest

from engines.shared.persona_config import PersonaStore
from test_offscreen_rendering import Fixture, Windowless


@unittest.skipUnless(os.environ.get('CLOAKFOX_CHROMIUM_BIN'), 'Set CLOAKFOX_CHROMIUM_BIN')
class EditingKeyboard(unittest.TestCase):
    def test_committed_unicode_preserves_text_and_rejects_invalid_payloads(self):
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Fixture)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with tempfile.TemporaryDirectory(prefix='cloakfox-unicode-') as folder:
                root=Path(folder);app=Windowless(Path(os.environ['CLOAKFOX_CHROMIUM_BIN']),root)
                try:
                    config=PersonaStore(root/'personas').get('1','chromium')
                    self.assertTrue(app.rpc('applyConfig',config=config)['ok'])
                    browser=app.open('1',f'http://127.0.0.1:{server.server_port}/',configRevision=config['revision'])
                    app.evaluate(browser,'field.focus();true')
                    text='café 日本語 😀'
                    reply=app.rpc('input',browser=browser,configRevision=config['revision'],kind='commitText',text=text)
                    self.assertTrue(reply['ok'],reply)
                    expression='new Promise(resolve=>{const end=Date.now()+2000;const check=()=>field.value==='+json.dumps(text)+'||Date.now()>end?resolve(field.value):setTimeout(check,10);check()})'
                    self.assertEqual(app.evaluate(browser,expression),text)
                    for bad in ('',True,None,[], 'x'*4097, '😀'*2049, '\0', '\x01'):
                        self.assertFalse(app.rpc('input',browser=browser,configRevision=config['revision'],kind='commitText',text=bad)['ok'])
                    for extra in ({'character':65},{'keyCode':8},{'shift':False},{'x':0},{'deltaX':0}):
                        self.assertFalse(app.rpc('input',browser=browser,configRevision=config['revision'],kind='commitText',text='X',**extra)['ok'])
                    self.assertFalse(app.rpc('input',browser=browser,configRevision=config['revision']+1,kind='commitText',text='X')['ok'])
                    self.assertFalse(app.rpc('input',browser=browser,configRevision=config['revision'],kind='char',character=88,text='X')['ok'])
                    self.assertEqual(app.evaluate(browser,'field.value'),text)
                finally:app.close()
        finally:server.shutdown();server.server_close()

    def test_editing_keys_preserve_selection_and_reject_invalid_requests(self):
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory(prefix='cloakfox-editing-') as folder:
                root = Path(folder)
                app = Windowless(Path(os.environ['CLOAKFOX_CHROMIUM_BIN']), root)
                try:
                    config = PersonaStore(root / 'personas').get('1', 'chromium')
                    self.assertTrue(app.rpc('applyConfig', config=config)['ok'])
                    browser = app.open('1', f'http://127.0.0.1:{server.server_port}/', configRevision=config['revision'])
                    app.wait_frame(browser)
                    app.evaluate(browser, "field.value='ABC';field.focus();field.setSelectionRange(3,3);true")
                    def key(code, shift=False, **extra):
                        return app.rpc('input', browser=browser, configRevision=config['revision'],
                                       kind='editKey', keyCode=code, shift=shift, **extra)
                    reply = key(37, True)
                    self.assertTrue(reply['ok'], reply)
                    selected = app.evaluate(browser, "new Promise(r=>{const end=Date.now()+2000;const check=()=>field.selectionStart===2||Date.now()>end?r([field.selectionStart,field.selectionEnd]):setTimeout(check,10);check()})")
                    self.assertEqual(selected, [2, 3])
                    self.assertTrue(key(8)['ok'])
                    self.assertEqual(app.evaluate(browser, "new Promise(r=>{const end=Date.now()+2000;const check=()=>field.value==='AB'||Date.now()>end?r(field.value):setTimeout(check,10);check()})"), 'AB')
                    for code, shift in ((True, False), (65, False), (-1, False), (37, 1), (37, 'false')):
                        self.assertFalse(key(code, shift)['ok'])
                    self.assertFalse(key(37, character=65)['ok'])
                    self.assertFalse(app.rpc('input', browser=browser, configRevision=config['revision'],
                                             kind='char', character=88, keyCode=8, shift=False)['ok'])
                    self.assertFalse(app.rpc('input', browser=browser, configRevision=config['revision'],
                                             kind='mouseDown', x=8, y=8, keyCode=8, shift=False)['ok'])
                    self.assertFalse(app.rpc('input', browser=browser, configRevision=config['revision'] + 1,
                                             kind='editKey', keyCode=8, shift=False)['ok'])
                    self.assertEqual(app.evaluate(browser, 'field.value'), 'AB')
                    def wait_for(expression, expected):
                        encoded = json.dumps(expected)
                        actual = app.evaluate(browser, "new Promise(r=>{const end=Date.now()+2000;const check=()=>{const value=(" + expression + ");JSON.stringify(value)===" + json.dumps(encoded) + "||Date.now()>end?r(value):setTimeout(check,10)};check()})")
                        self.assertEqual(actual, expected)
                    app.evaluate(browser, "field.setSelectionRange(1,1);true")
                    self.assertTrue(key(39)['ok'])
                    wait_for('[field.selectionStart,field.selectionEnd]', [2, 2])
                    self.assertTrue(key(37)['ok'])
                    wait_for('field.selectionStart', 1)
                    self.assertTrue(key(46)['ok'])
                    wait_for('field.value', 'A')
                    app.evaluate(browser, "const area=document.createElement('textarea');area.id='area';document.body.append(area);true")
                    self.assertTrue(key(9)['ok'])
                    wait_for('document.activeElement.id', 'area')
                    self.assertTrue(key(13)['ok'])
                    wait_for('area.value', '\n')
                    self.assertTrue(key(9, True)['ok'])
                    wait_for('document.activeElement.id', 'field')
                finally:
                    app.close()
        finally:
            server.shutdown()
            server.server_close()
