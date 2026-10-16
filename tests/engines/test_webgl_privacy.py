"""Actual WebGL1/2 pixel reads, pack layouts and PBO copy privacy checks."""
import hashlib
import http.server
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from probe_cef_isolation import Companion
from test_canvas_privacy import DRAW, READ

WORK = r"""function readGL(version='webgl2',pbo=false,packed=false) {
 const c=typeof document==='undefined'?new OffscreenCanvas(32,24):document.createElement('canvas');c.width=32;c.height=24;
 const gl=c.getContext(version,{preserveDrawingBuffer:true,antialias:false});if(!gl)throw new Error('No '+version);
 gl.clearColor(72/255,108/255,144/255,1);gl.clear(gl.COLOR_BUFFER_BIT);
 gl.enable(gl.SCISSOR_TEST);gl.scissor(3,24-4-9,17,9);gl.clearColor(141/255,79/255,203/255,1);gl.clear(gl.COLOR_BUFFER_BIT);gl.disable(gl.SCISSOR_TEST);
 const stride=packed?160:128,skip=packed?332:0,offset=16;
 if(packed){gl.pixelStorei(gl.PACK_ALIGNMENT,8);gl.pixelStorei(gl.PACK_ROW_LENGTH,40);gl.pixelStorei(gl.PACK_SKIP_PIXELS,3);gl.pixelStorei(gl.PACK_SKIP_ROWS,2)}
 const out=new Uint8Array(offset+skip+stride*23+128+32).fill(85);
 let copied=true;
 if(pbo){const b=gl.createBuffer();gl.bindBuffer(gl.PIXEL_PACK_BUFFER,b);gl.bufferData(gl.PIXEL_PACK_BUFFER,out,gl.STREAM_READ);
 gl.readPixels(0,0,32,24,gl.RGBA,gl.UNSIGNED_BYTE,offset);gl.getBufferSubData(gl.PIXEL_PACK_BUFFER,0,out);
 const copy=gl.createBuffer();gl.bindBuffer(gl.COPY_READ_BUFFER,b);gl.bindBuffer(gl.COPY_WRITE_BUFFER,copy);gl.bufferData(gl.COPY_WRITE_BUFFER,out.length,gl.STREAM_COPY);
 gl.copyBufferSubData(gl.COPY_READ_BUFFER,gl.COPY_WRITE_BUFFER,0,0,out.length);const other=new Uint8Array(out.length);gl.getBufferSubData(gl.COPY_WRITE_BUFFER,0,other);copied=other.every((v,i)=>v===out[i]);gl.bindBuffer(gl.PIXEL_PACK_BUFFER,null);
 }else if(version==='webgl2'){gl.readPixels(0,0,32,24,gl.RGBA,gl.UNSIGNED_BYTE,out,offset)}
 else{gl.readPixels(0,0,32,24,gl.RGBA,gl.UNSIGNED_BYTE,out.subarray(offset))}
 const top=[],active=new Set();for(let y=23;y>=0;y--)for(let x=0;x<128;x++){const i=offset+skip+y*stride+x;top.push(out[i]);active.add(i)}
 const padding=out.every((v,i)=>active.has(i)||v===85);
 if(packed){gl.pixelStorei(gl.PACK_ALIGNMENT,4);gl.pixelStorei(gl.PACK_ROW_LENGTH,0);gl.pixelStorei(gl.PACK_SKIP_PIXELS,0);gl.pixelStorei(gl.PACK_SKIP_ROWS,0)}
 const crop=new Uint8Array(17*9*4);gl.readPixels(3,11,17,9,gl.RGBA,gl.UNSIGNED_BYTE,crop);
 const cropTop=[];for(let y=8;y>=0;y--)cropTop.push(...crop.subarray(y*17*4,(y+1)*17*4));
 const expected=[];for(let y=4;y<13;y++)expected.push(...top.slice((y*32+3)*4,(y*32+20)*4));
 const debug=gl.getExtension('WEBGL_debug_renderer_info');
 return {pixels:top,padding,copied,crop:JSON.stringify(cropTop)===JSON.stringify(expected),error:gl.getError(),debug:debug!==null,supportedDebug:gl.getSupportedExtensions().includes('WEBGL_debug_renderer_info')};
}"""

