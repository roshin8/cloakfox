#!/usr/bin/env python3
"""Disposable-profile standardized GPU integration probe; rebuilt binary required.

Exercises actual limits/allocation, shader resources, workers, container ownership,
invalid precision enums, persisted config preservation, native controls and frozen
context policy. This does not compare or imitate detector reference hashes.
"""
from __future__ import annotations
import functools
import http.server
import json
import os
from pathlib import Path
import tempfile
import threading
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait

INSPECT = r"""
function inspect(gl) {
 if(!gl)return {missing:true};
 const gl2=typeof gl.MAX_3D_TEXTURE_SIZE==='number';
 const ext=gl.getExtension('WEBGL_debug_renderer_info');
 const identity=[gl.getParameter(gl.VENDOR),gl.getParameter(gl.RENDERER),
  ext?gl.getParameter(ext.UNMASKED_VENDOR_WEBGL):null,
  ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):null];
 const names=['MAX_TEXTURE_SIZE','MAX_CUBE_MAP_TEXTURE_SIZE','MAX_RENDERBUFFER_SIZE',
  'MAX_VERTEX_ATTRIBS','MAX_TEXTURE_IMAGE_UNITS','MAX_VERTEX_TEXTURE_IMAGE_UNITS',
  'MAX_COMBINED_TEXTURE_IMAGE_UNITS','MAX_VERTEX_UNIFORM_VECTORS',
  'MAX_FRAGMENT_UNIFORM_VECTORS','MAX_VARYING_VECTORS','MAX_3D_TEXTURE_SIZE',
  'MAX_ARRAY_TEXTURE_LAYERS','MAX_VERTEX_UNIFORM_COMPONENTS','MAX_FRAGMENT_UNIFORM_COMPONENTS',
  'MAX_VERTEX_OUTPUT_COMPONENTS','MAX_FRAGMENT_INPUT_COMPONENTS','MAX_VARYING_COMPONENTS',
  'MAX_UNIFORM_BUFFER_BINDINGS','MAX_DRAW_BUFFERS','MAX_SAMPLES'];
 const caps=Object.fromEntries(names.filter(n=>typeof gl[n]==='number').map(n=>[n,gl.getParameter(gl[n])]));
 const extensions=gl.getSupportedExtensions();
 const working=extensions.filter(n=>!!gl.getExtension(n));
 const precision=[];
 for(const st of [gl.VERTEX_SHADER,gl.FRAGMENT_SHADER])for(const pt of [gl.LOW_FLOAT,gl.MEDIUM_FLOAT,gl.HIGH_FLOAT,gl.LOW_INT,gl.MEDIUM_INT,gl.HIGH_INT]) {
  const p=gl.getShaderPrecisionFormat(st,pt);precision.push([p.rangeMin,p.rangeMax,p.precision]);
 }
 while(gl.getError()){}
 const invalidPrecision=gl.getShaderPrecisionFormat(12345,gl.HIGH_FLOAT);
 const invalidError=gl.getError();
 const allocate=(width)=>{
  const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);
  gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,width,1,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
  const error=gl.getError();gl.deleteTexture(texture);return error;
 };
 const below=allocate(caps.MAX_TEXTURE_SIZE),above=allocate(caps.MAX_TEXTURE_SIZE+1);
 const rb=gl.createRenderbuffer();gl.bindRenderbuffer(gl.RENDERBUFFER,rb);
 gl.renderbufferStorage(gl.RENDERBUFFER,gl.RGBA4,caps.MAX_RENDERBUFFER_SIZE+1,1);
 const renderbufferAbove=gl.getError();gl.deleteRenderbuffer(rb);
 const cap=caps.MAX_VERTEX_ATTRIBS;
 gl.vertexAttrib1f(cap,0);const attribAbove=gl.getError();
 gl.activeTexture(gl.TEXTURE0+caps.MAX_COMBINED_TEXTURE_IMAGE_UNITS);
 const textureUnitAbove=gl.getError();
 // Use every array element so the translator cannot remove an unused excess.
 const vectors=caps.MAX_VERTEX_UNIFORM_VECTORS;
 const shader=gl.createShader(gl.VERTEX_SHADER);
 gl.shaderSource(shader,`uniform vec4 u[${vectors+1}];void main(){vec4 p=vec4(0.0);for(int i=0;i<${vectors+1};i++){p+=u[i];}gl_Position=p;}`);
 gl.compileShader(shader);const shaderAbove=gl.getShaderParameter(shader,gl.COMPILE_STATUS);
 const shaderLog=gl.getShaderInfoLog(shader);gl.deleteShader(shader);
 gl.clearColor(.25,.5,.75,1);const color=Array.from(gl.getParameter(gl.COLOR_CLEAR_VALUE));
 return {gl2,identity,caps,extensions,working,precision,invalidPrecision,invalidError,
  below,above,renderbufferAbove,attribAbove,textureUnitAbove,shaderAbove,shaderLog,color};
}
"""

