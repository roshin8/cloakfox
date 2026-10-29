#!/usr/bin/env python3
"""Loopback system/opaque-principal locale scope and live-cache regression."""
from __future__ import annotations
import json
import os
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from probe_focus_masking import chrome,set_pref

CHILD=r'''<!doctype html><script>
const first=navigator.languages;
function capture(){parent.postMessage({localeScope:true,language:navigator.language,
 languages:Array.from(navigator.languages),frozen:Object.isFrozen(navigator.languages),
 stable:navigator.languages===navigator.languages,sameFirst:navigator.languages===first},'*')}
addEventListener('message',capture);addEventListener('languagechange',capture);capture();
</script>'''
PAGE='<!doctype html><script>window.localeReplies=[];addEventListener("message",e=>{if(e.data.localeScope)localeReplies.push(e.data)});const f=document.createElement("iframe");f.sandbox="allow-scripts";f.srcdoc='+json.dumps(CHILD).replace('</','<\\/')+';document.documentElement.append(f);</script>'

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body=PAGE.encode();self.send_response(200);self.send_header('Content-Type','text/html')
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*_):pass

def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    report=Path(os.environ.get('REPORT_DIR') or tempfile.mkdtemp(prefix='cloakfox-language-scopes-'))
    report.mkdir(parents=True,exist_ok=True);checks=[];observations={}
    def check(ok,label,data=None):
        checks.append({'pass':bool(ok),'label':label,'data':data});print(('PASS ' if ok else 'FAIL ')+label,flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-language-scopes-profile-') as tmp:
            profile=Path(tmp,'profile');profile.mkdir()
            (profile/'user.js').write_text('user_pref("cloakfox.enabled",false);\n')
            (profile/'locale-scope-worker.js').write_text('postMessage({language:navigator.language,languages:Array.from(navigator.languages),gpuType:typeof navigator.gpu});')
            options=Options();options.binary_location=os.environ['CLOAKFOX_BIN']
            for option in ['-headless','-purgecaches','-profile',str(profile)]:options.add_argument(option)
            driver=webdriver.Firefox(options=options,service=Service(service_args=['--allow-system-access'],log_output=str(report/'gecko.log')))
            driver.set_script_timeout(15)
            observations['browserInfo']=chrome(driver,'return {version:Services.appinfo.version,buildID:Services.appinfo.appBuildID}')
            assert observations['browserInfo']['version'].startswith('159.'),observations['browserInfo']
            chrome(driver,'''const {FileUtils}=ChromeUtils.importESModule('resource://gre/modules/FileUtils.sys.mjs');
              const handler=Services.io.getProtocolHandler('resource').QueryInterface(Ci.nsIResProtocolHandler);
              handler.setSubstitution('locale-scope-fixture',Services.io.newFileURI(new FileUtils.File(arguments[0])));
            ''',str(profile))
            def system():
                driver.get('about:support')
                check(chrome(driver,'return gBrowser.selectedBrowser.browsingContext.currentWindowGlobal.documentPrincipal.isSystemPrincipal'),'about:support has system principal')
                return driver.execute_script('return {language:navigator.language,languages:Array.from(navigator.languages),frozen:Object.isFrozen(navigator.languages),stable:navigator.languages===navigator.languages,webdriver:navigator.webdriver,gpuType:typeof navigator.gpu,gpuSame:navigator.gpu===navigator.gpu,gpuPrototype:!navigator.gpu||Object.getPrototypeOf(navigator.gpu)===GPU.prototype}')
            def opaque():
                return driver.execute_async_script('''const done=arguments[0],old=localeReplies.length;
                  document.querySelector('iframe').contentWindow.postMessage('collect','*');
                  const poll=()=>localeReplies.length>old?done(localeReplies.at(-1)):setTimeout(poll,20);poll();''')
            try:
                native_system=system()
                def chrome_worker():
                    driver.set_context('chrome')
                    try:
                        return driver.execute_async_script("""const done=arguments[0];
                          const w=new ChromeWorker('resource://locale-scope-fixture/locale-scope-worker.js');
                          w.onmessage=e=>{w.terminate();done(e.data)};w.onerror=e=>{w.terminate();done({error:e.message})};
                        """)
                    finally:driver.set_context('content')
                native_worker=chrome_worker()
                check('error' not in native_worker,'system ChromeWorker can report native controls',native_worker)
                driver.get(f'http://127.0.0.1:{server.server_port}/')
                WebDriverWait(driver,10).until(lambda d:d.execute_script('return localeReplies.length')>0)
                native_opaque=opaque()
                check(chrome(driver,'return gBrowser.selectedBrowser.browsingContext.children[0].currentWindowGlobal.documentPrincipal.isNullPrincipal'),'sandbox frame has genuine opaque principal')
                chrome(driver,"""const key='cloakfox.s.cloak_cfg_0';const cfg=JSON.parse(Services.prefs.getStringPref(key,'{}'));
                  cfg['navigator.language']='de-DE';cfg['headers.Accept-Language']='de-DE,de;q=0.9';cfg['navigator:webgpu:disabled']=true;Services.prefs.setStringPref(key,JSON.stringify(cfg));""")
                set_pref(driver,'cloakfox.enabled',True)
                deadline=time.monotonic()+5
                while True:
                    masked=opaque()
                    if masked['languages']==['de-DE','de'] or time.monotonic()>deadline:break
                    time.sleep(.1)
                check(masked['language']=='de-DE' and masked['languages']==['de-DE','de'],'opaque frame masks host language on live enable',masked)
                check(masked['frozen'] and masked['stable'] and not masked['sameFirst'],'opaque live enable invalidates frozen cache',masked)
                chrome(driver,"""const key='cloakfox.s.cloak_cfg_0';const cfg=JSON.parse(Services.prefs.getStringPref(key));
                  cfg['navigator.language']='fr-FR';cfg['headers.Accept-Language']='fr-FR,fr;q=0.9';Services.prefs.setStringPref(key,JSON.stringify(cfg));""")
                deadline=time.monotonic()+5
                while True:
                    changed=opaque()
                    if changed['languages']==['fr-FR','fr'] or time.monotonic()>deadline:break
                    time.sleep(.1)
                check(changed['language']=='fr-FR' and changed['languages']==['fr-FR','fr'] and changed['frozen'] and changed['stable'],'opaque live config update preserves masking and frozen identity',changed)
                set_pref(driver,'cloakfox.enabled',False)
                deadline=time.monotonic()+5
                while True:
                    restored=opaque()
                    if restored['languages']==native_opaque['languages'] or time.monotonic()>deadline:break
                    time.sleep(.1)
                check(restored['language']==native_opaque['language'] and restored['languages']==native_opaque['languages'],'opaque masteroff restores native language',restored)
                set_pref(driver,'cloakfox.enabled',True)
                masked_system=system()
                check(masked_system==native_system,'system document retains native locale, WebGPU and automation controls under masking',masked_system)
                masked_worker=chrome_worker()
                check(masked_worker==native_worker,'system ChromeWorker retains native locale and GPU controls under masking',masked_worker)
            finally:driver.quit()
    finally:
        server.shutdown();server.server_close()
        (report/'result.json').write_text(json.dumps({'checks':checks,'observations':observations},indent=2)+'\n');print('Report: '+str(report),flush=True)
    if not all(c['pass'] for c in checks):raise SystemExit(1)

if __name__=='__main__':main()
