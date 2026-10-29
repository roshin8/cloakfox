"""Local TLS integration test: state isolation, positive controls, and worker parity.

Two non-default containers use the SAME origin. Cache network requests are
counted at the loopback server; no external service or physical device is used.
"""
from pathlib import Path
from screen_management_fixture import ScreenManagementFixture
import json

NAV='({userAgent:navigator.userAgent,platform:navigator.platform,language:navigator.language,hardwareConcurrency:navigator.hardwareConcurrency})'
PAGE='''<!doctype html><title>Container state test</title><script>
window.presentation=()=>({});
async function db(){return await new Promise((resolve,reject)=>{const r=indexedDB.open('isolation',1);r.onupgradeneeded=()=>r.result.createObjectStore('state');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)})}
async function idb(value){const d=await db();try{return await new Promise((resolve,reject)=>{const tx=d.transaction('state',value===undefined?'readonly':'readwrite');const store=tx.objectStore('state');const r=value===undefined?store.get('marker'):store.put(value,'marker');let result;r.onsuccess=()=>result=r.result;tx.oncomplete=()=>resolve(result??null);tx.onerror=()=>reject(tx.error)})}finally{d.close()}}
async function shared(value){const w=new SharedWorker('/shared-state.js');(window.sharedWorkers??=[]).push(w);w.port.start();return await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('shared worker timeout')),5000);w.port.onmessage=e=>{clearTimeout(timer);window.sharedPort=w.port;resolve(e.data)};w.port.postMessage({value})})}
async function dedicated(){const w=new Worker('/dedicated-state.js');return await new Promise((resolve,reject)=>{const timer=setTimeout(()=>{w.terminate();reject(Error('dedicated worker timeout'))},5000);w.onmessage=e=>{clearTimeout(timer);w.terminate();resolve(e.data)}})}
async function service(){const r=await navigator.serviceWorker.getRegistration();if(!r)return null;const worker=r.active||r.waiting||r.installing;if(!worker)return null;return await new Promise((resolve,reject)=>{const p=new MessageChannel();const timer=setTimeout(()=>reject(Error('service worker timeout')),5000);p.port1.onmessage=e=>{clearTimeout(timer);resolve(e.data)};worker.postMessage({},[p.port2])})}
window.writeState=async marker=>{document.cookie='identity='+marker+';SameSite=Lax;Secure;Path=/';localStorage.setItem('identity',marker);await idb(marker);const c=await caches.open('isolation');await c.put('/cache-marker',new Response(marker));await shared(marker);await navigator.serviceWorker.register('/service-state.js');await navigator.serviceWorker.ready;return await readState()};
window.readState=async()=>{const c=await caches.open('isolation');const response=await c.match('/cache-marker');return {cookie:document.cookie,local:localStorage.getItem('identity'),idb:await idb(),cache:response?await response.text():null,shared:await shared(),dedicated:{nav:await dedicated()},service:await service(),page:''' + NAV + '''}};
</script>'''
SHARED='''let marker=null;onconnect=e=>{const p=e.ports[0];p.onmessage=ev=>{if(ev.data.value!==undefined)marker=ev.data.value;p.postMessage({marker,nav:'''+NAV+'''})};p.start()};'''
SERVICE='''oninstall=e=>e.waitUntil(skipWaiting());onactivate=e=>e.waitUntil(clients.claim());onmessage=e=>e.waitUntil((async()=>{const c=await caches.open('isolation');const r=await c.match('/cache-marker');e.ports[0].postMessage({marker:r?await r.text():null,nav:'''+NAV+'''})})());'''

def main():
    failures=[]
    def check(ok,name,data):
        print(('PASS ' if ok else 'FAIL ')+name+': '+json.dumps(data),flush=True)
        if not ok: failures.append(name)
    with ScreenManagementFixture() as f:
        f.routes.update({'/state.html':(PAGE,{}),'/shared-state.js':(SHARED,{}),'/dedicated-state.js':('postMessage'+NAV+';',{}),'/consistency.js':((Path(__file__).resolve().parents[2]/'additions/browser/components/cloakfox/content/persona-consistency.mjs').read_text(),{}),'/service-state.js':(SERVICE,{}),'/network-cache.txt':('cache check',{'Cache-Control':'public, max-age=3600'})})
        f.set_config(1,{'navigator.userAgent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0','navigator.platform':'Win32','navigator.hardwareConcurrency':4,'navigator.language':'en-US'})
        f.set_config(2,{'navigator.userAgent':'Mozilla/5.0 (X11; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0','navigator.platform':'Linux x86_64','navigator.hardwareConcurrency':8,'navigator.language':'en-US'})
        d=f.open('/state.html',container=1);a_handle=d.current_window_handle
        def state(marker=None):
            script='const done=arguments[arguments.length-1];'+('writeState(arguments[0])' if marker else 'readState()')+'.then(done,e=>done({error:String(e)}));'
            return d.execute_async_script(script,*([marker] if marker else []))
        a=state('A');check(not a.get('error'),'container A state setup',a.get('error'))
        d.execute_async_script('const done=arguments[0];fetch("/network-cache.txt").then(()=>done(true),e=>done(String(e)))')
        initial=sum(p=='/network-cache.txt' for _,p in f.requests)
        f.open('/state.html',container=2);b_handle=d.current_window_handle;b=state()
        check(not b.get('error'),'container B state read',b.get('error'))
        for key in ['local','idb','cache']:check(b.get(key) is None,'B cannot read A '+key,b.get(key))
        check('identity=A' not in b.get('cookie',''),'cookies isolated',b.get('cookie'))
        check(b.get('shared',{}).get('marker') is None,'shared worker global isolated',b.get('shared',{}).get('marker'))
        check(b.get('service') is None,'service worker registration isolated',b.get('service'))
        d.execute_async_script('const done=arguments[0];fetch("/network-cache.txt").then(()=>done(true),e=>done(String(e)))')
        after_b=sum(p=='/network-cache.txt' for _,p in f.requests)
        check(after_b==initial+1,'network cache isolated across containers',[initial,after_b])
        state('B');f.open('/state.html',container=1);again=state()
        for key in ['local','idb','cache']:check(again.get(key)=='A','A retains its own '+key,again.get(key))
        check('identity=A' in again.get('cookie',''),'A retains its own cookie',again.get('cookie'))
        for kind in ['shared','service','dedicated']:
            if kind!='dedicated': check(again.get(kind,{}).get('marker')=='A',kind+' same-container positive control',again.get(kind,{}).get('marker'))
            page=again.get('page',{});worker=again.get(kind,{}).get('nav',{})
            differences=d.execute_async_script('const [page,worker,done]=arguments;import("/consistency.js").then(m=>done(m.compareRealmSignals(page,worker)),e=>done({error:String(e)}))',page,worker)
            check(not differences,kind+' page/worker identity parity',differences)
        d.execute_async_script('const done=arguments[0];fetch("/network-cache.txt").then(()=>done(true),e=>done(String(e)))')
        check(sum(p=='/network-cache.txt' for _,p in f.requests)==after_b,'same-container network-cache reuse',after_b)
        d.switch_to.window(b_handle);d.refresh();b_again=state()
        check(all(b_again.get(k)=='B' for k in ['local','idb','cache']),'B retains independent writes',b_again)
    assert not failures,failures
if __name__=='__main__':main()
