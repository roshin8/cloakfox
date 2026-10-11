"""Shared/service/dedicated worker region, container and live policy coverage.

Uses page-parsed functions (not WebDriver's Intl realm), real worker fetches,
long-lived worker instances, and loopback origins only. Run after native rebuild.
"""
import http.server
import json
import tempfile
import threading
from pathlib import Path
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from probe_daily_defaults import launch
from probe_container_workflows import open_site, switch_content
from probe_regions import MEASURE

WORKER = MEASURE + """
const instance = crypto.randomUUID();
async function report() {
 const c=new OffscreenCanvas(40,40),x=c.getContext('2d');
 x.fillStyle='#5278aa';x.fillRect(0,0,40,40);
 x.fillStyle='#b44e25';x.fillRect(5,7,23,19);
 let h=2166136261; for(const b of x.getImageData(0,0,40,40).data) h=Math.imul(h^b,16777619)>>>0;
 return {...measure(),instance,canvas:h,header:await (await fetch('/headers')).text()};
}
"""
PAGE = """<!doctype html><title>Worker lifecycle</title><button id=measure>measure</button><script>
let workers;
async function setup(){
 const dedicated=new Worker('/dedicated.js');
 const shared=new SharedWorker('/shared.js');shared.port.start();
 const reg=await navigator.serviceWorker.register('/service.js');
 await navigator.serviceWorker.ready;
 workers={dedicated,shared:shared.port,service:reg.active};
}
const ready=setup();
function ask(target,service=false){return new Promise((resolve,reject)=>{
 const timer=setTimeout(()=>reject(Error('worker timeout')),12000);
 const done=e=>{clearTimeout(timer);resolve(e.data)};
 if(service){const ch=new MessageChannel();ch.port1.onmessage=done;target.postMessage('report',[ch.port2]);}
 else {target.onmessage=done;target.postMessage('report');}
});}
document.getElementById('measure').onclick=async()=>{document.body.removeAttribute('data-result');try{
 await ready;const result={};for(const [kind,target] of Object.entries(workers))result[kind]=await ask(target,kind==='service');
 document.body.setAttribute('data-result',JSON.stringify(result));
}catch(e){document.body.setAttribute('data-result',JSON.stringify({error:String(e)}));}};
</script>"""

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        scripts = {
            '/dedicated.js': WORKER + 'onmessage=async()=>postMessage(await report());',
            '/shared.js': WORKER + 'onconnect=e=>{const p=e.ports[0];p.onmessage=async()=>p.postMessage(await report());p.start();};',
            '/service.js': WORKER + "oninstall=e=>skipWaiting();onactivate=e=>e.waitUntil(clients.claim());onmessage=e=>e.waitUntil(report().then(r=>e.ports[0].postMessage(r)));",
        }
        body = (self.headers.get('Accept-Language', '') if self.path == '/headers' else scripts.get(self.path, PAGE)).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/javascript' if self.path in scripts else 'text/html')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *_args): pass

def measure(driver):
    driver.execute_script("document.getElementById('measure').click()")
    data=json.loads(WebDriverWait(driver,25).until(lambda d:d.execute_script("return document.body.getAttribute('data-result')")))
    assert 'error' not in data,data
    return data

def policy(driver,ucid,exception=False,expires=None):
    driver.set_context('chrome')
    secret=driver.execute_script("""
const {setPrivacyPolicy}=ChromeUtils.importESModule('resource:///modules/CloakfoxPrivacyPolicy.sys.mjs');
const key='cloakfox.s.cloak_cfg_'+arguments[0];
const before=JSON.parse(Services.prefs.getStringPref(key))['fingerprint:secret'];
setPrivacyPolicy(arguments[0],{version:1,preset:'standard',exceptions:arguments[1]?[{site:'http://workers.test',vectors:['canvas'],expiresAt:arguments[2]||Date.now()+60000}]:[]});
const raw=Services.prefs.getStringPref(key),after=JSON.parse(raw);
return {sameSecret:before===after['fingerprint:secret'],configBytes:new TextEncoder().encode(raw).length,policy:after['privacy:policy'],epoch:Services.prefs.getIntPref('cloakfox.font_identity_epoch',0)};
""",ucid,exception,expires)
    assert secret['sameSecret'], 'policy update rotated identity secret'
    print(json.dumps({'policyUpdate':{'container':ucid,**secret}}),flush=True)
    driver.set_context('content')

def wait_canvas(driver, baseline, *, changed, phase, timeout=15):
    latest = {}
    def matches(_):
        nonlocal latest
        latest = measure(driver)
        return latest if all((latest[k]['canvas'] != baseline[k]['canvas']) == changed for k in baseline) else False
    try:
        return WebDriverWait(driver, timeout).until(matches)
    except TimeoutException as error:
        detail = {'phase':phase,'expectedChanged':changed,'baseline':baseline,'current':latest,
                  'workerChanges':{k:latest.get(k,{}).get('canvas') != baseline[k]['canvas'] for k in baseline}}
        print(json.dumps({'workerPolicyFailure':detail},indent=2),flush=True)
        raise AssertionError(json.dumps(detail)) from error