RASTER = r"""
return ['webgl','webgl2'].map(kind=>{
 const canvas=document.createElement('canvas');canvas.width=8;canvas.height=128;
 const gl=canvas.getContext(kind,{antialias:false,preserveDrawingBuffer:true});
 if(!gl)return {kind,missing:true};
 const compile=(type,src)=>{const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);return s;};
 const vs=compile(gl.VERTEX_SHADER,'attribute vec2 pos;void main(){gl_Position=vec4(pos,0.0,1.0);gl_PointSize=128.0;}');
 const fs=compile(gl.FRAGMENT_SHADER,'precision mediump float;void main(){gl_FragColor=vec4(1.0,0.0,0.0,1.0);}');
 const p=gl.createProgram();gl.attachShader(p,vs);gl.attachShader(p,fs);gl.linkProgram(p);
 if(!gl.getProgramParameter(p,gl.LINK_STATUS))return {kind,error:gl.getProgramInfoLog(p)};
 gl.useProgram(p);const a=gl.getAttribLocation(p,'pos');
 const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([0,0,-1,0,1,0]),gl.STATIC_DRAW);
 gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,2,gl.FLOAT,false,0,0);
 const rows=()=>{const bytes=new Uint8Array(8*128*4);gl.readPixels(0,0,8,128,gl.RGBA,gl.UNSIGNED_BYTE,bytes);let count=0;
  for(let y=0;y<128;y++){let colored=false;for(let x=0;x<8;x++)colored ||= bytes[(y*8+x)*4]>128;if(colored)count++;}return count;};
 gl.clearColor(0,0,0,1);gl.clear(gl.COLOR_BUFFER_BIT);gl.drawArrays(gl.POINTS,0,1);
 const pointRows=rows();
 gl.clear(gl.COLOR_BUFFER_BIT);gl.lineWidth(128);gl.drawArrays(gl.LINES,1,2);
 const lineRows=rows(),lineState=gl.getParameter(gl.LINE_WIDTH);
 return {kind,pointRows,lineRows,lineState,error:gl.getError()};
});
"""



READBACK = r"""
const canvas=document.createElement('canvas');canvas.width=2;canvas.height=2;
const gl=canvas.getContext('webgl2',{antialias:false,preserveDrawingBuffer:true});
if(!gl)return {missing:true};
const fb=gl.createFramebuffer();gl.bindFramebuffer(gl.FRAMEBUFFER,fb);
const rb=gl.createRenderbuffer();gl.bindRenderbuffer(gl.RENDERBUFFER,rb);
gl.renderbufferStorage(gl.RENDERBUFFER,gl.RGBA8UI,2,2);
gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.RENDERBUFFER,rb);
const status=gl.checkFramebufferStatus(gl.FRAMEBUFFER);
gl.clearBufferuiv(gl.COLOR,0,new Uint32Array([17,123,231,255]));
const integer=new Uint8Array(16).fill(88);
gl.readPixels(0,0,2,2,gl.RGBA_INTEGER,gl.UNSIGNED_BYTE,integer);
const integerError=gl.getError();
gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.clearColor(1,0,1,1);gl.clear(gl.COLOR_BUFFER_BIT);
const ordinary=new Uint8Array(16);gl.readPixels(0,0,2,2,gl.RGBA,gl.UNSIGNED_BYTE,ordinary);
const ordinaryError=gl.getError();
const pbo=gl.createBuffer();gl.bindBuffer(gl.PIXEL_PACK_BUFFER,pbo);
gl.bufferData(gl.PIXEL_PACK_BUFFER,new Uint8Array(16).fill(88),gl.STREAM_READ);
gl.readPixels(0,0,2,2,gl.RGBA,gl.UNSIGNED_BYTE,0);const pboError=gl.getError();
const pboData=new Uint8Array(16);gl.getBufferSubData(gl.PIXEL_PACK_BUFFER,0,pboData);
const bufferError=gl.getError();
gl.bindBuffer(gl.PIXEL_PACK_BUFFER,null);
return {status,integer:Array.from(integer),integerError,pboData:Array.from(pboData),pboError,bufferError,ordinaryError,
 renderer:gl.getParameter(gl.RENDERER),texture:gl.getParameter(gl.MAX_TEXTURE_SIZE)};
"""


