"""Native FontFace lifecycle with persona fonts, local fallback and master off.

Uses bundled Arial bytes served on loopback; no external font requests. Run
with CLOAKFOX_BIN and optional REPORT_DIR. local() is deliberately unavailable
while the persona family list is active, including for allowed families; normal
CSS family rendering remains available. Master off restores native local lookup.
"""
from __future__ import annotations
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from selenium.common.exceptions import TimeoutException
import time
from probe_bundled_fonts import fonts_dir_for
from screen_management_fixture import ScreenManagementFixture

PROBE = r'''
const [family, source, done] = arguments;
const face = new FontFace(family, source);
const initial = face.status;
const loaded = face.loaded;
let settledBeforeLoad = false;
loaded.then(()=>{settledBeforeLoad=true},()=>{settledBeforeLoad=true});
Promise.resolve().then(async()=>{
  const beforeLoad = settledBeforeLoad;
  const promise = face.load();
  const loading = face.status;
  let result, error;
  try { result = await promise; } catch(e) { error=e.name; }
  done({initial, beforeLoad, loading, final:face.status, samePromise:promise===loaded,
    resolvedSelf:result===face, error:error || null});
});
'''

def main():
    binary=os.environ['CLOAKFOX_BIN']
    fonts=fonts_dir_for(binary)
    assert fonts, 'Bundled font pack required'
    font=(fonts/'Arial.ttf').read_bytes()
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if self.path.startswith('/font.ttf'):
                time.sleep(.2)  # require a genuinely asynchronous network load
                body=font; status=200; mime='font/ttf'
            elif self.path=='/':
                body=b'<!doctype html><meta charset=utf-8><title>FontFace fixture</title>'; status=200; mime='text/html'
            else:
                time.sleep(.2); body=b'missing'; status=404; mime='text/plain'
            self.send_response(status); self.send_header('Content-Type',mime)
            self.send_header('Cache-Control','no-store'); self.end_headers()
            self.wfile.write(body)
        def log_message(self,*_): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_port}'
    failures=[]; results={}
    def check(ok,name,value):
        results[name]=value
        print(('PASS ' if ok else 'FAIL ')+name+': '+json.dumps(value),flush=True)
        if not ok: failures.append(name)
    try:
        with ScreenManagementFixture(binary=binary) as f:
            d=f.driver
            f.set_config(0,{'fonts':['Arial','Courier New','Times New Roman','Helvetica','Menlo']})
            f.set_master(False)
            d=f.restart()  # obtain a verified native face-name positive control
            d.set_script_timeout(10);d.get(origin)
            native=d.execute_async_script('''const done=arguments[0];(async()=>{
              for(const name of ['ArialMT','Helvetica','HelveticaNeue','Times-Roman','Menlo-Regular',
                  'DejaVuSans','LiberationSans-Regular','SegoeUI']) {
                const f=new FontFace('NativeControl','local("'+name+'")');
                try {await f.load();done({name,status:f.status});return} catch {}
              }done({error:'No installed native face control available'});
            })();''')
            native['policy']=f.chrome("return {enabled:Services.prefs.getBoolPref('cloakfox.enabled'),whitelist:Services.prefs.getStringPref('font.system.whitelist',''),rfp:Services.prefs.getBoolPref('privacy.resistFingerprinting'),visibility:Services.prefs.getIntPref('layout.css.font-visibility.standard',-1)}")
            check(native.get('status')=='loaded','verified native installed face control',native)
            assert native.get('status')=='loaded',native
            local_name=native['name']
            f.set_master(True);d=f.restart();d.set_script_timeout(10);d.get(origin)
            for enabled in (True,False):
                f.set_master(enabled)
                if not enabled:
                    d=f.restart()  # global installed-family whitelist rebuilds at startup
                    d.set_script_timeout(10); d.get(origin)
                else:
                    d.refresh()
                for family in ('Arial','AuthorCustomFamily'):
                    for success in (True,False):
                        path='font.ttf' if success else 'missing.woff'
                        source=f'url("{origin}/{path}?{enabled}-{family}")'
                        value=d.execute_async_script(PROBE,family,source)
                        expected='loaded' if success else 'error'
                        check(value['initial']=='unloaded' and not value['beforeLoad']
                              and value['loading']=='loading' and value['final']==expected
                              and value['samePromise'] and value['resolvedSelf']==success
                              and value['error']==(None if success else 'NetworkError'),
                              f'master {enabled} {family} {path} lifecycle',value)
                # The independently verified installed face must be inaccessible through local().
                for family in ('Arial','LocalAlias'):
                    value=d.execute_async_script(PROBE,family,f'local("{local_name}")')
                    check(value['initial']=='unloaded' and value['final']==('error' if enabled else 'loaded')
                          and value['resolvedSelf']==(not enabled),f'master {enabled} local {family}',value)
                before=len(requests)
                value=d.execute_async_script(PROBE,'MixedCustom',f'local("{local_name}"), url("{origin}/font.ttf?fallback-{enabled}")')
                check(value['initial']=='unloaded' and value['final']=='loaded' and value['resolvedSelf']
                      and (not enabled or len(requests)>before),f'master {enabled} local URL fallback',value)
                value=d.execute_script('''const s=document.createElement('span');s.textContent='mmmmWWiiii';
                  s.style.fontSize='72px';document.body.append(s);s.style.fontFamily='monospace';let base=s.offsetWidth;
                  s.style.fontFamily='Arial,monospace';let actual=s.offsetWidth;s.remove();return {base,actual};''')
                check(value['base']!=value['actual'],f'master {enabled} allowed CSS family renders',value)
                try:
                    value=d.execute_async_script('''const done=arguments[1];fetch(arguments[0]).then(r=>r.arrayBuffer()).then(async b=>{
                  const f=new FontFace('BufferCustom',new Uint8Array(b));try{const result=await f.loaded;
                  done({status:f.status,self:result===f})}catch(e){done({status:f.status,error:e.name})}});''',origin+'/font.ttf?buffer-'+str(enabled))
                except TimeoutException:
                    value={'error':'TimeoutError'}
                check(value=={'status':'loaded','self':True},f'master {enabled} typed webfont',value)
            (f.report_path/'fontface-results.json').write_text(json.dumps(results,indent=2))
    finally:
        server.shutdown(); server.server_close()
    assert not failures,failures

if __name__=='__main__': main()