def main():
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    results=[]
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-worker-lifecycle-') as temp:
            profile=Path(temp)/'profile';profile.mkdir()
            profile.joinpath('user.js').write_text('user_pref("network.dns.localDomains","workers.test,other.test");\nuser_pref("dom.securecontext.allowlist","workers.test,other.test");\nuser_pref("network.trr.mode",5);\nuser_pref("dom.security.https_only_mode",false);\n')
            driver=launch(profile,Path(temp)/'gecko.log')
            try:
                ids=driver.execute_script("""
const {ContextualIdentityService:cis}=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
const {setRegion}=ChromeUtils.importESModule('resource:///modules/CloakfoxRegions.sys.mjs');
const {setContainerNetwork}=ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkPolicy.sys.mjs');
return [{locale:'de-DE',languages:['de-DE','de'],timezone:'Europe/Berlin'},{locale:'ja-JP',languages:['ja-JP','en-US'],timezone:'Asia/Tokyo'}].map((region,i)=>{const id=cis.create('Worker '+i,'fingerprint','blue').userContextId;setContainerNetwork(id,{mode:0,proxyURL:'',webrtcMode:2});setRegion(id,region);return id;});
""")
                # Restart with the full configs on disk: Gecko's immutable
                # startup shared-pref map may retain their original >4KiB
                # values while later dynamic pref updates omit those values.
                saved=driver.execute_async_script("""
const done=arguments[arguments.length-1];
(async()=>{const {ContextualIdentityService:cis}=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
if(cis._saver?.isRunning)await cis._saver.finalize();cis.saveSoon();cis._saver.disarm();await cis.save();Services.prefs.savePrefFile(null);})().then(()=>done(null),e=>done(String(e)));
""")
                assert saved is None, saved
                driver.quit()
                driver=launch(profile,Path(temp)/'gecko-restarted.log')
                for i,ucid in enumerate(ids):
                    other_handle,_=open_site(driver,f'http://other.test:{server.server_port}/',ucid)
                    other=measure(driver)
                    primary_handle,_=open_site(driver,f'http://workers.test:{server.server_port}/',ucid)
                    initial=measure(driver)
                    print(json.dumps({'initial':{'container':ucid,'workers':initial,'otherSite':other}}),flush=True)
                    for kind in initial:
                        assert initial[kind]['canvas']!=other[kind]['canvas'], ('site isolation',kind,initial,other)
                    for data in initial.values():
                        assert data['locale']==['de-DE','ja-JP'][i],data
                        assert data['languages']==[['de-DE','de'],['ja-JP','en-US']][i],data
                        assert data['language']==['de-DE','ja-JP'][i],data
                        assert data['timezone']==['Europe/Berlin','Asia/Tokyo'][i],data
                        assert data['explicit']=='ja-JP',data
                        assert [data['winter'],data['summer']]==[[-60,-120],[-540,-540]][i],data
                        assert data['header']==['de-DE,de;q=0.9','ja-JP,en-US;q=0.9'][i],data
                    policy(driver,ucid,True)
                    excepted=wait_canvas(driver,initial,changed=True,phase='exception added')
                    switch_content(driver,other_handle)
                    other_excepted=measure(driver)
                    assert other_excepted==other,('exception escaped its site',other,other_excepted)
                    switch_content(driver,primary_handle)
                    policy(driver,ucid)
                    restored=wait_canvas(driver,initial,changed=False,phase='exception removed')
                    for kind in initial:
                        assert initial[kind]['instance']==excepted[kind]['instance']==restored[kind]['instance'],(kind,initial,restored)
                    # Check expiry on the existing worker without any main-thread
                    # config read or page reload after installing the exception.
                    driver.set_context('chrome');expiry=driver.execute_script('return Date.now()+3000');driver.set_context('content')
                    policy(driver,ucid,True,expiry)
                    short=measure(driver)
                    assert all(short[k]['canvas']==excepted[k]['canvas'] for k in short),short
                    expired=wait_canvas(driver,initial,changed=False,phase='exception expired',timeout=12)
                    results.append({'container':ucid,'initial':initial,'excepted':excepted,'restored':restored,'expired':expired,'otherSite':other})
                for kind in results[0]['initial']:
                    assert results[0]['initial'][kind]['canvas']!=results[1]['initial'][kind]['canvas'],results
                print(json.dumps({'ok':True,'results':results},indent=2))
            finally: driver.quit()
    finally:server.shutdown();server.server_close()

if __name__=='__main__':main()
