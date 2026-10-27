#!/usr/bin/env python3
"""Loopback regression for inherited frame protection, worker GPU and WebIDL brands.

Run against a freshly built CLOAKFOX_BIN. Disposable profile; no real websites,
GPU adapter requests, or changes to the installed app/profile.
"""
from __future__ import annotations
import json
import os
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_focus_masking import chrome, set_pref

COLLECT = r"""
function collect(){
  const n=navigator,p=Object.getPrototypeOf(n),gpu=n.gpu;
  const r={gpuAvailable:!!gpu,gpuType:typeof gpu,gpuBinding:'gpu' in p,brands:{},values:{},
    gpuShape:gpu?{same:gpu===n.gpu,constructor:gpu.constructor.name,prototype:Object.getPrototypeOf(gpu)===GPU.prototype}:null};
  for(const key of ['gpu','webdriver','pdfViewerEnabled','onLine','cookieEnabled']){
    const d=Object.getOwnPropertyDescriptor(p,key);if(!d?.get)continue;
    r.values[key]=typeof n[key]==='object'?typeof n[key]:n[key];
    r.brands[key]=[{},null,undefined,Object.create(p)].map(receiver=>{
      try{d.get.call(receiver);return null}catch(e){return e.name}
    });
  }
  if(n.javaEnabled){
    r.values.javaEnabled=n.javaEnabled();
    try{p.javaEnabled.call({});r.brands.javaEnabled=null}catch(e){r.brands.javaEnabled=e.name}
  }
  return r;
}
"""
PAGE = '<!doctype html><title>Realm privacy</title><script>' + COLLECT + r"""
window.audit={page:collect()};
const run=new URLSearchParams(location.search).get('run');
for(const kind of ['blank','srcdoc','normal']){
  const f=document.createElement('iframe');f.id=kind;
  f.onload=()=>{audit[kind]=f.contentWindow.collect?f.contentWindow.collect():
    f.contentWindow.eval('('+collect.toString()+')()')};
  if(kind==='srcdoc')f.srcdoc='<!doctype html><body>srcdoc';
  else f.src=kind==='blank'?'about:blank':'/frame';
  document.documentElement.append(f);
  if(kind==='blank')audit.initialBlank=f.contentWindow.eval('('+collect.toString()+')()');
}
const opaque=document.createElement('iframe');opaque.id='opaque';
opaque.sandbox='allow-scripts';opaque.srcdoc='<!doctype html><body>opaque';
document.documentElement.append(opaque);
const w=new Worker('/dedicated.js?run='+run);w.onmessage=e=>{audit.dedicated=e.data};
const shared=new SharedWorker('/shared.js?run='+run);shared.port.onmessage=e=>{audit.shared=e.data};shared.port.start();
navigator.serviceWorker.register('/service.js?run='+run).then(async reg=>{
  const worker=reg.installing||reg.waiting||reg.active;
  if(worker.state!=='activated')await new Promise(resolve=>worker.addEventListener('statechange',()=>{
    if(worker.state==='activated')resolve();
  }));
  const channel=new MessageChannel();channel.port1.onmessage=e=>{audit.service=e.data;channel.port1.close()};
  worker.postMessage('collect',[channel.port2]);
}).catch(e=>{audit.error=String(e)});
window.refreshWorkers=async()=>{
 const request=p=>new Promise(resolve=>{p.onmessage=e=>resolve(e.data);p.postMessage('collect')});
 return {dedicated:await request(w),shared:await request(shared.port)};
};
window.addEventListener('pagehide',()=>{w.terminate();shared.port.close()});
</script>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = urlparse(self.path).path
        scripts = {
            '/dedicated.js': 'postMessage(collect());onmessage=()=>postMessage(collect());',
            '/shared.js': 'onconnect=e=>{const p=e.ports[0];p.postMessage(collect());p.onmessage=()=>p.postMessage(collect())};',
            '/service.js': 'oninstall=()=>skipWaiting();onmessage=e=>e.ports[0].postMessage(collect());',
        }
        body = (COLLECT + scripts[route] if route in scripts else
                '<!doctype html><script>'+COLLECT+'</script>' if route == '/frame' else PAGE).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/javascript' if route in scripts else 'text/html')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *args):
        pass


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    root = Path(os.environ.get('REPORT_DIR') or tempfile.mkdtemp(prefix='cloakfox-realm-report-'))
    root.mkdir(parents=True, exist_ok=True)
    checks, observations = [], {}
    def check(ok, label, value=None):
        checks.append({'pass': bool(ok), 'label': label, 'value': value})
        print(('PASS ' if ok else 'FAIL ') + label, flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-realm-profile-') as tmp:
            profile = Path(tmp, 'profile');profile.mkdir()
            (profile/'user.js').write_text('user_pref("cloakfox.enabled", false);\n'
                'user_pref("dom.webgpu.enabled", true);\n'
                'user_pref("privacy.userContext.enabled", true);\n')
            options = Options();options.binary_location = os.environ['CLOAKFOX_BIN']
            options.add_argument('-headless');options.add_argument('-purgecaches')
            options.add_argument('-profile');options.add_argument(str(profile))
            driver = webdriver.Firefox(options=options, service=Service(
                service_args=['--allow-system-access'], log_output=str(root/'gecko.log')))
            driver.set_script_timeout(20)
            observations['browserInfo']=chrome(driver,'return {version:Services.appinfo.version,buildID:Services.appinfo.appBuildID}')
            assert observations['browserInfo']['version'].startswith('159.'),observations['browserInfo']
            try:
                url = f'http://127.0.0.1:{server.server_port}/'
                default = driver.current_window_handle
                chrome(driver, """
                  for(const id of [0,2]){
                    const k='cloakfox.s.cloak_cfg_'+id;
                    const c=JSON.parse(Services.prefs.getStringPref(k,'{}'));
                    c['navigator:webgpu:disabled']=id===2;
                    Services.prefs.setStringPref(k,JSON.stringify(c));
                  }
                """)
                before = set(driver.window_handles)
                chrome(driver, """
                  gBrowser.selectedTab=gBrowser.addTab(arguments[0],{userContextId:2,
                    triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
                """, url+'warm')
                container = next(h for h in driver.window_handles if h not in before)
                for enabled, ucid, handle in [(False,0,default),(True,0,default),(True,2,container),(False,2,container)]:
                    driver.switch_to.window(handle);set_pref(driver,'cloakfox.enabled',enabled)
                    driver.get(url+'warm');time.sleep(.4)
                    driver.get(url+'?run='+str(time.time_ns()))
                    deadline=time.monotonic()+15;r=None
                    while time.monotonic()<deadline:
                        r=driver.execute_script('return window.wrappedJSObject?.audit||window.audit')
                        if r and all(k in r for k in ['page','initialBlank','blank','srcdoc','normal','dedicated','shared','service']):break
                        time.sleep(.1)
                    label=f'{enabled}:{ucid}';observations[label]=r
                    complete=r and all(k in r for k in ['page','initialBlank','blank','srcdoc','normal','dedicated','shared','service'])
                    check(complete,'all realms '+label,r)
                    if not complete:continue
                    for realm,data in r.items():
                        for key,brand in data['brands'].items():
                            check(brand=='TypeError' if key=='javaEnabled' else all(b=='TypeError' for b in brand),
                                  f'WebIDL brand {label}/{realm}/{key}',brand)
                        if not enabled or realm in ['dedicated','shared','service']:
                            # Service-worker WebGPU availability follows Firefox's native pref,
                            # enabled by default on macOS ARM in157. Keep the
                            # master-off control as the baseline for every realm.
                            native_available=observations['False:0'][realm]['gpuAvailable']
                            expected=native_available and not(enabled and ucid==2)
                            check(data['gpuAvailable']==expected,f'GPU policy {label}/{realm}',data)
                        elif realm in ['page','initialBlank','blank','srcdoc','normal']:
                            expected_type='undefined' if ucid==2 else 'object'
                            check(data['gpuType']==expected_type,f'inherited GPU presentation {label}/{realm}',data)
                        if data['gpuAvailable']:
                            check(data['gpuShape']=={'same':True,'constructor':'GPU','prototype':True},
                                  f'native GPU identity and prototype {label}/{realm}',data['gpuShape'])
                    if enabled:
                        for realm in ['initialBlank','blank','srcdoc','normal']:
                            check(r[realm]['values']==r['page']['values'],f'frame values agree {label}/{realm}',r[realm])
                    eligibility=chrome(driver,"""
                      const root=gBrowser.selectedBrowser.browsingContext.currentWindowGlobal;
                      const match=w=>{try{w.getActor('CloakfoxFeatureDetect');return true}catch{return false}};
                      const frames=root.browsingContext.children.slice(0,3).map(c=>match(c.currentWindowGlobal));
                      const opaque=match(root.browsingContext.children[3].currentWindowGlobal);
                      return {frames,opaque,chrome:match(window.windowGlobalChild)};
                    """)
                    check(all(eligibility['frames']) and not eligibility['chrome'] and not eligibility['opaque'],'content frames only '+label,eligibility)
                    if enabled:
                        # Same native getters and existing workers obey config
                        # updates without replacing their WebIDL accessors.
                        chrome(driver,'''const key='cloakfox.s.cloak_cfg_'+arguments[0];
                          const cfg=JSON.parse(Services.prefs.getStringPref(key));
                          cfg['navigator:webgpu:disabled']=arguments[1];Services.prefs.setStringPref(key,JSON.stringify(cfg));
                        ''',ucid,ucid==0)
                        deadline=time.monotonic()+5
                        while True:
                            live=driver.execute_async_script("const done=arguments[0];(window.wrappedJSObject||window).refreshWorkers().then(done)")
                            expected_available=ucid!=0
                            if all(d['gpuAvailable']==expected_available for d in live.values()) or time.monotonic()>deadline:break
                            time.sleep(.1)
                        check(all(d['gpuAvailable']==expected_available for d in live.values()),'live worker GPU config update '+label,live)
                        top=driver.execute_script('return {available:!!navigator.gpu,same:navigator.gpu===navigator.gpu}')
                        check(top=={'available':expected_available,'same':True},'live page GPU config update '+label,top)
                        chrome(driver,'''const key='cloakfox.s.cloak_cfg_'+arguments[0];
                          const cfg=JSON.parse(Services.prefs.getStringPref(key));
                          cfg['navigator:webgpu:disabled']=arguments[1];Services.prefs.setStringPref(key,JSON.stringify(cfg));
                        ''',ucid,ucid==2)
                    if enabled and ucid==2:
                        set_pref(driver,'cloakfox.enabled',False)
                        live=driver.execute_async_script("const done=arguments[0];(window.wrappedJSObject||window).refreshWorkers().then(done)")
                        check(all(d['gpuAvailable'] for d in live.values()),'live worker masteroff',live)
                # Browser-internal about documents must retain native behavior.
                driver.get('about:config')
                excluded=chrome(driver,"""
                  try{gBrowser.selectedBrowser.browsingContext.currentWindowGlobal.getActor('CloakfoxFeatureDetect');return false}
                  catch{return true}
                """)
                check(excluded,'about:config actor excluded')
            finally:
                driver.quit()
    finally:
        server.shutdown();server.server_close()
        (root/'result.json').write_text(json.dumps({'checks':checks,'observations':observations},indent=2)+'\n')
        print('Report: '+str(root),flush=True)
    if not all(c['pass'] for c in checks):raise SystemExit(1)

if __name__=='__main__':main()
