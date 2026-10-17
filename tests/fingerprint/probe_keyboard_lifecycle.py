"""Retained EventTarget methods must survive their source frame's destruction.

Local fixtures, disposable profile, installed binary by default. Does not contact
AA or alter personal profiles. Asserts recipient event delivery and cadence.
"""
import json
import os
import shutil
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

SCRIPT = r"""
const done=arguments[0];
(async()=>{
 const frame=document.createElement('iframe');frame.src='/frame';
 await new Promise(resolve=>{frame.onload=resolve;document.body.append(frame)});
 const add=frame.contentWindow.EventTarget.prototype.addEventListener;
 const remove=frame.contentWindow.EventTarget.prototype.removeEventListener;
 let existing=0;const pre=()=>existing++;
 add.call(document,'keydown',pre);
 frame.remove();
 await new Promise(resolve=>setTimeout(resolve,50));
 const results=[];
 const test=(name,fn)=>{try{results.push({name,...fn()})}catch(e){results.push({name,pass:false,error:String(e)})}};
 test('existing listener after source frame removal',()=>{
   document.dispatchEvent(new KeyboardEvent('keydown'));
   return {pass:existing===1,existing};
 });
 test('borrowed non-key add/remove after source frame removal',()=>{
   let calls=0;const fn=()=>calls++;
   add.call(document,'lifecycle-check',fn);document.dispatchEvent(new Event('lifecycle-check'));
   remove.call(document,'lifecycle-check',fn);document.dispatchEvent(new Event('lifecycle-check'));
   return {pass:calls===1,calls};
 });
 test('borrowed methods support Window, element and standalone EventTarget',()=>{
   const counts=[];
   for(const target of [window,document.createElement('div'),new EventTarget()]){
     let calls=0;const listener={handleEvent(){calls++}};
     add.call(target,'keydown',listener);target.dispatchEvent(new KeyboardEvent('keydown'));
     remove.call(target,'keydown',listener);target.dispatchEvent(new KeyboardEvent('keydown'));
     counts.push(calls);
   }
   return {pass:counts.every(n=>n===1),counts};
 });
 test('invalid receivers still throw',()=>{
   const errors=[];
   for(const fn of [add,remove])for(const receiver of [{},42]){
     try{fn.call(receiver,'keydown',()=>{});errors.push(false)}catch(e){errors.push(true)}
   }
   return {pass:errors.every(Boolean),errors};
 });
 test('borrowed key add/remove retains recipient cadence',()=>{
   const target=new EventTarget();const stamps=[];const raw=[];const own=[];const fn=e=>{stamps.push(e.timeStamp);own.push(Object.hasOwn(e,'timeStamp'))};
   add.call(target,'keydown',fn);
   for(let i=0;i<4;i++){const e=new KeyboardEvent('keydown');raw.push(e.timeStamp);target.dispatchEvent(e)}
   remove.call(target,'keydown',fn);target.dispatchEvent(new KeyboardEvent('keydown'));
   const bumped=stamps.filter((stamp,i)=>stamp-raw[i]>=20).length;
   return {pass:stamps.length===4&&!own.some(Boolean)&&bumped>=3,stamps,raw,own,bumped};
 });
 test('borrowed remove clears registration made before removal',()=>{
   const before=existing;remove.call(document,'keydown',pre);
   document.dispatchEvent(new KeyboardEvent('keydown'));
   return {pass:existing===before,existing,before};
 });
 const nav=document.createElement('iframe');nav.src='/frame';
 await new Promise(resolve=>{nav.onload=resolve;document.body.append(nav)});
 const oldDoc=nav.contentDocument, OldKeyboardEvent=nav.contentWindow.KeyboardEvent;
 let retained=0;const oldListener=()=>retained++;
 oldDoc.addEventListener('keydown',oldListener);
 nav.src='/frame?new=1';await new Promise(resolve=>nav.onload=resolve);
 test('retained document listener removal after same-origin navigation',()=>{
   oldDoc.removeEventListener('keydown',oldListener);
   oldDoc.dispatchEvent(new OldKeyboardEvent('keydown'));
   return {pass:retained===0,retained};
 });
 nav.remove();
 done(results);
})().catch(e=>done([{name:'fixture',pass:false,error:String(e)}]));
"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers()
        self.wfile.write(b'<!doctype html><title>Keyboard lifecycle</title><body>Local fixture</body>')
    def log_message(self,*args): pass

def main():
    out=Path(os.environ.get('REPORT_DIR','/tmp/cloakfox-keyboard-lifecycle'));out.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='cfx-keyboard-lifecycle-') as profile:
            options=Options();options.binary_location=os.environ.get('CLOAKFOX_BIN','/Applications/Cloakfox.app/Contents/MacOS/cloakfox')
            for arg in ('--headless','-no-remote','-purgecaches','-profile',profile):options.add_argument(arg)
            options.accept_insecure_certs=False
            options.set_preference('remote.prefs.recommended',False)
            options.set_preference('cloakfox.enabled',True)
            options.set_preference('cloakfox.appearance.firefox',False)
            driver=webdriver.Firefox(options=options,service=Service(shutil.which('geckodriver'),service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
            try:
                driver.set_context('chrome')
                runtime=driver.execute_script("return {enabled:Services.prefs.getBoolPref('cloakfox.enabled'),build:Services.appinfo.appBuildID}")
                assert runtime['enabled'] is True,runtime
                driver.set_context('content');driver.get(f'http://127.0.0.1:{server.server_port}/')
                results=driver.execute_async_script(SCRIPT)
                report={'runtime':runtime,'checks':results};(out/'result.json').write_text(json.dumps(report,indent=2))
                print(json.dumps(report,indent=2),flush=True)
                assert all(r['pass'] for r in results),'keyboard lifecycle regression'
            finally:driver.quit()
    finally:server.shutdown();server.server_close()

if __name__=='__main__':main()
