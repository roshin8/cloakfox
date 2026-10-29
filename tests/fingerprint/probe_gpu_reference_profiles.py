#!/usr/bin/env python3
"""Full native reference-derived GPU probe; run only against the new Firefox159 binary.

Uses a disposable profile and loopback pages. Tests the immutable source-derived
catalog, resource/shader operations, independent owners/sites/workers and captured
context identity. Never changes installed applications or personal profiles.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_container_workflows import chrome, open_site
from probe_webgl_backend_profile import INSPECT, READBACK
from probe_container_gpu_profiles import GPU
ROOT=Path(__file__).resolve().parents[2]
EXECUTION=(ROOT/'tests/fingerprint/observed_gpu_execution.js').read_text()
EXECUTION_WORKER=EXECUTION+'onmessage=()=>postMessage(observedGpuExecution());'
DETAILS=INSPECT+r'''
function captureReference(expected) {
 return ['webgl','webgl2'].map((kind,index)=>{
  const gl=(typeof document==='object'?document.createElement('canvas'):new OffscreenCanvas(8,8)).getContext(kind);
  if(!gl)return {missing:true,kind};
  const result=inspect(gl),context=expected[kind];
  result.allParameters=Object.fromEntries(Object.keys(context.parameters).map(key=>{
   let value=gl.getParameter(Number(key));
   if(ArrayBuffer.isView(value))value=Array.from(value);
   return [key,value];
  }));
  result.defaultSamples=gl.getParameter(gl.SAMPLES);
  result.ranges=[Array.from(gl.getParameter(gl.ALIASED_POINT_SIZE_RANGE)),Array.from(gl.getParameter(gl.ALIASED_LINE_WIDTH_RANGE)),Array.from(gl.getParameter(gl.MAX_VIEWPORT_DIMS))];
  result.privacyDenied=['WEBGL_debug_shaders','EXT_disjoint_timer_query','EXT_disjoint_timer_query_webgl2','WEBGL_provoking_vertex'].map(ext=>gl.getExtension(ext)===null);
  if(index) {
   const clear=()=>{while(gl.getError()){};};
   const rb=gl.createRenderbuffer();gl.bindRenderbuffer(gl.RENDERBUFFER,rb);clear();
   gl.renderbufferStorageMultisample(gl.RENDERBUFFER,result.caps.MAX_SAMPLES,gl.RGBA8,2,2);result.samplesAt=gl.getError();
   gl.renderbufferStorageMultisample(gl.RENDERBUFFER,result.caps.MAX_SAMPLES+1,gl.RGBA8,2,2);result.samplesAbove=gl.getError();
   result.sampleCounts=Array.from(gl.getInternalformatParameter(gl.RENDERBUFFER,gl.RGBA8,gl.SAMPLES));gl.deleteRenderbuffer(rb);
   const buffer=gl.createBuffer();gl.bindBufferBase(gl.UNIFORM_BUFFER,result.caps.MAX_UNIFORM_BUFFER_BINDINGS,buffer);result.uboAbove=gl.getError();gl.deleteBuffer(buffer);
   const tex=gl.createTexture();gl.bindTexture(gl.TEXTURE_3D,tex);clear();gl.texImage3D(gl.TEXTURE_3D,0,gl.RGBA8,1,1,result.caps.MAX_3D_TEXTURE_SIZE+1,0,gl.RGBA,gl.UNSIGNED_BYTE,null);result.texture3dAbove=gl.getError();gl.deleteTexture(tex);
   const array=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D_ARRAY,array);clear();gl.texImage3D(gl.TEXTURE_2D_ARRAY,0,gl.RGBA8,1,1,result.caps.MAX_ARRAY_TEXTURE_LAYERS+1,0,gl.RGBA,gl.UNSIGNED_BYTE,null);result.arrayAbove=gl.getError();gl.deleteTexture(array);
  }
  gl.getExtension('WEBGL_lose_context')?.loseContext();return result;
 });
}
'''
STARTUP_JS=r'''function captureStartup(){return ['webgl','webgl2'].map(kind=>{
 const c=typeof document==='object'?document.createElement('canvas'):new OffscreenCanvas(8,8),g=c.getContext(kind);
 if(!g)return {kind,missing:true};const ext=g.getExtension('WEBGL_debug_renderer_info');
 const p=g.getShaderPrecisionFormat(g.FRAGMENT_SHADER,g.MEDIUM_FLOAT);
 const result={kind,missing:false,identity:ext?[g.getParameter(ext.UNMASKED_VENDOR_WEBGL),g.getParameter(ext.UNMASKED_RENDERER_WEBGL)]:[],texture:g.getParameter(g.MAX_TEXTURE_SIZE),uniforms:g.getParameter(g.MAX_VERTEX_UNIFORM_VECTORS),precision:p?[p.rangeMin,p.rangeMax,p.precision]:null};
 g.getExtension('WEBGL_lose_context')?.loseContext();return result;
});}
function referenceNoise(){
 const c=typeof document==='object'?document.createElement('canvas'):new OffscreenCanvas(16,16);c.width=c.height=16;
 const g=c.getContext('webgl',{antialias:false,preserveDrawingBuffer:true});if(!g)return {missing:true};
 try {
 const shader=(type,source)=>{const s=g.createShader(type);g.shaderSource(s,source);g.compileShader(s);if(!g.getShaderParameter(s,g.COMPILE_STATUS))throw Error(g.getShaderInfoLog(s));return s;};
 const vs=shader(g.VERTEX_SHADER,'attribute vec2 a;varying vec2 uv;void main(){uv=(a+1.)*.5;gl_Position=vec4(a,0.,1.);}');
 const fs=shader(g.FRAGMENT_SHADER,'precision highp float;varying vec2 uv;void main(){gl_FragColor=vec4(.1+.7*uv.x,.15+.65*uv.y,.2+.5*uv.x*uv.y,1.);}');
 const program=g.createProgram();g.attachShader(program,vs);g.attachShader(program,fs);g.linkProgram(program);if(!g.getProgramParameter(program,g.LINK_STATUS))throw Error(g.getProgramInfoLog(program));g.useProgram(program);
 const buffer=g.createBuffer();g.bindBuffer(g.ARRAY_BUFFER,buffer);g.bufferData(g.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),g.STATIC_DRAW);
 const loc=g.getAttribLocation(program,'a');g.enableVertexAttribArray(loc);g.vertexAttribPointer(loc,2,g.FLOAT,false,0,0);g.viewport(0,0,16,16);g.drawArrays(g.TRIANGLES,0,3);g.finish();
 const read=()=>{const data=new Uint8Array(16*16*4);g.readPixels(0,0,16,16,g.RGBA,g.UNSIGNED_BYTE,data);return Array.from(data);};
 const pixels=read(),repeat=read(),error=g.getError();g.deleteBuffer(buffer);g.deleteProgram(program);g.deleteShader(vs);g.deleteShader(fs);return {pixels,repeat,error};
 }catch(error){return {error:String(error)}}finally{g.getExtension('WEBGL_lose_context')?.loseContext();}
}
'''
WORKER=DETAILS+"onmessage=event=>postMessage(captureReference(event.data));"
STARTUP_WORKER=STARTUP_JS+'postMessage({startup:captureStartup(),noise:referenceNoise(),navigator:{platform:navigator.platform,oscpu:navigator.oscpu,hasOscpu:"oscpu" in navigator}});'
STARTUP_RUN=r'''const done=arguments[arguments.length-1],worker=new Worker('/startup-worker.js',{type:arguments[0]||'classic'});const timer=setTimeout(()=>{worker.terminate();done({error:'startup worker timeout'})},30000);worker.onmessage=e=>{clearTimeout(timer);worker.terminate();done(e.data)};worker.onerror=e=>{clearTimeout(timer);worker.terminate();done({error:e.message})};'''
FRAME_RUN=r'''const done=arguments[arguments.length-1],frame=document.createElement('iframe');document.body.append(frame);
try{const snapshot=frame.contentWindow.Function(arguments[0]+';return {startup:captureStartup(),noise:referenceNoise(),navigator:{platform:navigator.platform,oscpu:navigator.oscpu,hasOscpu:"oscpu" in navigator}};')();done(snapshot)}catch(error){done({error:String(error)})}finally{frame.remove();}'''
RESTORE=r'''const done=arguments[arguments.length-1],g=window.held,ext=g.getExtension('WEBGL_lose_context');let finished=false;const timer=setTimeout(()=>finish({error:'context restoration timeout'}),15000);function finish(value){if(finished)return;finished=true;clearTimeout(timer);done(value);}g.canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();setTimeout(()=>ext.restoreContext(),50)},{once:true});g.canvas.addEventListener('webglcontextrestored',()=>{const identity=g.getExtension('WEBGL_debug_renderer_info');finish([g.getParameter(identity.UNMASKED_RENDERER_WEBGL),g.getParameter(3379),g.getParameter(36347),g.getParameter(g.SAMPLES)]);},{once:true});ext.loseContext();'''
WORKER_RUN=r'''const done=arguments[arguments.length-1],worker=new Worker('/worker.js');let timer=setTimeout(()=>{worker.terminate();done({error:'reference worker timeout'})},30000);worker.onmessage=e=>{clearTimeout(timer);worker.terminate();done(e.data)};worker.onerror=e=>{clearTimeout(timer);worker.terminate();done({error:e.message})};worker.postMessage(arguments[0]);'''
# Execute the same native operations before any page actor can patch a blank
# frame, and in both worker loading modes. Readback keeps the exact restrictions
# asserted by the existing window probe.
SCOPED_SOURCE=DETAILS+EXECUTION+'function scopedReadback(){'+READBACK.replace("document.createElement('canvas')", "(typeof document==='object'?document.createElement('canvas'):new OffscreenCanvas(2,2))")+'}'+"function scopedGpu(){return new Promise(done=>{"+GPU.replace('const done=arguments[arguments.length-1];','')+'});}'+"async function scopedCapture(input){return {rows:captureReference(input.contexts),execution:input.observed?observedGpuExecution():null,readback:scopedReadback(),webgpu:await scopedGpu()};}"
SCOPED_WORKER=SCOPED_SOURCE+'onmessage=event=>scopedCapture(event.data).then(value=>postMessage(value),error=>postMessage({error:String(error)}));'
SCOPED_RUN=r'''const done=arguments[arguments.length-1],w=new Worker('/scoped-worker.js',{type:arguments[1]});const timer=setTimeout(()=>{w.terminate();done({error:'scoped worker timeout'})},60000);w.onmessage=e=>{clearTimeout(timer);w.terminate();done(e.data)};w.onerror=e=>{clearTimeout(timer);w.terminate();done({error:e.message})};w.postMessage(arguments[0]);'''
SCOPED_FRAME=r'''const done=arguments[arguments.length-1],frame=document.createElement('iframe');document.body.append(frame);try{frame.contentWindow.Function(arguments[0]+';return scopedCapture;')()(arguments[1]).then(value=>{frame.remove();done(value)},error=>{frame.remove();done({error:String(error)})})}catch(error){frame.remove();done({error:String(error)})}'''
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  body=SCOPED_WORKER.encode() if self.path.startswith('/scoped-worker.js') else EXECUTION_WORKER.encode() if self.path.startswith('/observed-execution.js') else STARTUP_WORKER.encode() if self.path.startswith('/startup-worker.js') else WORKER.encode() if self.path.startswith('/worker.js') else b'<!doctype html><title>Native reference GPU profile probe</title>'
  self.send_response(200);self.send_header('Content-Type','text/javascript' if self.path.startswith(('/worker.js','/startup-worker.js','/observed-execution.js','/scoped-worker.js')) else 'text/html');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass

def main():
 binary=Path(os.environ['CLOAKFOX_BIN']).resolve();out=Path(os.environ.get('REPORT_DIR','/tmp/cloakfox-gpu-reference-159'));out.mkdir(parents=True,exist_ok=True)
 report={'canonicalExportPolicy':'Verified canonical CPU authored pixels may coincide across containers and sites. Separate records, secrets, captured contexts and ownership guards remain required. Existing noncanonical fallback noise is tested separately with reference/pipeline off.', 'binary':str(binary),'xulSHA256':hashlib.sha256((binary.parent/'XUL').read_bytes()).hexdigest(),'checks':[],'cases':[],'inconclusive':[]}
 observed_mode=os.environ.get('OBSERVED_GPU_MODE','0')=='1'
 catalog=json.loads((ROOT/'additions/cloakcfg/gpu-reference-executable.json').read_text())
 profiles=catalog['observedProfiles' if observed_mode else 'profiles']
 report['observedMode']=observed_mode
 server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 def check(ok,name):report['checks'].append({'name':name,'pass':bool(ok)});print(('PASS ' if ok else 'FAIL ')+name,flush=True)
 def save():(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 def startup_valid(value,profile):
  return isinstance(value,list) and len(value)==2 and all(not row.get('missing') and row.get('identity')==[profile['vendor'],profile['renderer']] and row.get('texture')==profile['contexts'][row['kind']]['parameters']['3379']['value'] and row.get('uniforms')==profile['contexts'][row['kind']]['parameters']['36347']['value'] and row.get('precision')==[127,127,23] for row in value)
 def denied(value):return isinstance(value,list) and len(value)==2 and all(row.get('missing') for row in value)
 def pixels(value):return value.get('pixels') if isinstance(value,dict) else None
 def noise_valid(value):return isinstance(value,dict) and value.get('error')==0 and len(value.get('pixels',[]))==1024 and value['pixels']==value.get('repeat') and any(value['pixels'])
 def evaluate(rows,profile,prefix):
  check(isinstance(rows,list) and len(rows)==2,prefix+' paired contexts returned')
  if not isinstance(rows,list):return
  for index,row in enumerate(rows):
   kind='webgl2' if index else 'webgl';name=prefix+'/'+kind;context=profile['contexts'][kind]
   check(not row.get('missing'),name+' native context admitted complete reference')
   if row.get('missing'):continue
   mismatch={key:{'expected':entry['value'],'actual':row['allParameters'].get(key)} for key,entry in context['parameters'].items() if key!='34467' and row['allParameters'].get(key)!=entry['value']}
   check(not mismatch,name+' all derived static parameters agree')
   row['parameterMismatches']=mismatch
   expected_precision=[]
   for shader in [35633,35632]:
    for precision in [36336,36337,36338,36339,36340,36341]:
     p=next(x['shaderPrecisionFormat'] for x in context['shaderPrecisionFormats'] if x['shaderType']==shader and x['precisionType']==precision);expected_precision.append([p['rangeMin'],p['rangeMax'],p['precision']])
   check(0<=row['defaultSamples']<=profile['contexts']['webgl2']['parameters']['36183']['value'],name+' actual default framebuffer stays within reference sample budget with global MSAA preference8')
   check(row['precision']==expected_precision,name+' complete full32bit precision table')
   check(sorted(row['extensions'])==sorted(context['supportedExtensions']) and row['working']==row['extensions'],name+' all extensions are admitted and callable')
   check(sorted(row['allParameters'].get('34467',[]))==sorted(context['parameters']['34467']['value']),name+' enabled compressed formats follow the admitted source pair')
   check(all(row['privacyDenied']),name+' shader/timing/version exclusions remain blocked')
   check(row['identity'][2:]==[profile['vendor'],profile['renderer']],name+' exact recorded coarse identity')
   check(row['below']==0 and row['above']==1281 and row['renderbufferAbove']==1281,name+' actual texture and renderbuffer budgets')
   check(row['shaderAbove'] is False and row['attribAbove']==1281 and row['textureUnitAbove']==1281,name+' actual shader attribute and texture-unit ceilings')
   check(row['invalidPrecision'] is None and row['invalidError']==1280,name+' invalid precision enums preserve native errors')
   if index:check(row['samplesAt']==0 and row['samplesAbove']==1282 and max(row['sampleCounts'],default=0)==context['parameters']['36183']['value'] and row['uboAbove']==1281 and row['texture3dAbove']==1281 and row['arrayAbove']==1281,name+' real MSAA UBO 3D and array boundaries')
 try:
  with tempfile.TemporaryDirectory(prefix='cloakfox-reference-159-') as tmp:
   options=Options();options.binary_location=str(binary)
   for arg in ['-headless','-profile',tmp,'-purgecaches']:options.add_argument(arg)
   for pref,value in [('cloakfox.enabled',True),('cloakfox.experimental.canvas_pipeline',True),('dom.webgpu.enabled',True),('layers.gpu-process.allow-headless',True)]:options.set_preference(pref,value)
   driver=webdriver.Firefox(options=options,service=Service(os.environ.get('GECKODRIVER','/opt/homebrew/bin/geckodriver'),service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
   try:
    driver.set_script_timeout(90)
    chrome(driver,"Services.prefs.setIntPref('webgl.msaa-samples',8);")
    report['runtime']=chrome(driver,'return {version:Services.appinfo.version,buildID:Services.appinfo.appBuildID};')
    check(report['runtime']['version'].startswith('159.'),'actual Firefox159 runtime')
    driver.set_context('content');base_handle=driver.current_window_handle
    expected_owners={}
    ids=chrome(driver,"Services.prefs.setBoolPref('cloakfox.opt.container_rendering_profiles',true);return Array.from({length:arguments[0]},(_,i)=>cis.create('Reference GPU '+i,'fingerprint','blue').userContextId);",2*len(profiles))
    for index,profile in enumerate(profiles):
     profile_label=f"{profile['code']}:{profile['renderer']} ({profile['os']}/{profile['family']})"
     owners=[]
     for offset in [0,1]:
      owner=ids[index*2+offset]
      config=chrome(driver,r'''const owner=arguments[0],ref=arguments[1],key='cloakfox.s.cloak_cfg_'+owner;
       const old=JSON.parse(Services.prefs.getStringPref(key)),personas=ChromeUtils.importESModule('resource:///modules/CloakfoxPersonas.sys.mjs');
       const next=personas.fillPersonaKeys('B'.repeat(43)+'=',owner,{os:({mac:'macos',win:'windows',lin:'linux',linux:'linux',windows:'windows'})[ref.os],hardware:ref.family});
       for(const [k,v] of Object.entries(old))if(/seed|secret/i.test(k))next[k]=v;
       next['webGl:renderer']=ref.renderer;next['webGl:vendor']=ref.vendor;next['rendering:gpu_reference']=true;next['rendering:gpu_observed']=arguments[2];next['navigator:webgpu:disabled']=false;
       const overrides=ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs');
       Services.prefs.setStringPref(key,JSON.stringify(overrides.applyGraphicsPolicy(next,owner)));
       // Use the settings API so startup distinguishes explicit off from an
       // absent choice, which intentionally defaults compatible Windows to on.
       overrides.setOverrides(owner,{'rendering:gpu_reference':true,'rendering:gpu_observed':arguments[2],
        'webGl:renderer':ref.renderer,'webGl:vendor':ref.vendor,
        'navigator.platform':next['navigator.platform'],'navigator.oscpu':next['navigator.oscpu']});
       const result=overrides.applyOverrides(owner,next);
       Services.prefs.setStringPref(key,JSON.stringify(result));return result;''',owner,profile,observed_mode)
      check(config['rendering:gpu_profile']['version']==(4 if observed_mode else 3) and config['rendering:gpu_profile']['owner']==owner and config['rendering:gpu_profile']['catalog']==[profile['code']],f'{profile_label}/{offset}: strict owned v3 descriptor')
      requested=chrome(driver,"return ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs').readOverrides(arguments[0]);",owner)
      check(requested.get('rendering:gpu_reference') is True and requested.get('rendering:gpu_observed') is observed_mode,f'{profile_label}/{offset}: exact explicit reference/observed choices persist through settings API')
      expected_owners[owner]=config
      owner_rows=[];noise_rows=[];site_bindings=[]
      for site_index,host in enumerate(['127.0.0.1','localhost','127.0.0.1']):
       url=f'http://{host}:{server.server_port}/?owner={owner}'
       if site_index==0:_,actual=open_site(driver,url,owner)
       else:
        driver.set_context('content');driver.get(url);actual=chrome(driver,"return Services.wm.getMostRecentWindow('navigator:browser').gBrowser.selectedBrowser.browsingContext.originAttributes.userContextId;")
       check(actual==owner,f'{profile_label}/{offset}/{host}: actual owner')
       driver.set_context('content');rows=driver.execute_script(DETAILS+'return captureReference(arguments[0]);',profile['contexts']);evaluate(rows,profile,f'{profile_label}/{offset}/{host}');owner_rows.append(rows)
       owner_message=f"cloakfox-canvas-owner-v1\n{config['canvas:seed']}\n(http,{host})"
       site_bindings.append(hmac.new(config['fingerprint:secret'].encode(),owner_message.encode(),hashlib.sha256).hexdigest()[:32])
       noise=driver.execute_script(STARTUP_JS+'return referenceNoise();');noise_rows.append(noise);check(noise_valid(noise),f'{profile_label}/{offset}/{host}: verified canonical GPU output repeats exactly')
      check(noise_rows[0]==noise_rows[2] and site_bindings[0]==site_bindings[2] and site_bindings[0]!=site_bindings[1],f'{profile_label}/{offset}: canonical output repeats while source-derived owner/site bindings stay separate')
      check(owner_rows[0]==owner_rows[2],f'{profile_label}/{offset}: site return deterministic')
      check(driver.execute_script('return [navigator.platform,navigator.oscpu];')==[config['navigator.platform'],config['navigator.oscpu']],f'{profile_label}/{offset}: native window retains own persona OS metadata')
      worker=driver.execute_async_script(WORKER_RUN,profile['contexts']);evaluate(worker,profile,f'{profile_label}/{offset}/worker')
      check(worker==owner_rows[-1],f'{profile_label}/{offset}: worker exact owner and context pair')
      startup=driver.execute_async_script(STARTUP_RUN,'classic');module_startup=driver.execute_async_script(STARTUP_RUN,'module');frame=driver.execute_async_script(FRAME_RUN,STARTUP_JS)
      for label,value in [('worker startup',startup),('module worker startup',module_startup),('initial blank frame',frame)]:
       check(startup_valid(value.get('startup'),profile),f'{profile_label}/{offset}: '+label+' native owner and reference before deferred actor patches')
       check(noise_valid(value.get('noise')) and pixels(value['noise'])==pixels(noise_rows[-1]),f'{profile_label}/{offset}: '+label+' keeps the verified canonical output')
       metadata=value.get('navigator',{})
       # Navigator.oscpu is window-only in Navigator.webidl; WorkerNavigator
       # includes NavigatorID, whose supported platform must remain owned.
       expected_metadata={'platform':config['navigator.platform'],'oscpu':config['navigator.oscpu'] if label=='initial blank frame' else None,'hasOscpu':label=='initial blank frame'}
       check(metadata==expected_metadata,f'{profile_label}/{offset}: '+label+' retains own supported persona OS metadata')
      if observed_mode:
       executions={'window':driver.execute_script(EXECUTION+'return observedGpuExecution();'),
        'worker':driver.execute_async_script("const done=arguments[arguments.length-1],w=new Worker('/observed-execution.js');const t=setTimeout(()=>{w.terminate();done({error:'execution worker timeout'})},30000);w.onmessage=e=>{clearTimeout(t);w.terminate();done(e.data)};w.onerror=e=>{clearTimeout(t);w.terminate();done({error:e.message})};w.postMessage(null);")}
       for scope,execution in executions.items():
        check(isinstance(execution.get('checks'),list) and bool(execution['checks']) and len(execution.get('contexts',[]))==2,f'{profile_label}/{offset}/{scope}: actual native execution completed for both contexts')
        for result in execution.get('checks',[]):check(result['pass'],f'{profile_label}/{offset}/{scope}: '+result['name'])
       report.setdefault('nativeExecutions',[]).append({'code':profile['code'],'renderer':profile['renderer'],'os':profile['os'],'family':profile['family'],'owner':owner,'executions':executions});save()
      scoped={scope:driver.execute_async_script(SCOPED_RUN,{'contexts':profile['contexts'],'observed':observed_mode},kind) for scope,kind in [('classic worker','classic'),('module worker','module')]}
      scoped['initial blank frame']=driver.execute_async_script(SCOPED_FRAME,SCOPED_SOURCE,{'contexts':profile['contexts'],'observed':observed_mode})
      for scope,value in scoped.items():
       prefix=f'{profile_label}/{offset}/{scope}'
       evaluate(value.get('rows'),profile,prefix)
       if observed_mode:
        execution=value.get('execution') or {}
        check(bool(execution.get('checks')) and len(execution.get('contexts',[]))==2,prefix+': native resource execution completed')
        for result in execution.get('checks',[]):check(result['pass'],prefix+': '+result['name'])
       restriction=value.get('readback',{})
       check(restriction.get('integerError')==1282 and restriction.get('pboError')==1282 and restriction.get('integer')==[88]*16,prefix+': precise integer and PBO protections retained')
       gpu=value.get('webgpu',{})
       if gpu.get('available'):check(gpu['aboveRejected'] and gpu['allocationRejected'] and gpu['maxBufferSize']==268435456 and gpu['maxStorageBufferBindingSize']==134217728,prefix+': actual canonical WebGPU bounds')
       elif gpu.get('error'):check(False,prefix+': WebGPU raised '+str(gpu['error']))
       else:report['inconclusive'].append({'name':prefix+': WebGPU','result':gpu})
      report.setdefault('scopedExecutions',[]).append({'code':profile['code'],'renderer':profile['renderer'],'os':profile['os'],'owner':owner,'scopes':scoped})
      strict=driver.execute_script(READBACK);check(strict.get('integerError')==1282 and strict.get('pboError')==1282 and strict.get('integer')==[88]*16,f'{profile_label}/{offset}: precise integer and PBO protections retained')
      gpu=driver.execute_async_script(GPU)
      if gpu.get('available'):check(gpu['aboveRejected'] and gpu['allocationRejected'] and gpu['maxBufferSize']==268435456 and gpu['maxStorageBufferBindingSize']==134217728,f'{profile_label}/{offset}: actual canonical WebGPU bounds')
      else:report['inconclusive'].append({'name':f'{profile_label}/{offset}: WebGPU','result':gpu})
      report['cases'].append({'code':profile['code'],'renderer':profile['renderer'],'os':profile['os'],'family':profile['family'],'owner':owner,'descriptor':config['rendering:gpu_profile'],'samples':owner_rows,'worker':worker,'startup':startup,'moduleStartup':module_startup,'frameStartup':frame,'noise':noise_rows,'ownerSiteBindingSHA256Prefix':site_bindings,'ownerBindingEvidence':'Expected source-derived HMAC tokens; actual native enforcement is exercised by wrong-owner and cross-source refusal tests, not a public metadata API.','readback':strict,'webgpu':gpu});owners.append(config);save()
      driver.set_context('content');driver.close();driver.switch_to.window(base_handle)
     check(report['cases'][-2]['ownerSiteBindingSHA256Prefix'][0]!=report['cases'][-1]['ownerSiteBindingSHA256Prefix'][0],profile_label+': identical recorded GPUs retain independent owner bindings even when canonical pixels coincide')
     check(owners[0]['rendering:gpu_profile']['owner']!=owners[1]['rendering:gpu_profile']['owner'] and owners[0]['fingerprint:secret']!=owners[1]['fingerprint:secret'],profile_label+': identical GPU records keep independent owner secrets')
    check({case['descriptor']['catalog'][0] for case in report['cases']}=={profile['code'] for profile in profiles} and len(report['cases'])==2*len(profiles),'all selected actual source record codes exercised across two distinct owners')
    report['sourcePool']=[{'code':profile['code'],'record':profile['record'],'sourceContexts':profile['sourceContexts'],'sourceRecords':profile.get('sourceRecords',[]),'renderer':profile['renderer'],'os':profile['os']} for profile in profiles]
    owner=ids[2*len(profiles)-1]
    _,actual=open_site(driver,f'http://127.0.0.1:{server.server_port}/?owner={owner}',owner);check(actual==owner,'malformed and captured-context checks use actual last reference owner')
    saved=json.dumps(expected_owners[owner],separators=(',',':'))
    malformed=[
     ('wrong owner',"config['rendering:gpu_profile'].owner=0"),
     ('wrong archive source',"config['rendering:gpu_profile'].source='sha256:forged'"),
     ('invalid source type',"config['rendering:gpu_profile'].source={archive:'forged'}"),
     ('empty record catalog',"config['rendering:gpu_profile'].catalog=[]"),
     ('foreign source record code',"config['rendering:gpu_profile'].catalog=[32769]"),
     ('unknown source record code',"config['rendering:gpu_profile'].catalog=[65535]"),
     ('legacy code in reference catalog',"config['rendering:gpu_profile'].catalog=[2]"),
     ('duplicate source records',"config['rendering:gpu_profile'].catalog.push(config['rendering:gpu_profile'].catalog[0])"),
     ('invalid catalog element type',"config['rendering:gpu_profile'].catalog=[String(config['rendering:gpu_profile'].catalog[0])]"),
     ('legacy v1 descriptor in reference mode',"config['rendering:gpu_profile'].version=1;delete config['rendering:gpu_profile'].catalog"),
     ('wrong descriptor version',"config['rendering:gpu_profile'].version=2"),
     ('wrong reference mode',"config['rendering:gpu_profile'].mode='physical'"),
     ('wrong privacy policy',"config['rendering:gpu_profile'].privacyPolicy='allow-debug-shaders'"),
     ('wrong version adaptation',"config['rendering:gpu_profile'].adaptation='physical-Firefox146'"),
     ('different BrowserForge OS',"config['navigator.platform']=config['navigator.platform']==='MacIntel'?'Win32':'MacIntel';config['navigator.oscpu']=config['navigator.platform']==='MacIntel'?'Intel Mac OS X 10.15':'Windows NT 10.0; Win64; x64'"),
     ('missing exact OS',"delete config['navigator.platform']"),
     ('missing descriptor',"delete config['rendering:gpu_profile']"),
     ('invalid reference toggle',"config['rendering:gpu_reference']='true'"),
    ]
    if observed_mode:
     malformed += [('unsupported Apple observed identity',"config['webGl:vendor']='Apple';config['webGl:renderer']='Apple M1, or similar';config['navigator.platform']='MacIntel';config['navigator.oscpu']='Intel Mac OS X 10.15'"),('invalid observed toggle',"config['rendering:gpu_observed']='true'"),('missing reference prerequisite',"config['rendering:gpu_reference']=false")]
    report['malformed']=[]
    for label,mutation in malformed:
     chrome(driver,"const config=JSON.parse(arguments[1]);"+mutation+";Services.prefs.setStringPref('cloakfox.s.cloak_cfg_'+arguments[0],JSON.stringify(config));",owner,saved)
     driver.set_context('content');driver.refresh();window=driver.execute_script(STARTUP_JS+'return captureStartup();');worker=driver.execute_async_script(STARTUP_RUN,'classic');frame=driver.execute_async_script(FRAME_RUN,STARTUP_JS)
     check(denied(window),label+': new native window contexts fail closed')
     check(denied(worker.get('startup')),label+': early worker contexts fail closed')
     check(denied(frame.get('startup')),label+': initial blank frame contexts fail closed')
     gpu=driver.execute_async_script(GPU);check(gpu.get('available') is False,label+': owned native WebGPU descriptor fails closed')
     report['malformed'].append({'case':label,'window':window,'worker':worker,'frame':frame,'webgpu':gpu});save()
    chrome(driver,"Services.prefs.setStringPref('cloakfox.s.cloak_cfg_'+arguments[0],arguments[1]);",owner,saved)
    driver.set_context('content');driver.close();driver.switch_to.window(base_handle)
    # Apple has MAX_SAMPLES4: pref8 must remain bounded on this held context,
    # including resize/restoration after the owning container toggles mode off.
    owner=ids[0];held_profile=profiles[0];held_case=report['cases'][0]
    _,actual=open_site(driver,f'http://127.0.0.1:{server.server_port}/?owner={owner}',owner)
    check(actual==owner and (observed_mode or (held_profile['family']=='apple' and held_profile['contexts']['webgl2']['parameters']['36183']['value']==4)),'captured resize and restoration exercise stricter Apple4 source against process MSAA preference8')
    driver.set_context('content')
    frozen=driver.execute_script("window.held=document.createElement('canvas').getContext('webgl');const ext=held.getExtension('WEBGL_debug_renderer_info');return [held.getParameter(ext.UNMASKED_RENDERER_WEBGL),held.getParameter(3379),held.getParameter(36347),held.getParameter(held.SAMPLES)];")
    check(0<=frozen[3]<=held_profile['contexts']['webgl2']['parameters']['36183']['value'],'captured Apple default framebuffer obeys sample4 before toggling with global preference8')
    chrome(driver,"const key='cloakfox.s.cloak_cfg_'+arguments[0],config=JSON.parse(Services.prefs.getStringPref(key));config['rendering:gpu_reference']=false;config['rendering:gpu_observed']=false;const next=ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs').applyGraphicsPolicy(config,arguments[0]);Services.prefs.setStringPref(key,JSON.stringify(next));",owner)
    driver.set_context('content');check(driver.execute_script("const ext=held.getExtension('WEBGL_debug_renderer_info');return [held.getParameter(ext.UNMASKED_RENDERER_WEBGL),held.getParameter(3379),held.getParameter(36347),held.getParameter(held.SAMPLES)];")==frozen,'existing native context keeps captured reference after toggle')
    resized=driver.execute_script("held.canvas.width=7;held.clearColor(.2,.3,.4,1);held.clear(held.COLOR_BUFFER_BIT);return held.getParameter(held.SAMPLES);");check(0<=resized<=held_profile['contexts']['webgl2']['parameters']['36183']['value'],'resized native default framebuffer keeps captured reference MSAA budget')
    restored=driver.execute_async_script(RESTORE);check(restored==frozen,'restored native context keeps captured reference after per-container toggle');report['restoredContext']=restored
    driver.refresh();off=driver.execute_script("return ['webgl','webgl2'].map(k=>{const g=document.createElement('canvas').getContext(k);return g&&g.getParameter(3379)});");check(all(n in [4096,8192] for n in off),'per-container toggle off restores previous protected catalog')
    off_noise=driver.execute_script(STARTUP_JS+'return referenceNoise();');check(noise_valid(off_noise) and pixels(off_noise)==pixels(held_case['noise'][0]),'turning reference mode off preserves existing protected GPU readback noise')
    # The established canonical exporter deliberately returns common authored
    # CPU pixels. Validate the older noise privacy contract independently with
    # canonical/reference modes off, retaining each saved identity and secret.
    chrome(driver,"Services.prefs.setBoolPref('cloakfox.opt.container_rendering_profiles',false);Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',false);")
    driver.set_context('content');driver.close();driver.switch_to.window(base_handle)
    fallback=[]
    fallback_js=r"""const c=document.createElement('canvas');c.width=c.height=16;const x=c.getContext('2d'),authored=new Uint8ClampedArray(1024);for(let i=0;i<256;i++){authored[i*4]=30+i%180;authored[i*4+1]=60+i%140;authored[i*4+2]=90+i%100;authored[i*4+3]=255;}x.putImageData(new ImageData(authored,16,16),0,0);const pixels=Array.from(x.getImageData(0,0,16,16).data),repeat=Array.from(x.getImageData(0,0,16,16).data);return {pixels,repeat,authored:Array.from(authored),error:0};"""
    for fallback_owner in ids[:2]:
     config=dict(expected_owners[fallback_owner]);config.update({'rendering:gpu_reference':False,'rendering:gpu_observed':False,'canvas:canonical_2d':False,'canvas:canonical_gpu':False,'webGl:backend_profile':False});config.pop('rendering:gpu_profile',None)
     chrome(driver,"Services.prefs.setStringPref('cloakfox.s.cloak_cfg_'+arguments[0],arguments[1]);",fallback_owner,json.dumps(config,separators=(',',':')))
     samples=[]
     for site_index,host in enumerate(['127.0.0.1','localhost','127.0.0.1']):
      url=f'http://{host}:{server.server_port}/?fallback-owner={fallback_owner}'
      if site_index==0:_,actual=open_site(driver,url,fallback_owner)
      else:
       driver.set_context('content');driver.get(url);actual=chrome(driver,"return Services.wm.getMostRecentWindow('navigator:browser').gBrowser.selectedBrowser.browsingContext.originAttributes.userContextId;")
      driver.set_context('content');value=driver.execute_script(fallback_js);samples.append(value)
      check(actual==fallback_owner and noise_valid(value) and value['pixels']!=value['authored'],f'fallback/{fallback_owner}/{host}: existing noncanonical canvas export retains owned deterministic noise')
     check(samples[0]==samples[2] and pixels(samples[0])!=pixels(samples[1]),f'fallback/{fallback_owner}: existing site-separated noise survives leaving and returning')
     fallback.append({'owner':fallback_owner,'samples':samples});driver.close();driver.switch_to.window(base_handle)
    check(pixels(fallback[0]['samples'][0])!=pixels(fallback[1]['samples'][0]),'fallback: independent saved owner identities retain different noise')
    report['noncanonicalFallbackNoise']={'scope':'Existing protected 2D canvas extraction with reference and canonical pipeline off; does not claim canonical GPU pixels must differ','owners':fallback}
    chrome(driver,"Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',true);Services.prefs.setBoolPref('cloakfox.opt.container_rendering_profiles',true);")
    # Restore every exact v3 owner and restart the same disposable profile.
    for saved_owner,config in expected_owners.items():chrome(driver,"Services.prefs.setStringPref('cloakfox.s.cloak_cfg_'+arguments[0],arguments[1]);",saved_owner,json.dumps(config,separators=(',',':')))
    chrome(driver,'Services.prefs.savePrefFile(null);')
    driver.quit()
    driver=webdriver.Firefox(options=options,service=Service(os.environ.get('GECKODRIVER','/opt/homebrew/bin/geckodriver'),service_args=['--allow-system-access'],log_output=str(out/'restart-gecko.log')))
    driver.set_script_timeout(90);report['restart']=[];driver.set_context('content');restart_base=driver.current_window_handle
    for index,profile in enumerate(profiles):
     profile_label=f"{profile['code']}:{profile['renderer']} ({profile['os']}/{profile['family']})"
     for offset in [0,1]:
      saved_owner=ids[index*2+offset];expected=expected_owners[saved_owner]
      _,actual=open_site(driver,f'http://127.0.0.1:{server.server_port}/?owner={saved_owner}',saved_owner)
      persisted=chrome(driver,"return {overrides:ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs').readOverrides(arguments[0]),enabled:Services.prefs.getBoolPref('cloakfox.opt.container_rendering_profiles',false),config:JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+arguments[0]))};",saved_owner)
      check(persisted['overrides'].get('rendering:gpu_reference') is True and persisted['overrides'].get('rendering:gpu_observed') is observed_mode,f'{profile_label}/{offset}: explicit saved reference/observed choices survive restart')
      check(actual==saved_owner and persisted['enabled'] and persisted['config'].get('rendering:gpu_reference') is True and persisted['config'].get('rendering:gpu_profile')==expected['rendering:gpu_profile'] and persisted['config'].get('fingerprint:secret')==expected['fingerprint:secret'] and persisted['config'].get('canvas:seed')==expected['canvas:seed'],f'{profile_label}/{offset}: v3 descriptor exact owner source toggle and secrets persist across restart')
      driver.set_context('content');startup=driver.execute_script(STARTUP_JS+'return {startup:captureStartup(),noise:referenceNoise(),navigator:{platform:navigator.platform,oscpu:navigator.oscpu,hasOscpu:"oscpu" in navigator}};');worker=driver.execute_async_script(STARTUP_RUN,'classic')
      check(startup_valid(startup.get('startup'),profile) and startup_valid(worker.get('startup'),profile),f'{profile_label}/{offset}: fresh startup native window and worker retain v3 profile')
      check(noise_valid(startup.get('noise')) and pixels(startup['noise'])==pixels(report['cases'][index*2+offset]['noise'][0]) and pixels(worker.get('noise',{}))==pixels(startup['noise']),f'{profile_label}/{offset}: same owner and canonical output survive restart')
      report['restart'].append({'owner':saved_owner,'code':profile['code'],'renderer':profile['renderer'],'os':profile['os'],'family':profile['family'],'descriptor':persisted['config'].get('rendering:gpu_profile'),'startup':startup,'worker':worker});save()
      driver.set_context('content');driver.close();driver.switch_to.window(restart_base)
   finally:driver.quit()
 finally:server.shutdown();server.server_close();save()
 if any(not row['pass'] for row in report['checks']):return 1
 return 2 if report['inconclusive'] else 0
if __name__=='__main__':raise SystemExit(main())
