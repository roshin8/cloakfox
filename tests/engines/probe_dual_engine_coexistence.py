"""Run Gecko 158 and CEF concurrently against one owned origin and private roots."""
import argparse
import http.server
import json
from pathlib import Path
import tempfile
import threading
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engines.shared.persona_config import PersonaStore

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_cef_isolation import Companion


class Fixture(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'<!doctype html><title>Owned dual engine fixture</title><body>Coexistence</body>'
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *_args):
        pass


STATE = """async function state(value){
 const db=await new Promise((resolve,reject)=>{const request=indexedDB.open('dual-engine',1);
 request.onupgradeneeded=()=>request.result.createObjectStore('kv');
 request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error)});
 const read=()=>new Promise((resolve,reject)=>{const r=db.transaction('kv').objectStore('kv').get('marker');r.onsuccess=()=>resolve(r.result||null);r.onerror=()=>reject(r.error)});
 if(value!==null){
 localStorage.setItem('marker',value);document.cookie='marker='+value+';path=/;Max-Age=3600';
 await new Promise((resolve,reject)=>{const t=db.transaction('kv','readwrite');t.objectStore('kv').put(value,'marker');t.oncomplete=resolve;t.onerror=()=>reject(t.error)});
 }
 const c=document.createElement('canvas');c.width=32;c.height=24;const x=c.getContext('2d');
 x.fillStyle='rgb(72,108,144)';x.fillRect(0,0,32,24);let hash=2166136261;
 for(const byte of x.getImageData(0,0,32,24).data)hash=Math.imul(hash^byte,16777619)>>>0;
 const result={local:localStorage.getItem('marker'),cookie:document.cookie,indexed:await read(),canvasHash:hash};db.close();return result;
}"""


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gecko-binary',type=Path,required=True)
    parser.add_argument('--chromium-binary',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--require-pixel-privacy',action='store_true')
    parser.add_argument('--require-persona-config',action='store_true')
    args=parser.parse_args()
    report={'checks':[]}
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Fixture)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{server.server_port}/'
    driver=None;app=None
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-dual-engines-') as folder:
            root=Path(folder);profile=root/'gecko';profile.mkdir()
            chromium_root=root/'chromium';chromium_root.mkdir(mode=0o700)
            store=PersonaStore(chromium_root/'personas')
            def open_cef(container, url, private=False):
                if not args.require_persona_config:return app.open(container,url,private=private)
                config=store.get(container,'chromium',private=private)
                applied=app.rpc('applyConfig',config=config)
                assert applied.get('ok') and applied.get('configRevision')==config['revision'],applied
                browser=app.open(container,url,private=private,configRevision=config['revision'])
                report['versionedConfigVerified']=True
                return browser
            options=Options();options.binary_location=str(args.gecko_binary.resolve())
            options.set_preference('cloakfox.enabled',True)
            for arg in ('-headless','-no-remote','-purgecaches','-profile',str(profile)):
                options.add_argument(arg)
            driver=webdriver.Firefox(options=options,service=Service(service_args=['--allow-system-access'],log_output=str(root/'geckodriver.log')))
            driver.set_script_timeout(20)
            driver.set_context('chrome')
            try:info=driver.execute_script('return {version:Services.appinfo.version,buildID:Services.appinfo.appBuildID,cloakfoxEnabled:Services.prefs.getBoolPref("cloakfox.enabled"),resistFingerprinting:Services.prefs.getBoolPref("privacy.resistFingerprinting")}')
            finally:driver.set_context('content')
            assert info['version'].startswith('158.'),info
            assert info['cloakfoxEnabled'] is True and info['resistFingerprinting'] is False,info
            report['gecko']=info
            app=Companion(args.chromium_binary.resolve(),chromium_root)
            report['chromium']=app.ready
            if args.require_pixel_privacy:assert app.ready.get('webgpuPixelReadbackVersion')==1,app.ready
            driver.get(url)
            def gecko(value=None):
                return driver.execute_async_script(STATE+'state(arguments[0]).then(arguments[arguments.length-1],e=>arguments[arguments.length-1]({error:String(e)}))',value)
            def cef(browser,value=None):
                return app.evaluate(browser,'(async()=>{'+STATE+'return state('+json.dumps(value)+')})()')
            def exact(record,marker):
                assert 'error' not in record,record
                assert record['local']==record['indexed']==marker,record
                assert record['cookie']==('marker='+marker if marker else ''),record
                assert record['canvasHash']>0,record
                if args.require_pixel_privacy:
                    raw=2166136261
                    for byte in [72,108,144,255]*(32*24):raw=((raw^byte)*16777619)&0xffffffff
                    assert record['canvasHash']!=raw,('Native canvas protection inactive',record)
            exact(gecko(),None)
            first=open_cef('1',url);second=open_cef('2',url)
            for browser in (first,second):exact(cef(browser),None)
            a=gecko('gecko158');b=cef(first,'chromium1');c=cef(second,'chromium2')
            exact(a,'gecko158');exact(b,'chromium1');exact(c,'chromium2')
            driver.refresh();assert gecko()==a
            assert cef(first)==b and cef(second)==c
            report['checks'].append('Concurrent same-origin cookies/localStorage/IndexedDB stay engine- and container-owned; canvas reads stable')
            private=open_cef('1',url,private=True);exact(cef(private),None);exact(cef(private,'private1'),'private1')
            assert app.rpc('close',browser=private)['ok'];app.wait(lambda x:x.get('event')=='closed' and x.get('browser')==private)
            store.forget_private('1','chromium')
            private=open_cef('1',url,private=True);exact(cef(private),None)
            exact(gecko(),'gecko158');exact(cef(first),'chromium1')
            report['checks'].append('Private Chromium destruction/regeneration does not alter persistent Gecko/Chromium state')
            app.close();app=None
            driver.refresh();assert gecko()==a
            report['checks'].append('Gecko remains usable after companion shutdown')
            app=Companion(args.chromium_binary.resolve(),chromium_root);first=open_cef('1',url)
            assert cef(first)==b
            driver.quit();driver=None
            assert cef(first)==b
            report['checks'].append('Companion restart preserves its own state and remains usable after Gecko shutdown')
            app.close();app=None
        report['status']='passed'
    finally:
        try:
            if app:app.close()
        finally:
            try:
                if driver:driver.quit()
            finally:
                server.shutdown();server.server_close()
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
