"""Real native profile enforcement across BrowserForge families and owners.

Disposable local profiles; native hardware subcases are inconclusive headless. No camera/screen grants or assessment.
"""
import functools
import hashlib
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_container_workflows import chrome,open_site
from probe_canvas_canonical_gpu import headless_webgpu_unavailable
from probe_webgl_backend_profile import INSPECT,READBACK,WORKER_RUN,WORKER_SOURCE

HTML=b'<!doctype html><title>Native container GPU profile test</title>'
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  body=WORKER_SOURCE.encode() if self.path.startswith('/worker.js') else HTML
  self.send_response(200);self.send_header('Content-Type','text/javascript' if self.path.startswith('/worker.js') else 'text/html');self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass
READ=INSPECT+"return ['webgl','webgl2'].map(k=>{const g=document.createElement('canvas').getContext(k),v=inspect(g);if(g)g.getExtension('WEBGL_lose_context')?.loseContext();return v;});"
GPU=r'''const done=arguments[arguments.length-1];(async()=>{
 if(!navigator.gpu)return {available:false,reason:'navigator.gpu absent'};const a=await navigator.gpu.requestAdapter();if(!a)return {available:false,reason:'no adapter'};
 const cap=a.limits.maxBufferSize;let aboveRejected=false;try{const d=await a.requestDevice({requiredLimits:{maxBufferSize:cap+1}});d.destroy()}catch{aboveRejected=true;}
 const d=await a.requestDevice({requiredLimits:{maxBufferSize:cap}});d.pushErrorScope('validation');d.createBuffer({size:cap+4,usage:GPUBufferUsage.COPY_DST});const allocationError=await d.popErrorScope();
 const info=a.info;const r={available:true,maxBufferSize:cap,deviceBufferSize:d.limits.maxBufferSize,aboveRejected,allocationRejected:!!allocationError,info:[info.vendor,info.architecture,info.description,info.device]};d.destroy();return r;
})().then(done,e=>done({error:String(e),stack:e.stack}));'''

