"""Catch shared storage/worker/message namespaces between container identities.

Real loopback origins and disposable profiles only. Same-owner positive controls
prove that writes/messages really arrive. No permissions, capture or public sites.
Changing container routing to a shared namespace must fail the isolation checks.
"""
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from probe_daily_defaults import launch
from probe_container_workflows import chrome, open_site, switch_content

WORKER = """let value=null;const instance=crypto.randomUUID();onconnect=e=>{const p=e.ports[0];p.onmessage=e=>{if(e.data.op==='set')value=e.data.value;p.postMessage({value,instance});};p.start();};"""
PAGE = """<!doctype html><title>Local container boundary fixture</title><script>
window.messages=[];window.channel=new BroadcastChannel('privacy-boundary');
channel.onmessage=e=>messages.push(e.data);
window.worker=new SharedWorker('/shared.js','privacy-boundary');worker.port.start();
function ask(op,value){return new Promise((resolve,reject)=>{
 const timer=setTimeout(()=>reject(Error('shared worker timeout')),5000);
 worker.port.onmessage=e=>{clearTimeout(timer);resolve(e.data)};
 worker.port.postMessage({op,value});
});}
function database(){return new Promise((resolve,reject)=>{
 const r=indexedDB.open('privacy-boundary',1);
 r.onupgradeneeded=()=>r.result.createObjectStore('values');
 r.onerror=()=>reject(r.error);r.onsuccess=()=>resolve(r.result);
});}
async function stored(write){
 const db=await database();let idb;
 try{ idb=await new Promise((resolve,reject)=>{
 const tx=db.transaction('values',write===undefined?'readonly':'readwrite'),store=tx.objectStore('values');
 const r=write===undefined?store.get('canary'):store.put(write,'canary');
 r.onsuccess=()=>{idb=write===undefined?(r.result??null):write};
 tx.oncomplete=()=>resolve(idb);tx.onabort=()=>reject(tx.error);
 });}finally{db.close();}
 const cache=await caches.open('privacy-boundary'),key=new URL('/canary',location.href);
 if(write!==undefined){localStorage.setItem('canary',write);sessionStorage.setItem('canary',write);document.cookie='canary='+write+'; SameSite=Lax; Max-Age=3600; path=/';await cache.put(key,new Response(write));}
 const response=await cache.match(key);
 return {local:localStorage.getItem('canary'),session:sessionStorage.getItem('canary'),idb,cache:response?await response.text():null,cookie:document.cookie,wire:await (await fetch('/headers',{cache:'no-store'})).text()};
}
</script>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = (WORKER if self.path=='/shared.js' else self.headers.get('Cookie','') if self.path=='/headers' else PAGE).encode()
        self.send_response(200)
        self.send_header('Content-Type','text/javascript' if self.path=='/shared.js' else 'text/plain' if self.path=='/headers' else 'text/html')
        self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass

def call(driver, expression, *args):
    result=driver.execute_async_script("const done=arguments[arguments.length-1];Promise.resolve().then(async()=>{"+expression+"}).then(value=>done({value}),error=>done({error:String(error)}));",*args)
    assert 'error' not in result,result
    return result['value']

def main():
    out=Path(os.environ.get('REPORT_DIR','/tmp/cloakfox-storage-boundaries'));out.mkdir(parents=True,exist_ok=True)
    report={'binary':os.environ['CLOAKFOX_BIN'],'headless':True,'checks':[]}
    def check(ok,name):
        report['checks'].append({'name':name,'pass':bool(ok)});print(('PASS ' if ok else 'FAIL ')+name,flush=True)
        assert ok,name
    def empty(data,label):
        for key in ('local','session','idb','cache'):check(data[key] is None,label+' has no foreign '+key)
        check('canary=' not in data['cookie'] and 'canary=' not in data['wire'],label+' has no foreign document or request cookie')
    def owns(data,value,label,session=True):
        for key in ('local','idb','cache'):check(data[key]==value,label+' retains own '+key)
        check(('canary='+value) in data['cookie'] and ('canary='+value) in data['wire'],label+' document and request cookies use own container')
        check(data['session']==(value if session else None),label+' sessionStorage is scoped to the correct tab')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-storage-boundaries-') as temp:
            profile=Path(temp)/'profile';profile.mkdir()
            d=launch(profile,out/'first-gecko.log');d.set_script_timeout(20)
            try:
                report['runtime']=d.execute_script('return {version:Services.appinfo.version,buildID:Services.appinfo.appBuildID,enabled:Services.prefs.getBoolPref("cloakfox.enabled")};')
                check(report['runtime']['enabled'],'privacy master enabled')
                a,b=chrome(d,"return ['Boundary A','Boundary B'].map(n=>cis.create(n,'fingerprint','blue').userContextId)")
                url=f'http://127.0.0.1:{server.server_port}/'
                handles={}
                for name,owner in [('A',a),('B',b),('A2',a)]:
                    handles[name],actual=open_site(d,url+f'?tab={name}',owner);check(actual==owner,name+' has actual requested owner')
                    empty(call(d,'return await stored();'),name+' initially')
                switch_content(d,handles['A']);owns(call(d,"return await stored('owner-A');"),'owner-A','A after write')
                first=call(d,"return await ask('set','worker-A');")
                switch_content(d,handles['B']);empty(call(d,'return await stored();'),'B after A writes')
                other=call(d,"return await ask('get');");check(other['value'] is None and other['instance']!=first['instance'],'identical SharedWorker URL/name has separate container state')
                owns(call(d,"return await stored('owner-B');"),'owner-B','B after own write')
                call(d,"return await ask('set','worker-B');")
                switch_content(d,handles['A2']);owns(call(d,'return await stored();'),'owner-A','same-owner new tab',session=False)
                shared=call(d,"return await ask('get');");check(shared==first,'same-owner SharedWorker positive control sees the live state')
                # The same message must reach A but never B, while both stay open.
                d.execute_script("channel.postMessage('from-A2');")
                switch_content(d,handles['A']);arrived=call(d,"for(let n=0;n<50&&!messages.length;n++)await new Promise(r=>setTimeout(r,20));return messages;")
                check(arrived==['from-A2'],'same-owner BroadcastChannel positive control delivers')
                switch_content(d,handles['B']);foreign=call(d,"await new Promise(r=>setTimeout(r,500));return messages;")
                check(foreign==[],'BroadcastChannel does not cross containers')
                d.execute_script("channel.postMessage('from-B');")
                switch_content(d,handles['A']);unchanged=call(d,"await new Promise(r=>setTimeout(r,500));return messages;")
                check(unchanged==['from-A2'],'reverse BroadcastChannel message stays in its container')
                d.refresh();owns(call(d,'return await stored();'),'owner-A','A reload')
                # Same owner, different origin: no storage or shared-worker state.
                site,actual=open_site(d,f'http://localhost:{server.server_port}/',a)
                check(actual==a,'other-site navigation preserves container owner')
                empty(call(d,'return await stored();'),'same owner other origin')
                isolated=call(d,"return await ask('get');");check(isolated['value'] is None and isolated['instance']!=first['instance'],'SharedWorker does not cross origins')
            finally:d.quit()
            d=launch(profile,out/'restart-gecko.log');d.set_script_timeout(20)
            try:
                for name,owner,value in [('A',a,'owner-A'),('B',b,'owner-B')]:
                    _,actual=open_site(d,url+f'?tab={name}',owner);check(actual==owner,name+' owner survives profile restart')
                    owns(call(d,'return await stored();'),value,name+' restart',session=False)
                    restarted=call(d,"return await ask('get');");check(restarted['value'] is None,name+' shared-worker memory is not persisted as storage')
            finally:d.quit()
    finally:
        server.shutdown();server.server_close();(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0
if __name__=='__main__':raise SystemExit(main())
