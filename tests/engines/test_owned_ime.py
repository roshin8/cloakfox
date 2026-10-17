"""Native renderer field/document ownership for offscreen input composition.

No page wrappers. Values and input events are observed only in owned fixtures.
"""
from collections import deque
import time
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from engines.shared.persona_config import PersonaStore
from test_offscreen_rendering import Fixture, Windowless


class StateEventsWindowless(Windowless):
    """Retain bounded unsolicited state events while waiting for RPC replies."""
    def __init__(self,*args,**kwargs):
        self.state_events=deque(maxlen=64)
        super().__init__(*args,**kwargs)

    def wait(self,match,timeout=30,allow_crash=False):
        for packet in list(self.state_events):
            if match(packet):
                self.state_events.remove(packet)
                return packet
        def capture(packet):
            if match(packet):return True
            if packet.get('event')=='ownedImeInvalidated':self.state_events.append(packet)
            return False
        return super().wait(capture,timeout,allow_crash)


@unittest.skipUnless(os.environ.get('CLOAKFOX_CHROMIUM_BIN'),'Set CLOAKFOX_CHROMIUM_BIN')
class OwnedIme(unittest.TestCase):
    def test_composition_is_bound_to_the_live_document_and_field(self):
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Fixture)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with tempfile.TemporaryDirectory(prefix='cloakfox-owned-ime-') as folder:
                root=Path(folder);app=Windowless(Path(os.environ['CLOAKFOX_CHROMIUM_BIN']),root)
                try:
                    self.assertEqual(app.ready.get('ownedImeVersion'),1,'Owned native renderer IME hook is not built')
                    config=PersonaStore(root/'personas').get('1','chromium')
                    self.assertTrue(app.rpc('applyConfig',config=config)['ok'])
                    url=f'http://127.0.0.1:{server.server_port}/'
                    browser=app.open('1',url,configRevision=1)
                    app.evaluate(browser,"field.focus();window.imeEvents=[];for(const type of ['compositionstart','compositionupdate','compositionend','input'])field.addEventListener(type,e=>imeEvents.push([e.type,e.isComposing===true]));true")
                    def state():
                        deadline=time.monotonic()+2
                        while True:
                            result=app.rpc('textInputState',browser=browser,configRevision=1)
                            self.assertTrue(result['ok'],result);value=result.get('state')
                            if value and value['editable']:break
                            self.assertLess(time.monotonic(),deadline,'Focused native editing state did not settle')
                            time.sleep(.01)
                        self.assertEqual(set(value),{'field','editable','password','selection','composition','caret'})
                        self.assertNotIn(config['persona']['seed'],json.dumps(value))
                        return value
                    first=state();self.assertTrue(first['editable']);self.assertFalse(first['password'])
                    self.assertEqual(set(first['field']),{'document','node'})
                    self.assertEqual(first['selection'],[0,0]);self.assertEqual(len(first['caret']),4)
                    def ime(action,field=None,**values):
                        return app.rpc('input',browser=browser,configRevision=1,kind='ownedIme',action=action,
                                       field=first['field'] if field is None else field,**values)
                    def wait(expression, expected):
                        encoded=json.dumps(expected)
                        result=app.evaluate(browser,"new Promise(resolve=>{const end=Date.now()+2000;const check=()=>{const value=("+expression+");JSON.stringify(value)===JSON.stringify("+encoded+")||Date.now()>end?resolve(value):setTimeout(check,10)};check()})")
                        self.assertEqual(result,expected)
                    reply=ime('set',text='に',selectionStart=1,selectionEnd=1)
                    self.assertTrue(reply['ok'],reply);self.assertTrue(reply['applied'],reply)
                    wait('field.value','に')
                    self.assertTrue(ime('set',text='日本',selectionStart=2,selectionEnd=2)['applied'])
                    wait('field.value','日本')
                    self.assertTrue(ime('commit',text='日本語 😀')['applied'])
                    wait('field.value','日本語 😀')
                    events=app.evaluate(browser,'imeEvents')
                    self.assertIn(['compositionstart',False],events);self.assertIn(['compositionend',False],events)
                    self.assertTrue(any(e==['input',True] for e in events),events)
                    # A DOM focus change happens before the queued commit is
                    # delivered. The old field token must never insert into B.
                    app.evaluate(browser,"const other=document.createElement('input');other.id='other';document.body.append(other);other.focus();true")
                    rejected=ime('commit',text='WRONG')
                    self.assertTrue(rejected['ok'],rejected);self.assertFalse(rejected['applied'],rejected)
                    self.assertEqual(app.evaluate(browser,'[field.value,other.value]'),['日本語 😀',''])
                    second=state();self.assertNotEqual(first['field'],second['field'])
                    self.assertTrue(ime('set',second['field'],text='é',selectionStart=1,selectionEnd=1)['applied'])
                    self.assertTrue(ime('cancel',second['field'])['applied']);wait('other.value','')
                    self.assertTrue(ime('set',second['field'],text='café',selectionStart=4,selectionEnd=4)['applied'])
                    self.assertTrue(ime('finish',second['field'])['applied']);wait('other.value','café')
                    # A navigation can reuse a frame and element ID; document
                    # ownership remains independent of both.
                    self.assertTrue(app.rpc('navigate',browser=browser,url=url)['ok'])
                    app.evaluate(browser,'field.focus();true')
                    third=state();self.assertNotEqual(first['field']['document'],third['field']['document'])
                    self.assertFalse(ime('commit',text='STALE')['applied'])
                    self.assertEqual(app.evaluate(browser,'field.value'),'')
                    for values in ({'action':'set','text':'x','selectionStart':True,'selectionEnd':1},
                                   {'action':'set','text':'x','selectionStart':0,'selectionEnd':2},
                                   {'action':'commit','text':'x'*4097},{'action':'commit','text':'\0'},
                                   {'action':'cancel','text':'extra'},{'action':'unknown'}):
                        action=values['action'];payload={k:v for k,v in values.items() if k!='action'}
                        self.assertFalse(ime(action,third['field'],**payload)['ok'])
                    self.assertEqual(app.evaluate(browser,'field.value'),'')
                finally:app.close()
        finally:server.shutdown();server.server_close()

    def test_same_field_password_transition_invalidates_cached_input_state(self):
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Fixture)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with tempfile.TemporaryDirectory(prefix='cloakfox-owned-ime-state-') as folder:
                root=Path(folder);app=StateEventsWindowless(Path(os.environ['CLOAKFOX_CHROMIUM_BIN']),root)
                try:
                    self.assertEqual(app.ready.get('ownedImeStateVersion'),1,'Native input-state invalidation hook is not built')
                    config=PersonaStore(root/'personas').get('1','chromium')
                    self.assertTrue(app.rpc('applyConfig',config=config)['ok'])
                    browser=app.open('1',f'http://127.0.0.1:{server.server_port}/',configRevision=1)
                    app.evaluate(browser,'field.focus();true')
                    before=app.rpc('textInputState',browser=browser,configRevision=1)['state']
                    self.assertFalse(before['password'])
                    # Mutation occurs after evaluate replies: no focus event,
                    # input request or polling query may discover it for us.
                    app.evaluate(browser,"setTimeout(()=>{field.type='password'},100);true")
                    deadline=time.monotonic()+3
                    while True:
                        changed=app.wait(lambda p:p.get('event')=='ownedImeInvalidated' and p.get('browser')==browser,
                                         timeout=max(.01,deadline-time.monotonic()))
                        self.assertEqual(changed['configRevision'],1)
                        password=app.rpc('textInputState',browser=browser,configRevision=1).get('state')
                        if password and password['password']:break
                        self.assertLess(time.monotonic(),deadline,'No native password-type invalidation arrived')
                    self.assertEqual(password['field'],before['field'])
                    self.assertFalse(app.rpc('input',browser=browser,configRevision=1,kind='ownedIme',action='set',
                        field=password['field'],text='secret',selectionStart=6,selectionEnd=6)['applied'])
                    self.assertEqual(app.evaluate(browser,'field.value'),'')
                finally:app.close()
        finally:server.shutdown();server.server_close()

    def test_delayed_frame_reply_cannot_replace_cross_origin_password_metadata(self):
        probe=Path(__file__).with_name('probe_owned_ime_state_order.py')
        result=subprocess.run([sys.executable,str(probe),os.environ['CLOAKFOX_CHROMIUM_BIN']],
                              capture_output=True,text=True,timeout=65)
        self.assertEqual(result.returncode,0,result.stderr[-5000:])