def main():
 out=Path(os.environ.get('REPORT_DIR','/tmp/cfx-container-gpu-profiles'));out.mkdir(parents=True,exist_ok=True)
 binary=os.environ['CLOAKFOX_BIN'];report={'binary':binary,'xulSHA256':hashlib.sha256((Path(binary).parent/'XUL').read_bytes()).hexdigest(),'checks':[],'cases':[],'inconclusive':[]}
 server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 def check(ok,name):report['checks'].append({'pass':bool(ok),'name':name});print(('PASS 'if ok else'FAIL ')+name,flush=True)
 def gpu_check(ok,value,name):
  if headless_webgpu_unavailable(value,report['nativeWebGPU']):
   report['inconclusive'].append({'name':name,'reason':'No headless native WebGPU adapter'})
   print('INCONCLUSIVE '+name,flush=True)
  else:check(ok,name)
 def save():(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 try:
  with tempfile.TemporaryDirectory(prefix='cfx-native-profiles-')as profile:
   options=Options();options.binary_location=binary
   for arg in ['-profile',profile,'-purgecaches']:options.add_argument(arg)
   options.set_preference('cloakfox.enabled',True);options.set_preference('cloakfox.experimental.canvas_pipeline',True);options.set_preference('dom.webgpu.enabled',True)
   d=webdriver.Firefox(options=options,service=Service('/opt/homebrew/bin/geckodriver',service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
   try:
    d.set_script_timeout(45)
    report['runtime']=chrome(d,'return {version:Services.appinfo.version,buildID:Services.appinfo.appBuildID};')
    chrome(d,"Services.prefs.setBoolPref('cloakfox.enabled',false);")
    d.set_context('content');d.get(f'http://127.0.0.1:{server.server_port}/native-control')
    report['nativeWebGPU']=d.execute_async_script(GPU)
    chrome(d,"Services.prefs.setBoolPref('cloakfox.enabled',true);")
    families=[('apple','macos',6144),('intel','windows',4096),('amd','windows',7168),('nvidia','windows',8192)]
    ids=chrome(d,"return Array.from({length:8},(_,i)=>cis.create('Native profile '+i,'fingerprint','blue').userContextId);")
    # Make every existing disposable owner eligible without rotating its secrets.
    chrome(d,"""const p=ChromeUtils.importESModule('resource:///modules/CloakfoxPersonas.sys.mjs');for(const key of Services.prefs.getChildList('cloakfox.s.cloak_cfg_')){const id=Number(key.slice('cloakfox.s.cloak_cfg_'.length));const c=JSON.parse(Services.prefs.getStringPref(key)),next=p.fillPersonaKeys('B'.repeat(43)+'=',id,{os:'windows',hardware:'nvidia'});for(const [k,v]of Object.entries(c))if(/seed|secret/i.test(k))next[k]=v;next['navigator:webgpu:disabled']=false;Services.prefs.setStringPref(key,JSON.stringify(next));}""")
    # Production activation preflights all owners and emits owned descriptors.
    chrome(d,"ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs').setContainerGPUProfilesEnabled(true);")
    for index,(family,os_name,texture)in enumerate(families):
     pair=[]
     for offset in range(2):
      ucid=ids[index*2+offset];url=f'http://127.0.0.1:{server.server_port}/?owner={ucid}'
      _,actual=open_site(d,url,ucid);check(actual==ucid,f'{family}/{offset}: actual container owner')
      cfg=chrome(d,"""const id=arguments[0],p=ChromeUtils.importESModule('resource:///modules/CloakfoxPersonas.sys.mjs'),o=ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs'),old=JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+id)),next=p.fillPersonaKeys('B'.repeat(43)+'=',id,{os:arguments[1],hardware:arguments[2]});for(const [k,v]of Object.entries(old))if(/seed|secret/i.test(k))next[k]=v;next['navigator:webgpu:disabled']=false;const cfg=o.applyGraphicsPolicy(next,id);Services.prefs.setStringPref('cloakfox.s.cloak_cfg_'+id,JSON.stringify(cfg));return cfg;""",ucid,os_name,family)
      d.set_context('content');d.refresh();samples=[]
      for host in ['127.0.0.1','localhost','127.0.0.1']:
       d.get(f'http://{host}:{server.server_port}/?owner={ucid}');gl=d.execute_script(READ);gpu=d.execute_async_script(GPU);samples.append({'host':host,'gl':gl,'webgpu':gpu})
       for g in gl:
        kind='GL2'if g.get('gl2')else'GL1';prefix=f'{family}/{offset}/{host}/{kind}'
        check(not g.get('missing'),prefix+' context exists')
        if g.get('missing'):continue
        check(g['identity'][1]==cfg['webGl:renderer'] and g['identity'][3]==cfg['webGl:renderer'] and g['identity'][2]==cfg['webGl:vendor'],prefix+' identity matches saved BrowserForge persona')
        check(g['caps']['MAX_TEXTURE_SIZE']==texture and g['below']==0 and g['above']==1281 and g['renderbufferAbove']==1281,prefix+' actual texture/renderbuffer ceilings enforced')
        check(g['shaderAbove'] is False and g['attribAbove']==1281 and g['textureUnitAbove']==1281,prefix+' actual shader/attribute/unit ceilings enforced')
        check(g['working']==g['extensions'] and g['invalidPrecision'] is None and g['invalidError']==1280,prefix+' extension and precision validation preserved')
       gpu_check(gpu.get('available') and gpu.get('aboveRejected') and gpu.get('allocationRejected') and gpu.get('deviceBufferSize')==gpu.get('maxBufferSize'),gpu,f'{family}/{offset}/{host}: WebGPU adapter/device/buffer limits enforced')
       if gpu.get('available')and not gl[0].get('missing'):check(gpu['maxBufferSize']==gl[0]['caps']['MAX_VERTEX_UNIFORM_VECTORS']*1024*1024,f'{family}/{offset}/{host}: both GPU APIs use same owner/site variant')
      check(samples[0]==samples[2],f'{family}/{offset}: site return restores captured profile')
      worker=d.execute_async_script(WORKER_RUN)
      check(isinstance(worker,list) and len(worker)==2 and all(not g.get('missing')for g in worker) and [(g.get('caps'),g.get('identity'))for g in worker]==[(g.get('caps'),g.get('identity'))for g in samples[2]['gl']],f'{family}/{offset}: worker owns same resource profile')
      strict=d.execute_script(READBACK);check(strict.get('integerError')==1282 and strict.get('pboError')==1282 and strict.get('integer')==[88]*16,f'{family}/{offset}: existing precise/PBO readback guards retained')
      row={'family':family,'owner':ucid,'descriptor':cfg['rendering:gpu_profile'],'samples':samples,'worker':worker,'strict':strict};report['cases'].append(row);pair.append(row);save()
     check(pair[0]['descriptor']['owner']!=pair[1]['descriptor']['owner'] and pair[0]['descriptor']['renderer']==pair[1]['descriptor']['renderer'],family+': identical personas have distinct owned descriptors')
    # Existing live contexts retain their captured policy after settings change.
    d.set_context('content')
    frozen=d.execute_script("window.heldGL=document.createElement('canvas').getContext('webgl');const x=heldGL.getExtension('WEBGL_debug_renderer_info');return [heldGL.getParameter(x.UNMASKED_RENDERER_WEBGL),heldGL.getParameter(3379),heldGL.getParameter(36347)];")
    original=chrome(d,"const k='cloakfox.s.cloak_cfg_'+arguments[0],c=JSON.parse(Services.prefs.getStringPref(k));const before=JSON.stringify(c);c['webGl:renderer']='Intel UHD Graphics';c['webGl:vendor']='Intel';c['rendering:gpu_profile']=ChromeUtils.importESModule('resource:///modules/CloakfoxGPUProfiles.sys.mjs').createGPUProfile(c,arguments[0]);Services.prefs.setStringPref(k,JSON.stringify(c));return before;",ids[-1])
    d.set_context('content');after=d.execute_script("const x=heldGL.getExtension('WEBGL_debug_renderer_info');return [heldGL.getParameter(x.UNMASKED_RENDERER_WEBGL),heldGL.getParameter(3379),heldGL.getParameter(36347)];")
    check(frozen==after,'live WebGL context retains captured identity and resource limits')
    restoredContext=d.execute_async_script("""const done=arguments[arguments.length-1],gl=heldGL,ext=gl.getExtension('WEBGL_lose_context');gl.canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();setTimeout(()=>ext.restoreContext(),50)},{once:true});gl.canvas.addEventListener('webglcontextrestored',()=>{const x=gl.getExtension('WEBGL_debug_renderer_info');done([gl.getParameter(x.UNMASKED_RENDERER_WEBGL),gl.getParameter(3379),gl.getParameter(36347)]);},{once:true});ext.loseContext();setTimeout(()=>done({timeout:true}),5000);""")
    check(restoredContext==frozen,'restored WebGL context enforces original captured profile after settings change')
    chrome(d,"Services.prefs.setStringPref('cloakfox.s.cloak_cfg_'+arguments[0],arguments[1]);",ids[-1],original)
    # A canvas readout exception cannot invalidate GPU resource ownership.
    owner=ids[-1]
    chrome(d,"const k='cloakfox.s.cloak_cfg_'+arguments[0],c=JSON.parse(Services.prefs.getStringPref(k));c['privacy:policy']={version:1,preset:'standard',exceptions:[{site:'http://127.0.0.1',expiresAt:Date.now()+600000,vectors:['canvas']}]};Services.prefs.setStringPref(k,JSON.stringify(c));",owner)
    d.set_context('content');d.refresh();exempt=d.execute_script(READ);exemptgpu=d.execute_async_script(GPU)
    check(all(not g.get('missing')for g in exempt),'canvas exception preserves native WebGL profile creation')
    gpu_check(exemptgpu.get('available'),exemptgpu,'canvas exception preserves native WebGPU profile creation')
    # New contexts must fail closed on an incorrect owner, not use ctx0/native.
    owner=ids[-1];chrome(d,"const k='cloakfox.s.cloak_cfg_'+arguments[0],c=JSON.parse(Services.prefs.getStringPref(k));c['rendering:gpu_profile'].owner=0;Services.prefs.setStringPref(k,JSON.stringify(c));",owner)
    d.set_context('content');d.refresh();missing=d.execute_script("return document.createElement('canvas').getContext('webgl')===null;");gpu=d.execute_async_script(GPU);check(missing,'wrong-owner descriptor fails closed in WebGL')
    gpu_check(gpu.get('available')is False,gpu,'wrong-owner descriptor fails closed in WebGPU')
    chrome(d,"ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs').setContainerGPUProfilesEnabled(false);")
    d.set_context('content');d.refresh();legacy=d.execute_script(READ);check(all(g.get('identity',[None,None])[1]=='WebGL'for g in legacy),'toggle off restores existing protected generic profile')
    # Reopen the same disposable profile; do not regenerate its persona or keys.
    chrome(d,"ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs').setContainerGPUProfilesEnabled(true);")
    saved=chrome(d,"return JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+arguments[0]));",ids[0])
    d.quit()
    d=webdriver.Firefox(options=options,service=Service('/opt/homebrew/bin/geckodriver',service_args=['--allow-system-access'],log_output=str(out/'restart-gecko.log')))
    d.set_script_timeout(45)
    _,actual=open_site(d,f'http://127.0.0.1:{server.server_port}/?owner={ids[0]}',ids[0]);d.set_context('content')
    restored=d.execute_script(READ);restoredgpu=d.execute_async_script(GPU)
    persisted=chrome(d,"return {enabled:Services.prefs.getBoolPref('cloakfox.opt.container_rendering_profiles',false),cfg:JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+arguments[0]))};",ids[0])
    check(actual==ids[0] and persisted['enabled'] and persisted['cfg']['rendering:gpu_profile']==saved['rendering:gpu_profile'] and persisted['cfg']['fingerprint:secret']==saved['fingerprint:secret'],'profile toggle, owner, persona and secret persist across restart')
    check(restored==report['cases'][0]['samples'][0]['gl'],'native WebGL resources retain same owner/site profile across restart')
    gpu_check(restoredgpu==report['cases'][0]['samples'][0]['webgpu'],restoredgpu,'native WebGPU resources retain same owner/site profile across restart')
   finally:d.quit()
 finally:server.shutdown();server.server_close();save()
 if any(not c['pass']for c in report['checks']):return 1
 return 2 if report['inconclusive'] else 0
if __name__=='__main__':raise SystemExit(main())