class Fixture(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body=(WORK+"onmessage=e=>{try{postMessage(readGL(...e.data))}catch(e){postMessage({failure:String(e)})}}" if self.path=='/worker.js' else '<!doctype html><title>Owned WebGL fixture</title>').encode()
        self.send_response(200);self.send_header('Content-Type','application/javascript' if self.path.endswith('.js') else 'text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass

class WebGLPrivacy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value=os.environ.get('CLOAKFOX_CHROMIUM_BIN')
        if not value:raise unittest.SkipTest('Set CLOAKFOX_CHROMIUM_BIN')
        cls.binary=Path(value);cls.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Fixture)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start();cls.url=f'http://127.0.0.1:{cls.server.server_port}/'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def setUp(self):
        self.root=tempfile.TemporaryDirectory(prefix='cloakfox-webgl-');self.app=Companion(self.binary,Path(self.root.name))
    def tearDown(self):self.app.close();self.root.cleanup()
    def read(self,browser,version='webgl2',pbo=False,packed=False,worker=False):
        args=json.dumps([version,pbo,packed])
        expression=("new Promise((resolve,reject)=>{const w=new Worker('/worker.js');w.onmessage=e=>{w.terminate();resolve(e.data)};w.onerror=reject;w.postMessage("+args+")})" if worker else '(function(){'+WORK+'return readGL(...'+args+')})()')
        value=self.app.evaluate(browser,expression);self.assertNotIn('failure',value,value)
        self.assertEqual(value['error'],0);self.assertTrue(value['padding']);self.assertTrue(value['copied']);self.assertTrue(value['crop'])
        return value
    @staticmethod
    def digest(pixels):return hashlib.sha256(bytes(pixels)).hexdigest()
    def test_direct_gl1_gl2_pbo_and_pack_agree_with_canvas(self):
        browser=self.app.open('301',self.url);expected=self.digest(self.app.evaluate(browser,READ))
        for version,pbo,packed in [('webgl',False,False),('webgl2',False,False),('webgl2',False,True),('webgl2',True,False),('webgl2',True,True)]:
            with self.subTest(version=version,pbo=pbo,packed=packed):
                self.assertEqual(self.digest(self.read(browser,version,pbo,packed)['pixels']),expected)
    def test_container_site_worker_and_reload_identity(self):
        a=self.app.open('301',self.url);b=self.app.open('302',self.url);c=self.app.open('301',self.url.replace('127.0.0.1','localhost'))
        first=self.digest(self.read(a)['pixels'])
        self.assertNotEqual(first,self.digest(self.read(b)['pixels']))
        self.assertNotEqual(first,self.digest(self.read(c)['pixels']))
        self.assertEqual(first,self.digest(self.read(a,worker=True)['pixels']))
        self.assertEqual(first,self.digest(self.read(a,pbo=True,packed=True,worker=True)['pixels']))
        self.assertTrue(self.app.rpc('navigate',browser=a,url=self.url)['ok'])
        self.assertEqual(first,self.digest(self.read(a)['pixels']))
    def test_disabled_readback_is_exact_and_restores_debug_extension(self):
        opened=self.app.rpc('open',container='301',url=self.url,privacy={'canvas':False});self.assertTrue(opened['ok'],opened)
        browser=self.app.open('301',self.url);expected=self.digest(self.app.evaluate(browser,READ))
        for pbo,packed in [(False,False),(True,True)]:
            value=self.read(browser,pbo=pbo,packed=packed);self.assertEqual(self.digest(value['pixels']),expected);self.assertTrue(value['debug']);self.assertTrue(value['supportedDebug'])
    def test_gpu_debug_extension_is_hidden_only_when_enabled(self):
        browser=self.app.open('301',self.url);value=self.read(browser)
        self.assertFalse(value['debug']);self.assertFalse(value['supportedDebug'])
    def test_protected_shader_render_still_uses_native_webgl(self):
        browser=self.app.open('301',self.url)
        value=self.app.evaluate(browser,Path(__file__).with_name('webgl_render.js').read_text())
        self.assertEqual(value['error'],0,value)
        pixel=value['pixel']
        self.assertTrue(pixel[0]>=254 and pixel[1]<=1 and pixel[2]<=1 and pixel[3]==255,value)
    def test_clipped_reads_preserve_sentinels_for_default_and_attachment(self):
        browser=self.app.open('301',self.url)
        value=self.app.evaluate(browser,r"""(()=>{const checks=[];
for(const version of ['webgl','webgl2'])for(const attachment of [false,true])for(const pbo of (version==='webgl2'?[false,true]:[false])){
 const c=document.createElement('canvas');c.width=8;c.height=8;const g=c.getContext(version,{preserveDrawingBuffer:true});const extent=attachment?4:8;
 if(attachment){const t=g.createTexture();g.bindTexture(g.TEXTURE_2D,t);g.texImage2D(g.TEXTURE_2D,0,g.RGBA,extent,extent,0,g.RGBA,g.UNSIGNED_BYTE,null);const f=g.createFramebuffer();g.bindFramebuffer(g.FRAMEBUFFER,f);g.framebufferTexture2D(g.FRAMEBUFFER,g.COLOR_ATTACHMENT0,g.TEXTURE_2D,t,0)}
 g.clearColor(64/255,128/255,191/255,1);g.clear(g.COLOR_BUFFER_BIT);
 for(const [x,y,width,height] of [[extent-1,0,2,2],[-1,-1,3,3],[extent+1,0,2,1],[0,extent-1,2,2],[0,0,0,1]]){
 const out=new Uint8Array(width*height*4+8).fill(255);
 if(pbo){const b=g.createBuffer();g.bindBuffer(g.PIXEL_PACK_BUFFER,b);g.bufferData(g.PIXEL_PACK_BUFFER,out,g.STREAM_READ);g.readPixels(x,y,width,height,g.RGBA,g.UNSIGNED_BYTE,4);g.getBufferSubData(g.PIXEL_PACK_BUFFER,0,out);g.bindBuffer(g.PIXEL_PACK_BUFFER,null);g.deleteBuffer(b)}
 else if(version==='webgl2')g.readPixels(x,y,width,height,g.RGBA,g.UNSIGNED_BYTE,out,4);
 else g.readPixels(x,y,width,height,g.RGBA,g.UNSIGNED_BYTE,out.subarray(4));
 let preserved=out.slice(0,4).every(v=>v===255)&&out.slice(4+width*height*4).every(v=>v===255),inside=true;
 for(let row=0;row<height;row++)for(let column=0;column<width;column++){
 const pixel=out.slice(4+(row*width+column)*4,8+(row*width+column)*4);
 if(x+column<0||x+column>=extent||y+row<0||y+row>=extent)preserved&&=pixel.every(v=>v===255);
 else inside&&=pixel[3]===255&&[64,128,191].every((v,i)=>Math.abs(v-pixel[i])<=1);
 }
 checks.push({version,attachment,pbo,x,y,width,height,preserved,inside,error:g.getError()});
 }}return checks})()""")
        for check in value:
            self.assertEqual(check['error'],0,check)
            self.assertTrue(check['preserved'],check)
            self.assertTrue(check['inside'],check)
    def test_invalid_reads_preserve_destinations_and_pending_errors(self):
        browser=self.app.open('301',self.url)
        value=self.app.evaluate(browser,r"""(()=>{const c=document.createElement('canvas');c.width=8;c.height=8;const g=c.getContext('webgl2');
 const t=g.createTexture();g.bindTexture(g.TEXTURE_2D,t);g.texStorage2D(g.TEXTURE_2D,1,g.RGBA8UI,8,8);
 const f=g.createFramebuffer();g.bindFramebuffer(g.FRAMEBUFFER,f);g.framebufferTexture2D(g.FRAMEBUFFER,g.COLOR_ATTACHMENT0,g.TEXTURE_2D,t,0);
 const out=new Uint8Array(256).fill(255);g.readPixels(0,0,8,8,g.RGBA,g.UNSIGNED_BYTE,out);const bad=g.getError();
 const unchanged=out.every(v=>v===255);g.bindFramebuffer(g.FRAMEBUFFER,null);g.clearColor(.25,.5,.75,1);g.clear(g.COLOR_BUFFER_BIT);
 g.enable(0xdead);g.readPixels(0,0,8,8,g.RGBA,g.UNSIGNED_BYTE,out);const pending=g.getError(),end=g.getError();
 const b=g.createBuffer();g.bindBuffer(g.PIXEL_PACK_BUFFER,b);g.bufferData(g.PIXEL_PACK_BUFFER,new Uint8Array(256).fill(255),g.STREAM_READ);
 g.bindFramebuffer(g.FRAMEBUFFER,f);g.readPixels(0,0,8,8,g.RGBA,g.UNSIGNED_BYTE,0);const pboError=g.getError();g.getBufferSubData(g.PIXEL_PACK_BUFFER,0,out);
 return {unchanged,bad,pending,end,pboUnchanged:out.every(v=>v===255),pboError};})()""")
        self.assertEqual(value,{'unchanged':True,'bad':1282,'pending':1280,'end':0,'pboUnchanged':True,'pboError':1282})

if __name__=='__main__':unittest.main()
