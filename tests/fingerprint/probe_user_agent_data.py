#!/usr/bin/env python3
"""UA Client Hints compatibility: first script, frames, workers, and containers.

Uses only local fixtures and disposable profiles. The early-script check is the
browser-brand predicate observed in HackerRank's onboarding bundle. It does not
exercise or claim support for interview/proctoring features.
"""
from __future__ import annotations
import json
import os
import shutil
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_focus_masking import chrome

CHROME = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
EDGE = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.6613.120 Safari/537.36 Edg/128.0.2739.79'
ANDROID = 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36'
FIREFOX = 'Mozilla/5.0 (X11; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0'
COLLECT = """
const early={ua:navigator.userAgent,present:'userAgentData' in navigator,
        classType:typeof NavigatorUAData,gate:!!navigator.userAgentData?.brands?.some(b=>b.brand.includes('Chromium')||b.brand.includes('Google Chrome'))};
async function collect(){
    const d=navigator.userAgentData;
    if(!d)return early;
    const desc=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(navigator),'userAgentData');
    let illegal=false,missing=false,missingPromise=false;
    try{desc.get.call({})}catch(e){illegal=e instanceof TypeError}
    try{const p=d.getHighEntropyValues();missingPromise=p instanceof Promise;await p}catch(e){missing=e instanceof TypeError}
    return {...early,low:d.toJSON(),json:JSON.parse(JSON.stringify(d)),
        tag:Object.prototype.toString.call(d),same:d===navigator.userAgentData,
        frozen:Object.isFrozen(d.brands),cached:d.brands===d.brands,
        own:Object.hasOwn(navigator,'userAgentData'),getter:desc.get.toString(),illegal,missing,missingPromise,
        empty:await d.getHighEntropyValues([]),subset:await d.getHighEntropyValues(['architecture','unknown']),
        high:await d.getHighEntropyValues(['architecture','bitness','fullVersionList','model','platformVersion','uaFullVersion','wow64','formFactors','unknown'])};
}
"""
PAGE = '<!doctype html><meta charset=utf-8><script>'+COLLECT+"window.result=collect();</script>"
WORKER = COLLECT+"self.onmessage=async()=>postMessage(await collect());"
SHARED = COLLECT+"self.onconnect=e=>{const p=e.ports[0];p.onmessage=async()=>p.postMessage(await collect());p.start()};"
SERVICE = COLLECT+"self.addEventListener('install',()=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));self.addEventListener('message',e=>e.waitUntil(collect().then(r=>e.ports[0].postMessage(r))));"
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body={'/worker.js':WORKER,'/shared.js':SHARED,'/service.js':SERVICE}.get(self.path,PAGE).encode()
        self.send_response(200);self.send_header('Content-Type','text/javascript' if self.path.endswith('.js') else 'text/html');self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass

