"""Local canvas channels, WebGL2 limits and precise/PBO readback policy."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

PROBE = r'''
const c=document.createElement('canvas');c.width=96;c.height=48;
const x=c.getContext('2d');x.fillStyle='white';x.fillRect(0,0,96,48);
x.fillStyle='black';x.font='14px Arial';x.fillText('canvas privacy',3,20);
x.beginPath();x.arc(40,30,12,0,6.28);x.stroke();
const pixels=x.getImageData(0,0,96,48).data;
const hash=a=>{let h=0;for(const v of a)h=(h*31+v)>>>0;return h;};
const channels=[0,1,2].map(ch=>hash(pixels.filter((_,i)=>i%4===ch)));
x.clearRect(0,0,96,48);const cleared=x.getImageData(0,0,96,48).data.every(v=>v===0);
const gl=document.createElement('canvas').getContext('webgl2');
if(!gl)return {error:'no webgl2',channels,cleared};
const limits=[35375,35380,32883,35071].map(p=>gl.getParameter(p));
// Raw RGBA readPixels exposes shader RGB independently of alpha. Protect
// that surface even when the rendered pixels are completely transparent.
const zaCanvas=document.createElement('canvas');zaCanvas.width=32;zaCanvas.height=32;
const za=zaCanvas.getContext('webgl2',{preserveDrawingBuffer:true,antialias:false});
const zaProgram=za.createProgram();
for(const [type,source] of [[za.VERTEX_SHADER,`#version 300 es
in vec2 position;void main(){gl_Position=vec4(position,0,1);}`],
[za.FRAGMENT_SHADER,`#version 300 es
precision highp float;out vec4 color;void main(){color=vec4(0.25,0.5,0.75,0.0);}`]]){
 const shader=za.createShader(type);za.shaderSource(shader,source);za.compileShader(shader);
 za.attachShader(zaProgram,shader);
}
za.linkProgram(zaProgram);za.useProgram(zaProgram);
const zaBuffer=za.createBuffer();za.bindBuffer(za.ARRAY_BUFFER,zaBuffer);
za.bufferData(za.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),za.STATIC_DRAW);
const zaLocation=za.getAttribLocation(zaProgram,'position');
za.enableVertexAttribArray(zaLocation);za.vertexAttribPointer(zaLocation,2,za.FLOAT,false,0,0);
za.drawArrays(za.TRIANGLES,0,3);
const zeroAlphaPixels=new Uint8Array(32*32*4);
za.readPixels(0,0,32,32,za.RGBA,za.UNSIGNED_BYTE,zeroAlphaPixels);
const zeroAlphaError=za.getError();
const zeroAlphaChannels=[0,1,2].map(ch=>hash(zeroAlphaPixels.filter((_,i)=>i%4===ch)));
const zeroAlphaExact=zeroAlphaPixels.every((v,i)=>i%4!==3||v===0);
const zeroAlphaRgbNonzero=zeroAlphaPixels.every((v,i)=>i%4===3||v>0);

const fb=gl.createFramebuffer();gl.bindFramebuffer(gl.FRAMEBUFFER,fb);
const rb=gl.createRenderbuffer();gl.bindRenderbuffer(gl.RENDERBUFFER,rb);
gl.renderbufferStorage(gl.RENDERBUFFER,gl.RGBA8UI,2,2);
gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.RENDERBUFFER,rb);
gl.clearBufferuiv(gl.COLOR,0,new Uint32Array([17,123,231,255]));
const integer=new Uint8Array(16);integer.fill(88);
gl.readPixels(0,0,2,2,gl.RGBA_INTEGER,gl.UNSIGNED_BYTE,integer);
const integerError=gl.getError();
const floats=new Float32Array(16);floats.fill(88);
let floatError=null,floatStatus=null;
if(gl.getExtension('EXT_color_buffer_float')){
 gl.renderbufferStorage(gl.RENDERBUFFER,gl.RGBA32F,2,2);
 floatStatus=gl.checkFramebufferStatus(gl.FRAMEBUFFER);
 gl.clearBufferfv(gl.COLOR,0,new Float32Array([0.25,0.5,0.75,1]));
 gl.readPixels(0,0,2,2,gl.RGBA,gl.FLOAT,floats);floatError=gl.getError();
}
gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.clearColor(0.25,0.5,0.75,1);gl.clear(gl.COLOR_BUFFER_BIT);
const ordinary=new Uint8Array(16);gl.readPixels(0,0,2,2,gl.RGBA,gl.UNSIGNED_BYTE,ordinary);
const ordinaryError=gl.getError();
const tail=new Uint8Array(32);tail.fill(88);
gl.readPixels(0,0,2,2,gl.RGBA,gl.UNSIGNED_BYTE,tail);
const tailUnchanged=tail.slice(16).every(v=>v===88);
gl.pixelStorei(gl.PACK_ROW_LENGTH,4);gl.pixelStorei(gl.PACK_SKIP_ROWS,1);gl.pixelStorei(gl.PACK_SKIP_PIXELS,1);
const padded=new Uint8Array(64);padded.fill(88);
gl.readPixels(0,0,2,2,gl.RGBA,gl.UNSIGNED_BYTE,padded);
const paddingUnchanged=padded.every((v,i)=>((i>=20&&i<28)||(i>=36&&i<44))||v===88);
gl.pixelStorei(gl.PACK_ROW_LENGTH,0);gl.pixelStorei(gl.PACK_SKIP_ROWS,0);gl.pixelStorei(gl.PACK_SKIP_PIXELS,0);
const tooSmall=new Uint8Array(8);tooSmall.fill(88);
gl.readPixels(0,0,2,2,gl.RGBA,gl.UNSIGNED_BYTE,tooSmall);
const smallError=gl.getError(),smallUnchanged=tooSmall.every(v=>v===88);
const pbo=gl.createBuffer();gl.bindBuffer(gl.PIXEL_PACK_BUFFER,pbo);
gl.bufferData(gl.PIXEL_PACK_BUFFER,new Uint8Array(16).fill(88),gl.STREAM_READ);
gl.readPixels(0,0,2,2,gl.RGBA,gl.UNSIGNED_BYTE,0);const pboError=gl.getError();
const pboData=new Uint8Array(16);gl.getBufferSubData(gl.PIXEL_PACK_BUFFER,0,pboData);
gl.bindBuffer(gl.PIXEL_PACK_BUFFER,null);
gl.readPixels(0,0,2,2,gl.RGBA,0xdead,new Uint8Array(16));const invalidError=gl.getError();
return {channels,cleared,limits,zeroAlphaChannels,zeroAlphaError,zeroAlphaExact,zeroAlphaRgbNonzero,integer:Array.from(integer),integerError,
 floats:Array.from(floats),floatError,floatStatus,ordinaryError,pboError,
 pboData:Array.from(pboData),invalidError,tailUnchanged,paddingUnchanged,smallError,smallUnchanged};
'''


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b'<!doctype html><title>Graphics privacy fixture</title>')
    def log_message(self, *_):
        pass


def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),Page)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    results={};checks=[]
    def check(ok,label):
        checks.append({'pass':bool(ok),'name':label});print(('PASS ' if ok else 'FAIL ')+label,flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-graphics-') as temp:
            options=Options();options.binary_location=os.environ['CLOAKFOX_BIN'];options.add_argument('-headless')
            options.add_argument('-profile');options.add_argument(temp);options.add_argument('-purgecaches')
            Path(temp,'user.js').write_text('user_pref("cloakfox.enabled",true);\n')
            d=webdriver.Firefox(options=options,service=Service(service_args=['--allow-system-access'],log_output=temp+'/gecko.log'))
            try:
                url=f'http://127.0.0.1:{server.server_port}/'
                d.get(url);time.sleep(1)
                for name,seed,enabled,strict in [('a',111111,True,True),('b',999999,True,True),('repeat',111111,True,True),('compat',111111,True,False),('native',111111,False,True)]:
                    d.set_context('chrome')
                    d.execute_script('''
const cfg=JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_0','{}'));
cfg['canvas:seed']=arguments[0];cfg['webgl:typed_readback:disabled']=arguments[2];
cfg['webGl2:parameters']={...cfg['webGl2:parameters'],35375:24,35380:256,32883:2048,35071:256};
Services.prefs.setStringPref('cloakfox.s.cloak_cfg_0',JSON.stringify(cfg));
Services.prefs.setBoolPref('cloakfox.enabled',arguments[1]);
''',seed,enabled,strict)
                    d.set_context('content');time.sleep(.4);d.get(url+'?case='+name);time.sleep(.3)
                    results[name]=d.execute_script(PROBE)
            finally:
                d.quit()
        a,b,repeat=results['a'],results['b'],results['repeat']
        check(not any(v.get('error') for v in results.values()),'WebGL2 context available')
        check(all(a['channels'][i]!=b['channels'][i] for i in range(3)),'every canvas RGB channel isolated across seeds')
        check(a['channels']==repeat['channels'],'canvas channels deterministic')
        check(all(a['zeroAlphaChannels'][i]!=b['zeroAlphaChannels'][i] for i in range(3)),
              'every zero-alpha WebGL RGB channel isolated across seeds')
        check(a['zeroAlphaChannels']==repeat['zeroAlphaChannels'],
              'zero-alpha WebGL RGB noise deterministic')
        check(all(a['zeroAlphaChannels'][i]!=results['native']['zeroAlphaChannels'][i] for i in range(3)),
              'zero-alpha WebGL RGB differs from native readback')
        for name,r in results.items():
            check(r['cleared'],name+': clearRect stays exact zero')
            check(r['zeroAlphaError']==0 and r['zeroAlphaExact'] and r['zeroAlphaRgbNonzero'],
                  name+': shader readback succeeds with exact zero alpha and nonzero RGB')
            check(r['ordinaryError']==0,name+': ordinary RGBA8 succeeds')
            check(r['tailUnchanged'] and r['paddingUnchanged'],name+': readback padding and tail exact')
            check(r['smallError']==1282 and r['smallUnchanged'],name+': failed read leaves destination exact')
            check(r['invalidError']==1280,name+': invalid type keeps INVALID_ENUM')
            if name!='native':check(r['limits']==[24,256,2048,256],name+': WebGL2 limits masked')
            strict=name not in ('compat','native')
            check(r['integerError']==(1282 if strict else 0),name+': integer readback policy')
            check(r['floatError']==(1282 if strict else 0),name+': float readback policy')
            check(r['pboError']==(1282 if strict else 0),name+': PBO readback policy')
            if strict:
                check(r['integer']==[88]*16 and r['floats']==[88]*16 and r['pboData']==[88]*16,name+': denied destinations unchanged')
            else:
                check(r['integer']==[17,123,231,255]*4 and r['floats']==[.25,.5,.75,1]*4,name+': compute data exact')
        report=Path(os.environ.get('GRAPHICS_PROBE_REPORT','/tmp/cloakfox-graphics-privacy-results.json'))
        report.write_text(json.dumps({'checks':checks,'results':results},indent=2));print(report)
        return 0 if all(c['pass'] for c in checks) else 1
    finally:
        server.shutdown()


if __name__=='__main__':
    raise SystemExit(main())
