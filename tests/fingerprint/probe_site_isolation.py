"""Disposable local-origin site-noise probe; run after a native rebuild.

CLOAKFOX_BIN=/path/to/cloakfox python tests/fingerprint/probe_site_isolation.py
No public network endpoints. Verifies reload/subdomain stability, cross-site
separation, third-party frame partitioning, and window/dedicated-worker agreement.
"""
from __future__ import annotations
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

COLLECT = r"""
async function collect() {
  const canvas = typeof document === 'undefined' ? new OffscreenCanvas(64,32) : document.createElement('canvas');
  canvas.width=64; canvas.height=32;
  const c=canvas.getContext('2d');
  c.fillStyle='#3b7fab'; c.fillRect(0,0,64,32);
  const bytes=c.getImageData(0,0,64,32).data;
  let hash=2166136261;
  for (const b of bytes) hash=Math.imul(hash^b,16777619)>>>0;
  c.font='16px monospace';
  const out={canvas:hash, math:[Math.sin(.5),Math.cos(.5),Math.log(2)], font:c.measureText('Cloakfox text 123').width};
  if (typeof OfflineAudioContext !== 'undefined') {
    const audio=new OfflineAudioContext(1,128,48000);
    const osc=audio.createOscillator();osc.frequency.value=440;
    osc.connect(audio.destination);osc.start();
    const buffer=await audio.startRendering();
    out.audio=Array.from(buffer.getChannelData(0));
  }
  return out;
}
"""
PAGE = """<!doctype html><meta charset=utf-8><script>""" + COLLECT + r"""
window.siteProbe=(async()=>{
 const main=await collect();
 const worker=await new Promise((resolve,reject)=>{
  const w=new Worker('/worker.js'); w.onmessage=e=>{resolve(e.data);w.terminate()};w.onerror=reject;
 });
 return {main,worker};
})();
if(location.pathname==='/frame') siteProbe.then(result=>parent.postMessage({siteProbe:result},'*'));
</script>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        content = (COLLECT + 'collect().then(result=>postMessage(result));') if self.path == '/worker.js' else PAGE
        payload=content.encode()
        self.send_response(200)
        self.send_header('Content-Type','text/javascript' if self.path=='/worker.js' else 'text/html')
        self.send_header('Content-Length',str(len(payload)))
        self.end_headers(); self.wfile.write(payload)
    def log_message(self,*args):
        pass


def run():
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    port=server.server_port
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-site-probe-') as temp:
            profile=Path(temp,'profile');profile.mkdir()
            prefs={'cloakfox.enabled':True,'network.dns.localDomains':'one.test,child.one.test,two.test,tracker.test',
                   'dom.security.https_only_mode':False,'dom.security.https_only_mode_pbm':False,
                   'network.trr.mode':5}
            profile.joinpath('user.js').write_text(''.join(f'user_pref({json.dumps(k)},{json.dumps(v)});\n' for k,v in prefs.items()))
            opts=Options();opts.binary_location=os.environ['CLOAKFOX_BIN']
            opts.add_argument('--headless');opts.add_argument('-profile');opts.add_argument(str(profile))
            with webdriver.Firefox(options=opts,service=Service(service_args=['--allow-system-access'],log_output=str(Path(temp,'gecko.log')))) as driver:
                driver.set_script_timeout(30)
                def sample(host):
                    driver.get(f'http://{host}:{port}/')
                    result=driver.execute_async_script('const cb=arguments[arguments.length-1];siteProbe.then(cb,e=>cb({error:String(e)}));')
                    assert 'error' not in result,result
                    return result
                a=sample('one.test');reload_a=sample('one.test');sub=sample('child.one.test');b=sample('two.test')
                assert a==reload_a,'same-site reload changed output'
                assert a==sub,'same schemeful site subdomain changed output'
                for key in ('canvas','math','font','audio'):
                    assert a['main'][key]!=b['main'][key],f'{key} remains cross-site linkable'
                for record in (a,b):
                    for key in ('canvas','math','font'):
                        assert record['main'][key]==record['worker'][key],f'window/worker disagreement: {key}'
                frames=[]
                for host in ('one.test','two.test'):
                    own=sample(host)
                    frame=driver.execute_async_script('''const cb=arguments[arguments.length-1];
                      const frame=document.createElement('iframe');
                      const receive=e=>{if(e.source===frame.contentWindow&&e.data.siteProbe){removeEventListener('message',receive);cb(e.data.siteProbe)}};
                      addEventListener('message',receive);frame.src=arguments[0];document.body.append(frame);''',f'http://tracker.test:{port}/frame')
                    assert frame==own,'third-party frame/worker did not use publisher site'
                    frames.append(frame)
                assert frames[0]!=frames[1],'tracker has same outputs across publishers'
                print(json.dumps({'status':'PASS','sites':['one.test','two.test'],'reload':True,'subdomain':True,'frames':True,'worker':True},indent=2))
    finally:
        server.shutdown();server.server_close()

if __name__=='__main__':
    run()