PRECISION_POLICY = r"""
function precisionPolicy(gl){
 const value=gl.getShaderPrecisionFormat(gl.VERTEX_SHADER,gl.HIGH_FLOAT);
 const valueError=gl.getError();
 const invalid=gl.getShaderPrecisionFormat(12345,gl.HIGH_FLOAT),invalidError=gl.getError();
 return {blocked:value===null,valueError,invalid:invalid===null,invalidError};
}
"""
WORKER_SOURCE = INSPECT + PRECISION_POLICY + "onmessage=e=>postMessage(e.data==='precision'?precisionPolicy(new OffscreenCanvas(8,8).getContext('webgl')):['webgl','webgl2'].map(k=>inspect(new OffscreenCanvas(8,8).getContext(k))));"
WORKER_RUN = r"""
const done=arguments[arguments.length-1];const payload=arguments.length>1?arguments[0]:1;const worker=new Worker('worker.js');let finished=false;
const timer=setTimeout(()=>finish({error:'worker timeout after 5 seconds'}),5000);
function finish(value){if(finished)return;finished=true;clearTimeout(timer);worker.terminate();done(value);}
worker.onmessage=e=>finish(e.data);
worker.onerror=e=>finish({error:e.message||'worker script failed to load or execute'});
worker.postMessage(payload);
"""


