"""Installed Mac GPU corpus, disposable profiles and loopback content only.

CLOAKFOX_BIN selects the candidate. --expect-backend-failure is for a disposable
app copy with missing/tampered canonical libraries; this script never mutates an
app. A vendor string alone is never accepted as proof of canonical routing.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_canvas_consistency import Page

SCRIPT = r'''
const done=arguments[arguments.length-1];
async function glSample(kind){
 const c=document.createElement('canvas');c.width=8;c.height=8;
 const g=c.getContext(kind,{preserveDrawingBuffer:true,antialias:false});
 if(!g)return{available:false};
 const two=kind==='webgl2';
 function shader(type,code){const s=g.createShader(type);g.shaderSource(s,code);g.compileShader(s);if(!g.getShaderParameter(s,g.COMPILE_STATUS))throw Error(g.getShaderInfoLog(s));return s;}
 const p=g.createProgram();
 g.attachShader(p,shader(g.VERTEX_SHADER,two?'#version 300 es\nin vec2 p;out vec2 uv;void main(){uv=(p+1.)*.5;gl_Position=vec4(p,0,1);}':'attribute vec2 p;varying vec2 uv;void main(){uv=(p+1.)*.5;gl_Position=vec4(p,0,1);}'));
 g.attachShader(p,shader(g.FRAGMENT_SHADER,two?'#version 300 es\nprecision highp float;in vec2 uv;uniform sampler2D tex;out vec4 o;void main(){o=texture(tex,uv)*vec4(uv,1,1);}':'precision highp float;varying vec2 uv;uniform sampler2D tex;void main(){gl_FragColor=texture2D(tex,uv)*vec4(uv,1,1);}'));
 g.linkProgram(p);if(!g.getProgramParameter(p,g.LINK_STATUS))throw Error(g.getProgramInfoLog(p));g.useProgram(p);
 const b=g.createBuffer();g.bindBuffer(g.ARRAY_BUFFER,b);g.bufferData(g.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),g.STATIC_DRAW);
 const a=g.getAttribLocation(p,'p');g.enableVertexAttribArray(a);g.vertexAttribPointer(a,2,g.FLOAT,false,0,0);
 const t=g.createTexture();g.bindTexture(g.TEXTURE_2D,t);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MIN_FILTER,g.NEAREST);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MAG_FILTER,g.NEAREST);
 g.texImage2D(g.TEXTURE_2D,0,g.RGBA,2,2,0,g.RGBA,g.UNSIGNED_BYTE,new Uint8Array([240,40,90,255,30,210,80,255,100,70,230,255,200,160,20,255]));
 const authoredPixels=new Uint8ClampedArray([240,40,90,255,30,210,80,255,100,70,230,255,200,160,20,255]);g.texImage2D(g.TEXTURE_2D,0,g.RGBA,g.RGBA,g.UNSIGNED_BYTE,new ImageData(authoredPixels,2,2));const imageDataUploadError=g.getError();
 g.viewport(0,0,8,8);g.drawArrays(g.TRIANGLES,0,3);g.finish();
 const read=()=>{const v=new Uint8Array(256);g.readPixels(0,0,8,8,g.RGBA,g.UNSIGNED_BYTE,v);return Array.from(v)};
 const pixels=read(),repeat=read(),error=g.getError();
 const round=document.createElement('canvas');round.width=round.height=8;const x=round.getContext('2d');x.drawImage(c,0,0);const roundtrip=Array.from(x.getImageData(0,0,8,8).data);
 let pboError=null,typedError=null,authoredBuffer=null,unknownBufferError=null,unknownBufferDestination=null,unknownInputError=null;
 if(two){
  const f=g.createFramebuffer();g.bindFramebuffer(g.FRAMEBUFFER,f);const ft=g.createTexture();g.bindTexture(g.TEXTURE_2D,ft);g.texImage2D(g.TEXTURE_2D,0,g.RGBA8UI,1,1,0,g.RGBA_INTEGER,g.UNSIGNED_BYTE,null);g.framebufferTexture2D(g.FRAMEBUFFER,g.COLOR_ATTACHMENT0,g.TEXTURE_2D,ft,0);g.readPixels(0,0,1,1,g.RGBA_INTEGER,g.UNSIGNED_BYTE,new Uint8Array(4));typedError=g.getError();g.bindFramebuffer(g.FRAMEBUFFER,null);
  const pb=g.createBuffer();g.bindBuffer(g.PIXEL_PACK_BUFFER,pb);g.bufferData(g.PIXEL_PACK_BUFFER,256,g.STREAM_READ);g.readPixels(0,0,8,8,g.RGBA,g.UNSIGNED_BYTE,0);pboError=g.getError();g.bindBuffer(g.PIXEL_PACK_BUFFER,null);
  const authored=g.createBuffer();g.bindBuffer(g.COPY_READ_BUFFER,authored);g.bufferData(g.COPY_READ_BUFFER,new Uint8Array([5,17,39,201]),g.STATIC_READ);const authoredRead=new Uint8Array(4);g.getBufferSubData(g.COPY_READ_BUFFER,0,authoredRead);authoredBuffer=Array.from(authoredRead);if(g.getError()!==0)throw Error('authored buffer readback failed');
  const image=new Image();const url=URL.createObjectURL(new Blob(['<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"><foreignObject width="2" height="2"><div xmlns="http://www.w3.org/1999/xhtml" style="background:rgb(70,120,190);width:2px;height:2px">x</div></foreignObject></svg>'],{type:'image/svg+xml'}));
  try{await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(Error('unknown GL SVG failed to load'));image.src=url})}finally{URL.revokeObjectURL(url)}
  g.bindTexture(g.TEXTURE_2D,g.createTexture());g.texImage2D(g.TEXTURE_2D,0,g.RGBA,g.RGBA,g.UNSIGNED_BYTE,image);unknownInputError=g.getError();const sentinel=new Uint8Array([77,77,77,77]);g.getBufferSubData(g.COPY_READ_BUFFER,0,sentinel);unknownBufferError=g.getError();unknownBufferDestination=Array.from(sentinel);
 }
 return{available:true,pixels,repeat,error,roundtrip,typedError,pboError,imageDataUploadError,authoredBuffer,unknownInputError,unknownBufferError,unknownBufferDestination};
}
async function webgpuSample(){
 if(!navigator.gpu)return{available:false,reason:'navigator.gpu absent'};
 const adapter=await navigator.gpu.requestAdapter();if(!adapter)return{available:false,reason:'no adapter'};
 const device=await adapter.requestDevice();device.pushErrorScope('validation');
 const input=device.createBuffer({size:64,usage:GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_SRC});
 const read=device.createBuffer({size:64,usage:GPUBufferUsage.MAP_READ|GPUBufferUsage.COPY_DST});
 const module=device.createShaderModule({code:'@group(0) @binding(0) var<storage,read_write> a:array<u32>; @compute @workgroup_size(16) fn main(@builtin(global_invocation_id) id:vec3u){a[id.x]=id.x*17u+3u;}'});
 const pipeline=device.createComputePipeline({layout:'auto',compute:{module,entryPoint:'main'}});const bind=device.createBindGroup({layout:pipeline.getBindGroupLayout(0),entries:[{binding:0,resource:{buffer:input}}]});
 let encoder=device.createCommandEncoder();const pass=encoder.beginComputePass();pass.setPipeline(pipeline);pass.setBindGroup(0,bind);pass.dispatchWorkgroups(1);pass.end();encoder.copyBufferToBuffer(input,0,read,0,64);device.queue.submit([encoder.finish()]);await read.mapAsync(GPUMapMode.READ);const compute=Array.from(new Uint32Array(read.getMappedRange()));read.unmap();
 const source=document.createElement('canvas');source.width=source.height=2;const s=source.getContext('2d');s.fillStyle='rgb(40,110,180)';s.fillRect(0,0,2,2);
 const texture=device.createTexture({size:[2,2],format:'rgba8unorm',usage:GPUTextureUsage.COPY_DST|GPUTextureUsage.COPY_SRC|GPUTextureUsage.TEXTURE_BINDING|GPUTextureUsage.RENDER_ATTACHMENT});device.queue.copyExternalImageToTexture({source},{texture},[2,2]);
 const texRead=device.createBuffer({size:512,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});encoder=device.createCommandEncoder();encoder.copyTextureToBuffer({texture},{buffer:texRead,bytesPerRow:256},[2,2]);device.queue.submit([encoder.finish()]);await texRead.mapAsync(GPUMapMode.READ);const raw=new Uint8Array(texRead.getMappedRange());const externalUpload=[...raw.slice(0,8),...raw.slice(256,264)];texRead.unmap();
 const canvas=document.createElement('canvas');canvas.width=canvas.height=8;document.body.append(canvas);const context=canvas.getContext('webgpu');const format=navigator.gpu.getPreferredCanvasFormat();context.configure({device,format,alphaMode:'opaque'});
 const renderModule=device.createShaderModule({code:'@vertex fn vs(@builtin(vertex_index) i:u32)->@builtin(position) vec4f {var p=array<vec2f,3>(vec2f(-1,-1),vec2f(3,-1),vec2f(-1,3));return vec4f(p[i],0,1);} @fragment fn fs(@builtin(position) p:vec4f)->@location(0) vec4f{return vec4f(p.x/8.,p.y/8.,0.5,1.);}'});
 const rp=device.createRenderPipeline({layout:'auto',vertex:{module:renderModule,entryPoint:'vs'},fragment:{module:renderModule,entryPoint:'fs',targets:[{format}]}});encoder=device.createCommandEncoder();const render=encoder.beginRenderPass({colorAttachments:[{view:context.getCurrentTexture().createView(),loadOp:'clear',storeOp:'store',clearValue:[0,0,0,1]}]});render.setPipeline(rp);render.draw(3);render.end();device.queue.submit([encoder.finish()]);await device.queue.onSubmittedWorkDone();
 const snap=document.createElement('canvas');snap.width=snap.height=8;const sx=snap.getContext('2d');sx.drawImage(canvas,0,0);const presentation=Array.from(sx.getImageData(0,0,8,8).data);
 const validation=await device.popErrorScope();
 // foreignObject is an explicitly untracked SVG producer. It must poison a
 // canonical device before any copy/shader result can be mapped for reading.
 const unknownImage=new Image();const unknownURL=URL.createObjectURL(new Blob(['<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"><foreignObject width="2" height="2"><div xmlns="http://www.w3.org/1999/xhtml" style="background:rgb(70,120,190);width:2px;height:2px">x</div></foreignObject></svg>'],{type:'image/svg+xml'}));
 try{await new Promise((resolve,reject)=>{unknownImage.onload=resolve;unknownImage.onerror=()=>reject(Error('unknown-source SVG failed to load'));unknownImage.src=unknownURL})}finally{URL.revokeObjectURL(unknownURL)}
 device.pushErrorScope('validation');
 device.queue.copyExternalImageToTexture({source:unknownImage},{texture},[2,2]);const unknownInputValidation=await device.popErrorScope();device.pushErrorScope('validation');encoder=device.createCommandEncoder();encoder.copyTextureToBuffer({texture},{buffer:texRead,bytesPerRow:256},[2,2]);device.queue.submit([encoder.finish()]);
 let unknownMapReadDenied=false,unknownMapError=null;
 try{await texRead.mapAsync(GPUMapMode.READ);texRead.unmap()}catch(e){unknownMapError={name:e.name,message:e.message};unknownMapReadDenied=e.name==='OperationError'}
 const unknownValidation=await device.popErrorScope();
 const write=device.createBuffer({size:4,usage:GPUBufferUsage.MAP_WRITE|GPUBufferUsage.COPY_SRC});let mapWriteAllowed=false;
 try{await write.mapAsync(GPUMapMode.WRITE);new Uint32Array(write.getMappedRange())[0]=123;write.unmap();mapWriteAllowed=true}catch(e){unknownMapError={...(unknownMapError||{}),writeError:String(e)}}
 let unknownDataURLDenied=false,unknownDataURLError=null;
 try{const url=canvas.toDataURL();unknownDataURLDenied=url==='data:,'}catch(e){unknownDataURLDenied=true;unknownDataURLError={name:e.name,message:e.message}}
 const blobResult=await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(Error('toBlob timeout')),15000);try{canvas.toBlob(blob=>{clearTimeout(timeout);resolve({denied:blob===null,error:null})})}catch(e){clearTimeout(timeout);resolve({denied:true,error:{name:e.name,message:e.message}})}});
 device.destroy();return{available:true,compute,externalUpload,presentation,validation:validation?validation.message:null,unknownInputValidation:unknownInputValidation?unknownInputValidation.message:null,unknownMapReadDenied,unknownMapError,unknownValidation:unknownValidation?unknownValidation.message:null,mapWriteAllowed,unknownDataURLDenied,unknownDataURLError,unknownBlobDenied:blobResult.denied,unknownBlobError:blobResult.error};
}
(async()=>{const result={};for(const kind of ['webgl','webgl2']){try{result[kind]=await glSample(kind)}catch(e){result[kind]={error:String(e),stack:e.stack}}}try{result.webgpu=await webgpuSample()}catch(e){result.webgpu={error:String(e),stack:e.stack}}done(result)})().catch(e=>done({error:String(e),stack:e.stack}));
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expect-backend-failure',action='store_true')
    args=parser.parse_args()
    output=Path(os.environ.get('REPORT_DIR','/tmp/cloakfox-canonical-gpu'));output.mkdir(parents=True,exist_ok=True)
    report={'binary':os.environ['CLOAKFOX_BIN'],'scope':'installed macOS only; actual CPU routing also requires missing/tampered bundle runs','checks':[],'samples':{}}
    def check(value,name):
        report['checks'].append({'name':name,'pass':bool(value)});print(('PASS 'if value else'FAIL ')+name,flush=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),Page);threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-gpu-corpus-') as profile:
            options=Options();options.binary_location=report['binary']
            for arg in ['-purgecaches','-profile',profile]:options.add_argument(arg)
            if os.environ.get('CLOAKFOX_HEADFUL')!='1':options.add_argument('-headless')
            options.set_preference('dom.webgpu.enabled',True)
            options.set_preference('cloakfox.opt.webgl_typed_readback_disabled',True)
            driver=webdriver.Firefox(options=options,service=Service(service_args=['--allow-system-access'],log_output=str(output/'gecko.log')))
            try:
                driver.set_script_timeout(120)
                modes=[('native-bundle-failure',False,False),('canonical-failure',True,True)] if args.expect_backend_failure else [('native',False,False),('legacy',True,False),('canonical',True,True),('canonical-repeat',True,True)]
                for mode,master,pipeline in modes:
                    driver.set_context('chrome')
                    driver.execute_script("Services.prefs.setBoolPref('cloakfox.enabled',arguments[0]);Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',arguments[1]);const k='cloakfox.s.cloak_cfg_0',c=JSON.parse(Services.prefs.getStringPref(k,'{}'));c['webgl:typed_readback:disabled']=!arguments[1];c['navigator:webgpu:disabled']=false;Services.prefs.setStringPref(k,JSON.stringify(c));",master,pipeline)
                    report['runtime']=driver.execute_script('return {buildID:Services.appinfo.appBuildID,version:Services.appinfo.version}')
                    driver.set_context('content');driver.get(f'http://127.0.0.1:{server.server_port}/');sample=driver.execute_async_script(SCRIPT);report['samples'][mode]=sample
                    for kind in ['webgl','webgl2','webgpu']:
                        value=sample.get(kind,{})
                        if args.expect_backend_failure and pipeline:
                            check(value.get('available') is False,kind+' fails closed with rejected canonical bundle');continue
                        check(value.get('available') is True,mode+' '+kind+' creates actual context/device')
                        if not value.get('available'):continue
                        if kind=='webgpu':
                            check(value['compute']==[i*17+3 for i in range(16)],mode+' WebGPU compute/map exact authored integers')
                            check(value['validation'] is None,mode+' WebGPU upload/render passes validation')
                            check(len(set(value['externalUpload']))>2,mode+' external canvas upload contains pixels')
                            check(len(set(value['presentation']))>8,mode+' WebGPU canvas presentation/snapshot nonempty')
                            check(bool(value['unknownInputValidation'])==pipeline,mode+' WebGPU unverified image input refused before upload')
                            check(value['mapWriteAllowed'],mode+' WebGPU MAP_WRITE remains usable after unknown import')
                            check(value['unknownMapReadDenied']==pipeline,mode+' WebGPU unknown-source MAP_READ follows frozen canonical policy')
                            check(value['unknownDataURLDenied']==pipeline,mode+' WebGPU unknown-source toDataURL follows canonical policy')
                            check(value['unknownBlobDenied']==pipeline,mode+' WebGPU unknown-source toBlob follows canonical policy')
                        else:
                            check(value['error']==0,mode+' '+kind+' shader/texture/readback has no GL error')
                            check(value['imageDataUploadError']==0,mode+' '+kind+' authored ImageData upload succeeds')
                            check(value['pixels']==value['repeat'],mode+' '+kind+' repeated readback stable')
                            check(len(set(value['pixels']))>8 and len(set(value['roundtrip']))>8,mode+' '+kind+' texture shader and canvas roundtrip contain pixels')
                            if kind=='webgl2':
                                check(value['unknownInputError']==(1282 if pipeline else 0),mode+' GL2 unverified input refused before upload')
                                check(value['authoredBuffer']==[5,17,39,201],mode+' authored GL2 buffer readback remains exact')
                                check(value['unknownBufferError']==(1282 if pipeline else 0),mode+' poisoned GL2 buffer readback follows canonical policy')
                                check(value['unknownBufferDestination']==([77,77,77,77] if pipeline else [5,17,39,201]),mode+' poisoned GL2 readback leaves destination unchanged')
                            if kind=='webgl2' and master:
                                check(value['typedError']==1282,mode+' strict precise typed readback denied')
                                check(value['pboError']==1282,mode+' strict PBO readback denied')
                if not args.expect_backend_failure:
                    check(report['samples']['canonical']==report['samples']['canonical-repeat'],'canonical corpus stable across reload')
            finally:driver.quit()
    finally:
        server.shutdown();server.server_close();(output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return int(any(not check['pass'] for check in report['checks']))


if __name__=='__main__':raise SystemExit(main())
