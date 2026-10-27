"""Use real cross-site transferred OffscreenCanvas and canonical GPU devices."""
import json,os,tempfile,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from probe_container_workflows import chrome
from probe_canvas_canonical_gpu import headless_webgpu_unavailable
class Page(BaseHTTPRequestHandler):
 def do_GET(self):
  b=b'<!doctype html><title>WebGPU owner boundary</title>'
  self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(b)
 def log_message(self,*_):pass
CHECK=r'''async function configure(c){if(!navigator.gpu)return {available:false,reason:'navigator.gpu absent'};const a=await navigator.gpu.requestAdapter();if(!a)return {unavailable:true,available:false,reason:'no adapter'};const d=await a.requestDevice();try{const x=c.getContext('webgpu');x.configure({device:d,format:'bgra8unorm'});const t=x.getCurrentTexture();return{configured:!!t}}catch(e){return{configured:false,name:e.name,message:e.message}}finally{d.destroy()}}'''
WORKER=r'''const done=arguments[arguments.length-1];const source=arguments[0];const w=new Worker(URL.createObjectURL(new Blob([source+';onmessage=e=>configure(e.data).then(postMessage,e=>postMessage({error:String(e)}))'],{type:'text/javascript'})));const c=new OffscreenCanvas(16,16);w.onmessage=e=>{w.terminate();done(e.data)};w.onerror=e=>done({error:e.message});w.postMessage(c,[c]);'''
def main():
 out=Path(os.environ.get('REPORT_DIR','/tmp/cfx-gpu-owner'));out.mkdir(parents=True,exist_ok=True);report={'binary':os.environ['CLOAKFOX_BIN'],'checks':[],'cases':[],'inconclusive':[]}
 def check(ok,name):report['checks'].append({'pass':bool(ok),'name':name});print(('PASS 'if ok else'FAIL ')+name,flush=True)
 def gpu_check(ok,value,name):
  if headless_webgpu_unavailable(value,report['nativeWebGPU']):
   report['inconclusive'].append({'name':name,'reason':'No headless native WebGPU adapter'})
   print('INCONCLUSIVE '+name,flush=True)
  else:check(ok,name)
 server=ThreadingHTTPServer(('127.0.0.1',0),Page);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with tempfile.TemporaryDirectory(prefix='cfx-gpu-owner-')as profile:
   o=Options();o.binary_location=report['binary']
   for a in ['-profile',profile,'-purgecaches']:o.add_argument(a)
   o.set_preference('dom.webgpu.enabled',True);o.set_preference('dom.disable_open_during_load',False);o.set_preference('privacy.resistFingerprinting',False)
   d=webdriver.Firefox(options=o,service=Service('/opt/homebrew/bin/geckodriver',service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
   try:
    d.set_script_timeout(30);report['runtime']=chrome(d,'return {buildID:Services.appinfo.appBuildID,version:Services.appinfo.version};')
    chrome(d,"const p=ChromeUtils.importESModule('resource:///modules/CloakfoxPersonas.sys.mjs');for(const k of Services.prefs.getChildList('cloakfox.s.cloak_cfg_')){const id=Number(k.slice('cloakfox.s.cloak_cfg_'.length)),old=JSON.parse(Services.prefs.getStringPref(k)),c=p.fillPersonaKeys('B'.repeat(43)+'=',id,{os:'windows',hardware:'nvidia'});for(const [k,v]of Object.entries(old))if(/seed|secret/i.test(k))c[k]=v;c['navigator:webgpu:disabled']=false;Services.prefs.setStringPref(k,JSON.stringify(c));}")
    chrome(d,"Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',true);ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs').setContainerGPUProfilesEnabled(true);")
    chrome(d,"Services.prefs.setBoolPref('cloakfox.enabled',false);")
    d.set_context('content');d.get(f'http://127.0.0.1:{server.server_port}/native-control')
    report['nativeWebGPU']=d.execute_async_script(CHECK+"const done=arguments[arguments.length-1];configure(new OffscreenCanvas(16,16)).then(done);")
    for enabled in [True,False]:
     chrome(d,"Services.prefs.setBoolPref('cloakfox.enabled',arguments[0]);",enabled)
     d.set_context('content');d.get(f'http://127.0.0.1:{server.server_port}/');sender=d.current_window_handle
     own=d.execute_async_script(CHECK+"const done=arguments[arguments.length-1];configure(new OffscreenCanvas(16,16)).then(done);")
     gpu_check(own.get('configured'),own,f'master{enabled}: same-owner canvas/device configures')
     worker=d.execute_async_script(WORKER,CHECK);gpu_check(worker.get('configured'),worker,f'master{enabled}: same-owner worker canvas/device configures')
     before=set(d.window_handles);d.execute_script("window.receiver=window.open(arguments[0],'owner-receiver');",f'http://localhost:{server.server_port}/')
     child=WebDriverWait(d,15).until(lambda x:next(iter(set(x.window_handles)-before),False));d.switch_to.window(child)
     WebDriverWait(d,15).until(lambda x:x.current_url==f'http://localhost:{server.server_port}/' and x.execute_script('return document.readyState')=='complete')
     d.execute_script(CHECK+"window.transferResult=null;window.onmessageerror=e=>window.transferResult={cloneError:true};window.onmessage=e=>configure(e.data).then(v=>window.transferResult=v,e=>window.transferResult={error:String(e)});")
     d.switch_to.window(sender);d.execute_script("const c=new OffscreenCanvas(16,16);receiver.postMessage(c,arguments[0],[c]);",f'http://localhost:{server.server_port}')
     d.switch_to.window(child);result=WebDriverWait(d,25).until(lambda x:x.execute_script('return window.transferResult'))
     if result.get('cloneError'):
      check(True,f'master{enabled}: platform refuses cross-process OffscreenCanvas transfer before configure')
     else:
      gpu_check(result.get('name')=='InvalidStateError'if enabled else result.get('configured'),result,f'master{enabled}: cross-site canvas/device '+('rejected'if enabled else'native behavior retained'))
     report['cases'].append({'master':enabled,'sameOwner':own,'worker':worker,'crossSite':result});d.close();d.switch_to.window(sender)
     # Same-process transfer after identity rotation reaches the native owner
     # comparison even where Gecko forbids cross-process canvas transfers.
     d.execute_script('window.pendingCanvas=new OffscreenCanvas(16,16);')
     chrome(d,"const k='cloakfox.s.cloak_cfg_0',c=JSON.parse(Services.prefs.getStringPref(k));c['canvas:seed']=(c['canvas:seed']+1)>>>0;Services.prefs.setStringPref(k,JSON.stringify(c));")
     d.set_context('content');before=set(d.window_handles);target=f'http://127.0.0.1:{server.server_port}/?new-owner=1'
     d.execute_script("window.receiver=window.open(arguments[0],'new-owner');",target)
     child=WebDriverWait(d,15).until(lambda x:next(iter(set(x.window_handles)-before),False));d.switch_to.window(child)
     WebDriverWait(d,15).until(lambda x:x.current_url==target and x.execute_script('return document.readyState')=='complete')
     d.execute_script(CHECK+"window.transferResult=null;window.onmessageerror=e=>window.transferResult={cloneError:true};window.onmessage=e=>configure(e.data).then(v=>window.transferResult=v,e=>window.transferResult={error:String(e)});")
     d.switch_to.window(sender);d.execute_script("receiver.postMessage(pendingCanvas,location.origin,[pendingCanvas]);")
     d.switch_to.window(child);rotated=WebDriverWait(d,25).until(lambda x:x.execute_script('return window.transferResult'))
     gpu_check(rotated.get('name')=='InvalidStateError'if enabled else rotated.get('configured'),rotated,f'master{enabled}: transferred stale-owner canvas '+('rejected by configure'if enabled else'native behavior retained'))
     report['cases'][-1]['rotatedOwner']=rotated;d.close();d.switch_to.window(sender)
   finally:d.quit()
 finally:server.shutdown();(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 if any(not c['pass']for c in report['checks']):return 1
 return 2 if report['inconclusive'] else 0
if __name__=='__main__':raise SystemExit(main())