def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    results=[]
    with tempfile.TemporaryDirectory(prefix='cloakfox-ua-data-') as tmp:
        opts=Options();opts.binary_location=os.environ['CLOAKFOX_BIN'];opts.add_argument('-headless')
        driver=webdriver.Firefox(options=opts,service=Service(executable_path=os.environ.get('GECKODRIVER') or shutil.which('geckodriver'),service_args=['--allow-system-access'],log_output=str(Path(tmp)/'gecko.log')))
        driver.set_script_timeout(20)
        def check(ok,name,data):
            results.append({'name':name,'pass':bool(ok),'data':data});print(('PASS' if ok else 'FAIL')+' '+name,flush=True)
            assert ok,json.dumps(data,indent=2)
        def set_identity(ua,ucid=0,enabled=True):
            chrome(driver,"""Services.prefs.setBoolPref('cloakfox.enabled',arguments[2]);
                const key='cloakfox.s.cloak_cfg_'+arguments[1],cfg=JSON.parse(Services.prefs.getStringPref(key,'{}'));
                cfg['navigator.userAgent']=arguments[0];cfg['headers.User-Agent']=arguments[0];
                Services.prefs.setStringPref(key,JSON.stringify(cfg));""",ua,ucid,enabled)
        def read():
            deadline=time.monotonic()+10
            while not driver.execute_script('return !!window.result'):
                assert time.monotonic()<deadline,'Fixture did not load'
                time.sleep(.05)
            return driver.execute_async_script('const done=arguments[0];window.result.then(done,e=>done({error:String(e)}));')
        def validate(r,platform,brand,version,mobile=False):
            check(r.get('gate') is True,'Chromium gate passes in first script',r)
            low=r['low'];brands={b['brand']:b['version'] for b in low['brands']}
            check(low['platform']==platform and low['mobile']==mobile and brands.get(brand)==version and 'Chromium' in brands,'UA-derived identity',r)
            check(set(r['subset'])=={'brands','mobile','platform','architecture'},'only requested supported hints returned',r)
            check(r['json']==low and r['empty']==low and 'unknown' not in r['high'],'JSON and hint filtering',r)
            check(not r['same'] and not r['cached'] and r['frozen'] and not r['own'] and r['illegal'] and r['missing'] and r['missingPromise'] and r['classType']=='function' and r['tag']=='[object NavigatorUAData]' and '[native code]' in r['getter'],'native API contract',r)
            return r
        try:
            set_identity(CHROME);driver.get(f'http://127.0.0.1:{server.server_port}/')
            top=validate(read(),'Linux','Google Chrome','120')
            check(top['high']['architecture']=='x86' and top['high']['bitness']=='64' and top['high']['uaFullVersion']=='120.0.0.0','Linux high entropy',top)
            # Both same-origin and cross-origin frames execute the predicate immediately.
            for host in ['127.0.0.1','localhost']:
                driver.execute_script("const f=document.createElement('iframe');f.src=arguments[0];document.body.appendChild(f)",f'http://{host}:{server.server_port}/frame')
                driver.switch_to.frame(driver.find_elements('tag name','iframe')[-1]);r=read();driver.switch_to.default_content()
                check(r['low']==top['low'] and r['gate'],'frame identity '+host,r)
            for kind in ['dedicated','shared','service']:
                script="""const [kind,done]=arguments;(async()=>{
                        if(kind==='dedicated'){const w=new Worker('/worker.js');w.onmessage=e=>{w.terminate();done(e.data)};w.onerror=e=>done({error:e.message});w.postMessage('report')}
                        if(kind==='shared'){const w=new SharedWorker('/shared.js');w.port.onmessage=e=>{w.port.close();done(e.data)};w.onerror=e=>done({error:e.message});w.port.start();w.port.postMessage('report')}
                        if(kind==='service'){const reg=await navigator.serviceWorker.register('/service.js');await navigator.serviceWorker.ready;const w=reg.active;const c=new MessageChannel();c.port1.onmessage=async e=>{await reg.unregister();done(e.data)};w.postMessage('report',[c.port2])}
                    })().catch(e=>done({error:String(e)}));"""
                r=driver.execute_async_script(script,kind)
                check(r.get('low')==top['low'] and r.get('high')==top['high'] and r.get('gate'),'worker identity '+kind,r)
            set_identity(EDGE,2)
            handles=set(driver.window_handles)
            chrome(driver,"const t=gBrowser.addTab(arguments[0],{userContextId:2,triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});gBrowser.selectedTab=t;",f'http://127.0.0.1:{server.server_port}/')
            deadline=time.monotonic()+10
            while not(set(driver.window_handles)-handles) and time.monotonic()<deadline:time.sleep(.05)
            driver.switch_to.window((set(driver.window_handles)-handles).pop())
            edge=validate(read(),'Windows','Microsoft Edge','128')
            check(edge['high']['uaFullVersion']=='128.0.2739.79' and {x['brand']:x['version'] for x in edge['high']['fullVersionList']}['Chromium']=='128.0.6613.120','Edge and Chromium full versions',edge)
            for kind in ['dedicated','shared','service']:
                r=driver.execute_async_script(script,kind)
                check(r.get('low')==edge['low'] and r.get('high')==edge['high'],'container worker isolation '+kind,r)
            driver.close();driver.switch_to.window(next(iter(handles)))
            for ua,enabled,label in [(ANDROID,True,'Android'),(FIREFOX,True,'Firefox'),(CHROME,False,'master disabled'),(CHROME.replace('Chrome/120.0.0.0','Chrome/not-a-version'),True,'malformed'),(CHROME.replace('Chrome/','CriOS/'),True,'iOS Chrome')]:
                set_identity(ua,enabled=enabled);driver.get(f'http://127.0.0.1:{server.server_port}/');r=read()
                if label=='Android':validate(r,'Android','Google Chrome','120',True);check(r['high']['model']=='Pixel 8' and r['high']['platformVersion']=='14.0.0','Android model/version',r)
                else:
                    check(not r['present'] and not r['gate'] and r['classType']=='undefined','API absent for '+label,r)
                    if label in ['Firefox','master disabled']:
                        worker=driver.execute_async_script(script,'dedicated')
                        check(not worker.get('present') and worker.get('classType')=='undefined','worker API absent for '+label,worker)

            reduced_android=ANDROID.replace('Android 14; Pixel 8','Android 10; K')
            set_identity(reduced_android);driver.get(f'http://127.0.0.1:{server.server_port}/');r=read()
            check(r['high']['model']=='' and r['high']['platformVersion']=='','reduced Android metadata withheld',r)
            for ua,platform,brand,arch,bits,label in [
                (CHROME.replace('x86_64','aarch64'),'Linux','Google Chrome','arm','64','ARM64'),
                (CHROME.replace('x86_64','armv7l'),'Linux','Google Chrome','arm','32','ARM32'),
                (CHROME.replace('X11; Linux x86_64','Windows NT 10.0; WOW64'),'Windows','Google Chrome','x86','64','WOW64'),
                (CHROME.replace('X11; Linux x86_64','Macintosh; Intel Mac OS X 10_15_7'),'macOS','Google Chrome','','','reduced Mac'),
                (CHROME.replace('Chrome/','Chromium/'),'Linux','Chromium','x86','64','Chromium')]:
                set_identity(ua);driver.get(f'http://127.0.0.1:{server.server_port}/');r=validate(read(),platform,brand,'120')
                check(r['high']['architecture']==arch and r['high']['bitness']==bits,'architecture '+label,r)
                if platform in ['Windows','macOS']:check(r['high']['platformVersion']=='','unknown OS revision withheld '+label,r)
            # Use a fresh browser and explicitly assert context trust rather
            # than assume a data navigation after trusted pages is insecure.
            driver.quit()
            driver=webdriver.Firefox(options=opts,service=Service(executable_path=os.environ.get('GECKODRIVER') or shutil.which('geckodriver'),service_args=['--allow-system-access'],log_output=str(Path(tmp)/'insecure-gecko.log')))
            set_identity(CHROME)
            driver.get('data:text/html,<script>window.result=Promise.resolve({secure:isSecureContext,present:"userAgentData" in navigator})</script>')
            insecure=read()
            check(insecure['secure'] is False and not insecure['present'],'API absent in insecure context',insecure)
            check(driver.execute_script('return typeof NavigatorUAData')=='function','interface remains exposed like Chromium on insecure context',{})
        finally:
            driver.quit();server.shutdown()
            out=Path(os.environ.get('CLOAKFOX_REPORT_DIR',tmp));out.mkdir(parents=True,exist_ok=True);(out/'ua-data.json').write_text(json.dumps(results,indent=2)+'\n')
    print(f'{len(results)} checks passed',flush=True)
if __name__=='__main__':main()
