"""Actual CEF native paint and input through the authenticated parent boundary."""
import http.server
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from engines.shared.persona_config import PersonaStore
from test_offscreen_rendering import Fixture

@unittest.skipUnless(os.environ.get('CLOAKFOX_NATIVE_SURFACE_PROBE'),'Set CLOAKFOX_NATIVE_SURFACE_PROBE for native host acceptance')
class NativeHostSurface(unittest.TestCase):
    def test_owned_fixture_reaches_native_parent_without_cef_window(self):
        self.check_owned_fixture()

    def test_popup_pixels_arrive_and_retire_on_owned_native_surface(self):
        self.check_owned_fixture(popup=True)

    def check_owned_fixture(self,popup=False):
        with tempfile.TemporaryDirectory(prefix='cloakfox-native-surface-') as directory:
            root=Path(directory);profile=root/'profile';profile.mkdir(mode=0o700)
            config=PersonaStore(root/'personas').get('1','chromium')
            configFile=root/'config.json';configFile.write_text(json.dumps(config));configFile.chmod(0o600)
            server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Fixture)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                arguments=[os.environ['CLOAKFOX_NATIVE_SURFACE_PROBE'],os.environ['CLOAKFOX_CHROMIUM_BIN'],
                    str(profile),str(configFile),f'http://127.0.0.1:{server.server_port}/']
                if popup:arguments.append('--popup')
                result=subprocess.run(arguments,capture_output=True,text=True,timeout=65)
                self.assertEqual(result.returncode,0,result.stderr[-5000:])
                frame=json.loads(result.stdout)
                self.assertEqual(frame['status'],'passed')
                self.assertEqual(frame['cornerBGRA'],[91,37,13,255])
                self.assertEqual([frame['width'],frame['height']],[640,480])
                self.assertEqual(frame['configRevision'],config['revision'])
                self.assertTrue(frame['inputOwnerVerified'])
                self.assertFalse(frame['topLevelWindow'])
                self.assertEqual(frame['popupPixelsVerified'],popup)
            finally:server.shutdown();server.server_close()

    def test_fixture_cannot_reach_another_origin_or_follow_redirects(self):
        received=[]
        class Outside(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(self.path)
                self.send_response(200);self.send_header('Access-Control-Allow-Origin','*');self.end_headers();self.wfile.write(b'outside')
            def log_message(self,*args):pass
        outside=http.server.ThreadingHTTPServer(('127.0.0.1',0),Outside)
        threading.Thread(target=outside.serve_forever,daemon=True).start()
        target=f'http://127.0.0.1:{outside.server_port}'
        class Scoped(Fixture):
            def do_GET(self):
                if self.path=='/redirect':
                    self.send_response(302);self.send_header('Location',target+'/redirected');self.end_headers();return
                if self.path=='/worker.js':
                    body=("fetch("+json.dumps(target+'/worker')+").catch(()=>{}).then(()=>postMessage('done'))").encode()
                elif self.path=='/service.js':
                    body=("self.onmessage=e=>e.waitUntil(fetch("+json.dumps(target+'/service')+").catch(()=>{}).then(()=>e.source.postMessage('done')))").encode()
                else:
                    body=("""<!doctype html><style>html,body{margin:0;background:rgb(13,37,91)}html{scrollbar-width:none}body{height:3000px}input{position:absolute;top:0;left:0}iframe{position:absolute;top:280px;left:300px}img{position:absolute;top:600px}</style><input id=field><iframe src='/redirect'></iframe><img src='"""+target+"""/image'><script>
window.fixtureCompletion=Promise.all([
 fetch("""+json.dumps(target+'/fetch')+""").catch(()=>{}),fetch('/redirect').catch(()=>{}),
 new Promise((resolve,reject)=>{const w=new Worker('/worker.js');w.onmessage=()=>{w.terminate();resolve()};w.onerror=reject}),
 navigator.serviceWorker.register('/service.js').then(()=>navigator.serviceWorker.ready).then(reg=>new Promise(resolve=>{navigator.serviceWorker.onmessage=()=>resolve();reg.active.postMessage('check')}))
]).then(()=>true);
</script>""").encode()
                self.send_response(200);self.send_header('Content-Type','application/javascript' if self.path.endswith('.js') else 'text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        scoped=http.server.ThreadingHTTPServer(('127.0.0.1',0),Scoped)
        threading.Thread(target=scoped.serve_forever,daemon=True).start()
        try:
            with tempfile.TemporaryDirectory(prefix='cloakfox-fixture-scope-') as directory:
                root=Path(directory);profile=root/'profile';profile.mkdir(mode=0o700)
                config=PersonaStore(root/'personas').get('1','chromium')
                config_file=root/'config.json';config_file.write_text(json.dumps(config));config_file.chmod(0o600)
                result=subprocess.run([os.environ['CLOAKFOX_NATIVE_SURFACE_PROBE'],os.environ['CLOAKFOX_CHROMIUM_BIN'],str(profile),str(config_file),f'http://127.0.0.1:{scoped.server_port}/'],capture_output=True,text=True,timeout=65)
                self.assertEqual(result.returncode,0,result.stderr[-5000:])
                self.assertEqual(received,[],'Experimental fixture escaped its permitted origin')
        finally:
            scoped.shutdown();scoped.server_close();outside.shutdown();outside.server_close()

    def test_fixture_websockets_stay_on_the_bound_origin_in_all_realms(self):
        import base64, hashlib
        outside_hits=[]; allowed_hits=[]
        class SocketServer(http.server.BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def socket(self, hits):
                hits.append(self.path)
                key=self.headers.get('Sec-WebSocket-Key','')
                accept=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
                self.send_response(101);self.send_header('Upgrade','websocket');self.send_header('Connection','Upgrade');self.send_header('Sec-WebSocket-Accept',accept);self.end_headers()
                self.wfile.write(b'\x81\x05owned');self.wfile.flush()
                self.close_connection=True
            def do_GET(self):self.socket(outside_hits)
            def log_message(self,*args):pass
        outside=http.server.ThreadingHTTPServer(('127.0.0.1',0),SocketServer)
        threading.Thread(target=outside.serve_forever,daemon=True).start()
        forbidden=f'ws://127.0.0.1:{outside.server_port}'
        class Scoped(SocketServer):
            def do_GET(self):
                if self.headers.get('Upgrade','').lower()=='websocket':self.socket(allowed_hits);return
                # Negative checks observe actual server traffic, not an error
                # string. Positive checks also require a native data frame.
                checks="const check=(path,allowed=false)=>new Promise(resolve=>{const s=new WebSocket(path);s.onerror=()=>resolve(!allowed);s.onopen=()=>{if(!allowed){s.close();resolve(false)}};s.onmessage=e=>{s.close();resolve(allowed&&e.data===\"owned\")};setTimeout(()=>{s.close();resolve(false)},2000)});"
                if self.path=='/worker.js':body=(checks+"Promise.all([check("+json.dumps(forbidden+'/dedicated')+"),check('ws://'+location.host+'/allowed-dedicated',true)]).then(values=>postMessage(values.every(Boolean)))").encode()
                elif self.path=='/shared.js':body=(checks+"onconnect=e=>{const p=e.ports[0];Promise.all([check("+json.dumps(forbidden+'/shared')+"),check('ws://'+location.host+'/allowed-shared',true)]).then(values=>p.postMessage(values.every(Boolean)))}").encode()
                elif self.path=='/service.js':body=(checks+"onmessage=e=>e.waitUntil(Promise.all([check("+json.dumps(forbidden+'/service')+"),check('ws://'+location.host+'/allowed-service',true)]).then(values=>e.source.postMessage(values.every(Boolean))))").encode()
                else:body=("<!doctype html><style>html,body{margin:0;background:rgb(13,37,91)}html{scrollbar-width:none}body{height:3000px}</style><input id=field><script>"+checks+"window.fixtureCompletion=Promise.all([check("+json.dumps(forbidden+'/page')+"),check('ws://'+location.host+'/allowed-page',true),new Promise(resolve=>{const w=new Worker('/worker.js');w.onmessage=e=>{w.terminate();resolve(e.data)}}),new Promise(resolve=>{const w=new SharedWorker('/shared.js');w.port.onmessage=e=>{w.port.close();resolve(e.data)}}),navigator.serviceWorker.register('/service.js').then(()=>navigator.serviceWorker.ready).then(r=>new Promise(resolve=>{navigator.serviceWorker.onmessage=e=>resolve(e.data);r.active.postMessage('check')}))]).then(values=>values.every(Boolean))</script>").encode()
                self.send_response(200);self.send_header('Content-Type','application/javascript' if self.path.endswith('.js') else 'text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        scoped=http.server.ThreadingHTTPServer(('127.0.0.1',0),Scoped)
        threading.Thread(target=scoped.serve_forever,daemon=True).start()
        try:
            with tempfile.TemporaryDirectory(prefix='cloakfox-fixture-websockets-') as directory:
                root=Path(directory);profile=root/'profile';profile.mkdir(mode=0o700)
                config=PersonaStore(root/'personas').get('1','chromium')
                config_file=root/'config.json';config_file.write_text(json.dumps(config));config_file.chmod(0o600)
                result=subprocess.run([os.environ['CLOAKFOX_NATIVE_SURFACE_PROBE'],os.environ['CLOAKFOX_CHROMIUM_BIN'],str(profile),str(config_file),f'http://127.0.0.1:{scoped.server_port}/'],capture_output=True,text=True,timeout=65)
                self.assertEqual(result.returncode,0,result.stderr[-5000:])
                self.assertCountEqual(allowed_hits,['/allowed-page','/allowed-dedicated','/allowed-shared','/allowed-service'],'Allowed owned WebSockets must still connect')
                self.assertEqual(outside_hits,[],'WebSocket escaped the immutable fixture origin')
        finally:
            scoped.shutdown();scoped.server_close();outside.shutdown();outside.server_close()
