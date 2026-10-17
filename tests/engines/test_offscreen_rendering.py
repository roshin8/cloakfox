"""Native windowless rendering feasibility with versioned privacy ownership.

Owned loopback fixture and disposable profile only. This is not same-window UI
acceptance or privacy-parity certification; the native Gecko host is separate.
"""
import http.server
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from engines.shared.persona_config import PersonaStore
from probe_cef_isolation import Companion
from test_canvas_privacy import READ

class Fixture(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body=b'<!doctype html><style>html,body{margin:0;background:rgb(13,37,91)}body{height:3000px}</style><title>Owned offscreen fixture</title><input id="field">'
        self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass

class Windowless(Companion):
    def __init__(self,binary,root,shared=False):
        self.log=tempfile.TemporaryFile(mode='w+')
        arguments=[str(binary),'--profile-root='+str(root),'--enable-probe','--test-keychain','--windowless']
        if shared:arguments.append('--shared-texture')
        self.process=subprocess.Popen(arguments,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,bufsize=1)
        self.messages=queue.Queue();self.serial=0
        def reader():
            for line in self.process.stdout:
                try:self.messages.put(json.loads(line))
                except json.JSONDecodeError:self.messages.put({'event':'bad-output','line':line})
            self.messages.put({'event':'eof'})
        threading.Thread(target=reader,daemon=True).start()
        try:self.ready=self.wait(lambda x:x.get('event')=='ready')
        except BaseException:
            self.process.wait(timeout=5);self.process.stdin.close();self.process.stdout.close();self.log.close();raise

    def wait_frame(self,browser,size=None):
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            result=self.rpc('frame',browser=browser)
            if result.get('ok') and result.get('cornerBGRA')==[91,37,13,255] and (size is None or result.get('size')==size):return result
            time.sleep(.025)
        raise AssertionError('Owned offscreen paint did not arrive: '+str(result))

@unittest.skipUnless(os.environ.get('CLOAKFOX_CHROMIUM_BIN'),'Set CLOAKFOX_CHROMIUM_BIN for native windowless tests')
class OffscreenRendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary=Path(os.environ['CLOAKFOX_CHROMIUM_BIN'])
        cls.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Fixture)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}/'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def test_owned_pixels_render_without_top_level_cef_window(self):
        with tempfile.TemporaryDirectory(prefix='cloakfox-offscreen-') as folder:
            root=Path(folder);store=PersonaStore(root/'personas');app=Windowless(self.binary,root)
            try:
                self.assertIs(app.ready.get('windowless'),True)
                config=store.get('1','chromium')
                applied=app.rpc('applyConfig',config=config);self.assertTrue(applied['ok'],applied)
                browser=app.open('1',self.url,configRevision=config['revision'])
                actual=app.evaluate(browser,"({ua:navigator.userAgent,cpu:navigator.hardwareConcurrency,language:navigator.language})")
                self.assertIn('Chrome/154.',actual['ua'])
                self.assertEqual(actual['cpu'],config['persona']['presentation']['hardwareConcurrency'])
                self.assertEqual(actual['language'],config['persona']['presentation']['languages'][0])
                # A native paint callback is asynchronous. Poll the bounded frame
                # state until the fixture's background reaches its bottom corner.
                state=app.wait_frame(browser)
                self.assertEqual(state['size'],[1000,720])
                self.assertEqual(state['cornerBGRA'],[91,37,13,255])
                self.assertEqual(state['configRevision'],config['revision'])
                self.assertEqual(state['container'],'1')
                self.assertIs(state['private'],False)
                self.assertIs(state['topLevelWindow'],False)
                self.assertNotIn('handle',state)
                self.assertNotIn('pixels',state)
            finally:app.close()
    def test_accelerated_surface_is_read_from_owned_callback_copy(self):
        with tempfile.TemporaryDirectory(prefix='cloakfox-offscreen-gpu-') as folder:
            root=Path(folder);store=PersonaStore(root/'personas');app=Windowless(self.binary,root,shared=True)
            try:
                config=store.get('1','chromium');applied=app.rpc('applyConfig',config=config)
                self.assertTrue(applied['ok'],applied)
                browser=app.open('1',self.url,configRevision=config['revision'])
                frame=app.wait_frame(browser)
                self.assertEqual(frame['paintSource'],'iosurface')
                self.assertEqual(frame['size'],[1000,720])
                self.assertIs(frame['topLevelWindow'],False)
            finally:app.close()
    def test_viewport_and_input_remain_revision_bound(self):
        with tempfile.TemporaryDirectory(prefix='cloakfox-offscreen-input-') as folder:
            root=Path(folder);store=PersonaStore(root/'personas');app=Windowless(self.binary,root)
            try:
                config=store.get('1','chromium');self.assertTrue(app.rpc('applyConfig',config=config)['ok'])
                browser=app.open('1',self.url,configRevision=config['revision'])
                stale=app.rpc('viewport',browser=browser,configRevision=config['revision']+1,width=640,height=480)
                self.assertFalse(stale['ok'])
                resized=app.rpc('viewport',browser=browser,configRevision=config['revision'],width=640,height=480)
                self.assertTrue(resized['ok'],resized)
                frame=app.wait_frame(browser,size=[640,480]);self.assertEqual(frame['size'],[640,480])
                for kind in ['mouseDown','mouseUp']:
                    self.assertTrue(app.rpc('input',browser=browser,configRevision=config['revision'],kind=kind,x=8,y=8)['ok'])
                rejected=app.rpc('input',browser=browser,configRevision=config['revision']+1,kind='char',character=88)
                self.assertFalse(rejected['ok'])
                typed=app.rpc('input',browser=browser,configRevision=config['revision'],kind='char',character=65)
                self.assertTrue(typed['ok'],typed)
                # Ordered protocol requests reach the same renderer UI queue.
                self.assertEqual(app.evaluate(browser,"document.getElementById('field').value"),'A')
                self.assertFalse(app.rpc('viewport',browser=browser,configRevision=config['revision'],width=-1,height=480)['ok'])
            finally:app.close()
    def test_large_viewport_keeps_unscaled_coordinates(self):
        for shared in (False,True):
            with self.subTest(shared=shared),tempfile.TemporaryDirectory(prefix='cloakfox-offscreen-large-') as folder:
                root=Path(folder);app=Windowless(self.binary,root,shared=shared)
                try:
                    config=PersonaStore(root/'personas').get('1','chromium')
                    self.assertTrue(app.rpc('applyConfig',config=config)['ok'])
                    browser=app.open('1',self.url,configRevision=config['revision'])
                    for width,height in ((2560,1440),(4096,512)):
                        reply=app.rpc('viewport',browser=browser,configRevision=config['revision'],width=width,height=height)
                        self.assertTrue(reply['ok'],reply)
                        self.assertEqual(app.wait_frame(browser,size=[width,height])['size'],[width,height])
                        # Observe layout in the actual renderer, not just its ack.
                        self.assertEqual(app.evaluate(browser,'[innerWidth,innerHeight]'),[width,height])
                    app.evaluate(browser,"Object.assign(document.getElementById('field').style,{position:'absolute',left:'2300px',top:'20px'});true")
                    for kind in ['mouseDown','mouseUp']:
                        self.assertTrue(app.rpc('input',browser=browser,configRevision=config['revision'],kind=kind,x=2308,y=28)['ok'])
                    self.assertTrue(app.rpc('input',browser=browser,configRevision=config['revision'],kind='char',character=66)['ok'])
                    self.assertEqual(app.evaluate(browser,"new Promise(resolve=>{const deadline=Date.now()+2000;const check=()=>document.getElementById('field').value==='B'||Date.now()>deadline?resolve(document.getElementById('field').value):setTimeout(check,10);check()})"),'B')
                    self.assertFalse(app.rpc('viewport',browser=browser,configRevision=config['revision'],width=4097,height=512)['ok'])
                finally:app.close()
    def test_windowless_canvas_policy_keeps_container_isolation(self):
        expected=[]
        for y in range(24):
            for x in range(32):
                expected.extend([141,79,203,255] if 3<=x<20 and 4<=y<13 else [72,108,144,255])
        for shared in (False,True):
            with self.subTest(shared=shared), tempfile.TemporaryDirectory(prefix='cloakfox-offscreen-privacy-') as folder:
                root=Path(folder);store=PersonaStore(root/'personas');app=Windowless(self.binary,root,shared=shared)
                try:
                    browsers=[]
                    for container in ('1','2'):
                        config=store.get(container,'chromium')
                        self.assertTrue(app.rpc('applyConfig',config=config)['ok'])
                        browsers.append(app.open(container,self.url,configRevision=config['revision']))
                    first=app.evaluate(browsers[0],READ)
                    self.assertNotEqual(first,expected,'Windowless mode exposed raw Canvas2D pixels')
                    self.assertEqual(first,app.evaluate(browsers[0],READ))
                    self.assertNotEqual(first,app.evaluate(browsers[1],READ))
                finally:app.close()
    def test_native_scroll_delivery(self):
        with tempfile.TemporaryDirectory(prefix='cloakfox-offscreen-wheel-') as folder:
            root=Path(folder);store=PersonaStore(root/'personas');app=Windowless(self.binary,root)
            try:
                config=store.get('1','chromium');self.assertTrue(app.rpc('applyConfig',config=config)['ok'])
                browser=app.open('1',self.url,configRevision=config['revision'])
                app.wait_frame(browser)
                self.assertEqual(app.evaluate(browser,'window.scrollY'),0)
                scrolled=app.rpc('input',browser=browser,configRevision=config['revision'],
                    kind='wheel',x=300,y=300,deltaX=0,deltaY=-200)
                self.assertTrue(scrolled['ok'],scrolled)
                deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    position=app.evaluate(browser,'window.scrollY')
                    if position>0:break
                    time.sleep(.025)
                self.assertGreater(position,0)
                self.assertFalse(app.rpc('input',browser=browser,configRevision=config['revision'],
                    kind='wheel',x=300,y=300,deltaX=0,deltaY=1000000)['ok'])
            finally:app.close()
    def test_select_popup_is_owned_composited_and_retired(self):
        for shared in (False, True):
            with self.subTest(shared=shared), tempfile.TemporaryDirectory(prefix='cloakfox-popup-paint-') as folder:
                root=Path(folder);app=Windowless(self.binary,root,shared=shared)
                try:
                    store=PersonaStore(root/'personas');config=store.get('1','chromium')
                    self.assertTrue(app.rpc('applyConfig',config=config)['ok'])
                    browser=app.open('1',self.url,configRevision=config['revision']);app.wait_frame(browser)
                    app.evaluate(browser,"field.remove();const pick=document.createElement('select');pick.id='pick';pick.style='position:absolute;left:40px;top:40px;width:200px';pick.innerHTML='<option>First</option><option>Second</option><option>Third</option>';document.body.append(pick);true")
                    def click():
                        for kind in ('mouseDown','mouseUp'):
                            self.assertTrue(app.rpc('input',browser=browser,configRevision=config['revision'],kind=kind,x=80,y=50)['ok'])
                    def popup(painted):
                        deadline=time.monotonic()+5
                        while time.monotonic()<deadline:
                            frame=app.rpc('frame',browser=browser)
                            if frame.get('ok') and frame.get('popupPainted') is painted:return frame
                            time.sleep(.025)
                        self.fail('Popup paint state did not settle: '+str(frame))
                    other=store.get('2','chromium');self.assertTrue(app.rpc('applyConfig',config=other)['ok'])
                    second=app.open('2',self.url,configRevision=other['revision'])
                    app.wait_frame(second)
                    click();frame=popup(True)
                    self.assertGreater(frame['popupRect'][2],0);self.assertGreater(frame['popupRect'][3],0)
                    self.assertFalse(app.wait_frame(second)['popupPainted'])
                    for code in (40,13):
                        self.assertTrue(app.rpc('input',browser=browser,configRevision=config['revision'],kind='editKey',keyCode=code,shift=False)['ok'])
                    popup(False)
                    self.assertEqual(app.evaluate(browser,'pick.selectedIndex'),1)
                    click();popup(True)
                    self.assertTrue(app.rpc('viewport',browser=browser,configRevision=config['revision'],width=640,height=480)['ok'])
                    self.assertFalse(app.wait_frame(browser,size=[640,480])['popupPainted'])
                    self.assertFalse(app.rpc('frame',browser=browser)['topLevelWindow'])
                finally:app.close()
    def test_popup_cannot_escape_unattached_windowless_host(self):
        with tempfile.TemporaryDirectory(prefix='cloakfox-offscreen-popup-') as folder:
            root=Path(folder);store=PersonaStore(root/'personas');app=Windowless(self.binary,root)
            try:
                config=store.get('1','chromium');self.assertTrue(app.rpc('applyConfig',config=config)['ok'])
                browser=app.open('1',self.url,configRevision=config['revision'])
                original=app.wait_frame(browser)
                # Until a trusted Gecko host can allocate a popup slot, a page
                # must not create a separate native window or share paint state.
                opened=app.rpc('cdp',browser=browser,method='Runtime.evaluate',params={
                    'expression':"window.open(location.href + '?popup') === null",
                    'userGesture':True,'returnByValue':True})
                self.assertTrue(opened['ok'],opened)
                self.assertTrue(opened['result']['result']['value'])
                self.assertEqual(app.wait_frame(browser)['size'],original['size'])
                self.assertIs(app.rpc('frame',browser=browser)['topLevelWindow'],False)
            finally:app.close()
    def test_windowless_requires_explicit_development_options(self):
        for flags in (['--windowless'],['--windowless','--enable-probe'],
                      ['--windowless','--test-keychain'],['--shared-texture','--enable-probe','--test-keychain']):
            with self.subTest(flags=flags), tempfile.TemporaryDirectory(prefix='cloakfox-offscreen-flags-') as folder:
                result=subprocess.run([str(self.binary),'--profile-root='+folder,*flags],
                    input='',capture_output=True,text=True,timeout=15)
                self.assertEqual(result.returncode,2,result.stderr)
                self.assertNotIn('"event":"ready"',result.stdout)
    def test_unconfigured_open_is_rejected_before_navigation(self):
        with tempfile.TemporaryDirectory(prefix='cloakfox-offscreen-negative-') as folder:
            app=Windowless(self.binary,Path(folder))
            try:
                result=app.rpc('open',container='1',url=self.url,private=False)
                self.assertFalse(result['ok'],result)
                self.assertIn('config',result['error'].lower())
            finally:app.close()