def main():
    report=Path(os.environ.get('REPORT_DIR','/tmp/cloakfox-gpu-backend-profile')).resolve()
    report.mkdir(parents=True,exist_ok=True)
    result={'checks':[],'measurements':{}}
    def check(condition,name):
        result['checks'].append({'name':name,'pass':bool(condition)})
        print(('PASS ' if condition else 'FAIL ')+name,flush=True)
    with tempfile.TemporaryDirectory(prefix='cloakfox-gpu-profile-') as tmp:
        root=Path(tmp);profile=root/'profile';profile.mkdir()
        (root/'index.html').write_text('<!doctype html><title>GPU cohort probe</title>')
        (root/'worker.js').write_text(WORKER_SOURCE)
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(http.server.SimpleHTTPRequestHandler,directory=tmp))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        url=f'http://127.0.0.1:{server.server_port}/index.html'
        (profile/'user.js').write_text('user_pref("cloakfox.enabled", true);\n')
        launches=0
        def launch():
            nonlocal launches
            launches+=1
            options=Options();options.binary_location=os.environ['CLOAKFOX_BIN']
            options.set_preference('cloakfox.experimental.canvas_pipeline',os.environ.get('CLOAKFOX_TEST_CANVAS_PIPELINE','0')=='1')
            for arg in ['-headless','-purgecaches','-profile',str(profile)]:options.add_argument(arg)
            return webdriver.Firefox(options=options,service=Service(service_args=['--allow-system-access'],log_output=str(report/f'gecko-{launches}.log')))
        driver=launch()
        def chrome(script,*args):
            driver.set_context('chrome')
            try:return driver.execute_script(script,*args)
            finally:driver.set_context('content')
        def measure():
            driver.get(url)
            WebDriverWait(driver,10).until(lambda d:d.execute_script('return document.readyState')=='complete')
            return WebDriverWait(driver,10).until(lambda d:d.execute_script(INSPECT+"window.cohortContexts=['webgl','webgl2'].map(k=>document.createElement('canvas').getContext(k));return cohortContexts.map(inspect);"))
        try:
            chrome('Services.prefs.setBoolPref("cloakfox.enabled",false);')
            native=measure();result['measurements']['native']=native
            chrome('Services.prefs.setBoolPref("cloakfox.enabled",true);Services.prefs.setBoolPref("cloakfox.opt.gpu_backend_profiles",false);')
            legacy=measure();result['measurements']['legacy']=legacy
            before=chrome(r"""const cfg=JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_0'));
             cfg['gpu:sentinel']='retained';cfg['webGl:vendor']='Unrelated test vendor';cfg['webGl:renderer']='Unrelated test renderer';
             cfg['webGl:parameters']['36347']=13;cfg['webGl2:parameters']['36347']=13;
             cfg['webGl2:parameters']['35658']=52;cfg['webGl2:parameters']['36183']=1;
             cfg['webGl:shaderPrecisionFormats']['12345,36338']={rangeMin:127,rangeMax:127,precision:23};
             Services.prefs.setStringPref('cloakfox.s.cloak_cfg_0',JSON.stringify(cfg));
             return cfg;""")
            chrome('Services.prefs.setBoolPref("cloakfox.opt.gpu_backend_profiles",true);')
            masked=measure();result['measurements']['profile']=masked
            raster=driver.execute_script(RASTER);result['measurements']['raster']=raster
            for item in raster:
                check(not item.get('missing') and 1<=item.get('pointRows',0)<=64 and 1<=item.get('lineRows',0)<=2 and item.get('lineState')==128 and item.get('error')==0,item['kind']+' point/line raster obeys cohort while requested line state stays native')
            for item in masked:
                kind='WebGL2' if item.get('gl2') else 'WebGL1'
                check(not item.get('missing'),kind+' supports complete protected baseline')
                if item.get('missing'):continue
                caps=item['caps'];gl2=item['gl2']
                check(item['identity'][:2]==['Mozilla','WebGL'] and all(v in [None,'Mozilla','WebGL'] for v in item['identity']),kind+' generic identity bypasses legacy GPU overrides')
                check(caps['MAX_TEXTURE_SIZE']==2048 and caps['MAX_RENDERBUFFER_SIZE']==2048 and caps['MAX_VERTEX_UNIFORM_VECTORS']==256,kind+' standardized capabilities bypass legacy scalar tables')
                check(item['below']==0 and item['above']==1281 and item['renderbufferAbove']==1281,kind+' texture/renderbuffer allocation enforces reported ceiling')
                check(item['attribAbove']==1281 and item['textureUnitAbove']==1281,kind+' attribute and texture-unit validation enforce cohort')
                check(item['shaderAbove'] is False,kind+' shader compiler rejects excess uniform resources')
                check(item['invalidPrecision'] is None and item['invalidError']==1280,kind+' invalid precision enum cannot be manufactured by config')
                check(item['extensions']==item['working'] and not any('debug_shaders' in e or 'compression' in e or 'compressed' in e for e in item['extensions']),kind+' conservative extensions retain native support checks')
                check(item['color']==[.25,.5,.75,1],kind+' mutable GL state remains native')
                if gl2:
                    check(caps['MAX_SAMPLES']==1,'profile preserves existing bounded masks for uncontrolled sample capability')
                    check(caps['MAX_VERTEX_UNIFORM_COMPONENTS']==1024 and caps['MAX_FRAGMENT_UNIFORM_COMPONENTS']==896 and caps['MAX_VERTEX_OUTPUT_COMPONENTS']==64 and caps['MAX_FRAGMENT_INPUT_COMPONENTS']==60 and caps['MAX_VARYING_COMPONENTS']==60,'WebGL2 scalar components agree with normalized shader resources')
            chrome('Services.prefs.setBoolPref("cloakfox.opt.webgl_typed_readback_disabled",true);')
            strict=driver.execute_script(READBACK);result['measurements']['profileStrictReadback']=strict
            check(strict.get('status')==36053 and strict.get('integerError')==1282 and strict.get('integer')==[88]*16,'compatible profile preserves strict RGBA8UI denial and unchanged destination')
            check(strict.get('pboError')==1282 and strict.get('pboData')==[88]*16 and strict.get('bufferError')==0,'compatible profile preserves strict PBO denial and unchanged buffer')
            check(strict.get('ordinaryError')==0 and strict.get('renderer')=='WebGL','strict readback leaves protected ordinary RGBA and generic profile available')
            chrome('Services.prefs.setBoolPref("cloakfox.opt.webgl_typed_readback_disabled",false);')
            compat=driver.execute_script(READBACK);result['measurements']['profileCompatibilityReadback']=compat
            check(compat.get('integerError')==0 and compat.get('integer')==[17,123,231,255]*4,'explicit readback compatibility restores exact integer computation data')
            check(compat.get('pboError')==0 and compat.get('pboData')==[255,0,255,255]*4 and compat.get('bufferError')==0,'explicit readback compatibility restores exact PBO data')
            check(compat.get('renderer')=='WebGL' and compat.get('texture')==2048,'readback compatibility retains generic standardized GPU profile')
            chrome('Services.prefs.setBoolPref("cloakfox.opt.webgl_typed_readback_disabled",true);')
            window_offscreen=driver.execute_script(INSPECT+"return ['webgl','webgl2'].map(k=>inspect(new OffscreenCanvas(8,8).getContext(k)));")
            result['measurements']['windowOffscreen']=window_offscreen
            check([x.get('caps') for x in window_offscreen]==[x.get('caps') for x in masked],'window OffscreenCanvas uses owning profile')
            worker=driver.execute_async_script(WORKER_RUN)
            result['measurements']['worker']=worker
            check(isinstance(worker,list) and [v.get('caps') for v in worker]==[v.get('caps') for v in masked] and [v.get('identity') for v in worker]==[v.get('identity') for v in masked],'worker OffscreenCanvas uses owning profile')
            shared_names=['MAX_VERTEX_ATTRIBS','MAX_VERTEX_UNIFORM_VECTORS','MAX_FRAGMENT_UNIFORM_VECTORS','MAX_COMBINED_TEXTURE_IMAGE_UNITS','MAX_TEXTURE_IMAGE_UNITS','MAX_VERTEX_TEXTURE_IMAGE_UNITS','MAX_VARYING_VECTORS']
            check(all(masked[0]['caps'][name]==masked[1]['caps'][name] for name in shared_names),'both WebGL versions expose the same shared device cohort')
            # A real second container carries conflicting internal policy and
            # sentinel caps. This distinguishes owning config from ambient ctx0.
            original_handle=driver.current_window_handle
            before_handles=set(driver.window_handles)
            ucid=chrome(r"""const {ContextualIdentityService}=ChromeUtils.importESModule(
              'moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
              const id=ContextualIdentityService.create('GPU ownership probe','fingerprint','blue').userContextId;
              const pref='cloakfox.s.cloak_cfg_'+id;
              const cfg=JSON.parse(Services.prefs.getStringPref(pref));cfg['webGl:backend_profile']=false;
              for(const name of ['webGl:parameters','webGl2:parameters'])cfg[name]['36347']=19;
              cfg['webGl2:parameters']['35658']=76;
              Services.prefs.setStringPref(pref,JSON.stringify(cfg));
              const win=Services.wm.getMostRecentWindow('navigator:browser');
              const tab=win.gBrowser.addTab('about:blank',{userContextId:id,
                triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
              win.gBrowser.selectedTab=tab;return id;""")
            owner_handle=(set(driver.window_handles)-before_handles).pop()
            driver.switch_to.window(owner_handle)
            owner=measure();result['measurements']['otherContainer']=owner
            owner_worker=driver.execute_async_script(WORKER_RUN)
            result['measurements']['otherContainerWorker']=owner_worker
            # Both legacy lookup and the frozen policy must follow container B,
            # while the default container remains on its protected baseline.
            check(isinstance(owner,list) and all(x.get('caps',{}).get('MAX_VERTEX_UNIFORM_VECTORS')==19 for x in owner) and isinstance(owner_worker,list) and all(x.get('caps',{}).get('MAX_VERTEX_UNIFORM_VECTORS')==19 for x in owner_worker),'real second-container window and worker use own policy and legacy parameter tables')
            result['measurements']['exactWorkerTableOwnership']={'configuredOwnerVectors':19,'observedWorkerVectors':[x.get('caps',{}).get('MAX_VERTEX_UNIFORM_VECTORS') for x in owner_worker] if isinstance(owner_worker,list) else owner_worker}

            chrome(r"""const pref='cloakfox.s.cloak_cfg_'+arguments[0];const cfg=JSON.parse(Services.prefs.getStringPref(pref));
              cfg['webGl:shaderPrecisionFormats']['35633,36338']={rangeMin:'wrong',rangeMax:127,precision:23};
              cfg['webGl:shaderPrecisionFormats:blockIfNotDefined']=true;
              Services.prefs.setStringPref(pref,JSON.stringify(cfg));""",ucid)
            blocked=driver.execute_script(PRECISION_POLICY+"return precisionPolicy(document.createElement('canvas').getContext('webgl'));")
            blocked_worker=driver.execute_async_script(WORKER_RUN,'precision')
            result['measurements']['malformedPrecisionPolicy']={'window':blocked,'worker':blocked_worker}
            check(blocked.get('blocked') is True and blocked.get('valueError')==0 and blocked.get('invalidError')==1280 and blocked_worker.get('blocked') is True and blocked_worker.get('invalidError')==1280,'malformed precision falls through owning block policy and invalid enums stay native in window/worker')
            owner_origin=chrome("return Services.wm.getMostRecentWindow('navigator:browser').gBrowser.selectedBrowser.contentPrincipal.originAttributes.userContextId")
            check(owner_origin==ucid,'ownership test uses actual container origin attributes')
            driver.close();driver.switch_to.window(original_handle)
            for site in [url,url.replace('127.0.0.1','localhost')]:
                driver.get(site)
                measured=driver.execute_script(INSPECT+"return ['webgl','webgl2'].map(k=>inspect(document.createElement('canvas').getContext(k)));")
                check([x.get('caps') for x in measured]==[x.get('caps') for x in masked],'own protected baseline survives site navigation '+site)
            # Recreate saved globals after navigation for the freeze test.
            masked=measure()
            chrome('Services.prefs.setBoolPref("cloakfox.opt.gpu_backend_profiles",false);')
            existing=driver.execute_script(INSPECT+'return cohortContexts.map(inspect);')
            check([x.get('caps') for x in existing]==[x.get('caps') for x in masked],'existing contexts retain frozen profile after toggle')
            restored=driver.execute_async_script(r"""const done=arguments[0];const gl=cohortContexts[0];const ext=gl.getExtension('WEBGL_lose_context');
              if(!ext){done({unsupported:true});return;}
              gl.canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();setTimeout(()=>ext.restoreContext(),50)},{once:true});
              gl.canvas.addEventListener('webglcontextrestored',()=>done({renderer:gl.getParameter(gl.RENDERER),texture:gl.getParameter(gl.MAX_TEXTURE_SIZE)}),{once:true});
              ext.loseContext();setTimeout(()=>done({timeout:true}),5000);""")
            result['measurements']['restoration']=restored
            check(restored.get('renderer')=='WebGL' and restored.get('texture')==2048,'loss/restoration retains frozen profile after toggle')
            unprofiled=measure();result['measurements']['profileOff']=unprofiled
            check(all(x.get('caps',{}).get('MAX_VERTEX_UNIFORM_VECTORS')==13 for x in unprofiled),'disabling mode restores saved legacy overrides for new contexts')
            chrome('Services.prefs.setBoolPref("cloakfox.opt.gpu_backend_profiles",true);Services.prefs.savePrefFile(null);')
            driver.quit();driver=launch()
            saved=chrome("return JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_0'));")
            check(saved.get('webGl:backend_profile') is True and saved.get('gpu:sentinel')=='retained' and saved.get('fingerprint:secret')==before.get('fingerprint:secret') and saved.get('canvas:seed')==before.get('canvas:seed') and saved.get('webGl:parameters')==before.get('webGl:parameters'),'restart preserves opt-in, seeds and manual GPU tables')
            restarted=measure();result['measurements']['restart']=restarted
            check([x.get('caps') for x in restarted]==[x.get('caps') for x in masked],'restart retains deterministic baseline')
            chrome('Services.prefs.setBoolPref("cloakfox.enabled",false);')
            masteroff=measure();result['measurements']['masterOff']=masteroff
            check([x.get('caps') for x in masteroff]==[x.get('caps') for x in native] and [x.get('identity') for x in masteroff]==[x.get('identity') for x in native],'master-off new contexts retain native GPU behavior')
        finally:
            driver.quit();server.shutdown();server.server_close()
            (report/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return 0 if all(c['pass'] for c in result['checks']) else 1

if __name__=='__main__':raise SystemExit(main())
