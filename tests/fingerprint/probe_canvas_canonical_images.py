"""Installed fixed-raster round trips, animation, and SVG cache policy transitions."""
import base64,io,json,os,tempfile,threading,time
from pathlib import Path
from http.server import ThreadingHTTPServer
from PIL import Image
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_canvas_consistency import Page
INIT=r'''
const done=arguments[arguments.length-1], png=arguments[0];
(async()=>{
 window.svgSource='<svg xmlns="http://www.w3.org/2000/svg" width="160" height="80"><rect width="160" height="80" fill="#807060"/><text x="3" y="54" font-size="40" font-family="sans-serif">AV Ω שלום</text></svg>';
 window.heldSVG=new Image();heldSVG.src='data:image/svg+xml,'+encodeURIComponent(svgSource);await heldSVG.decode();
 const c=document.createElement('canvas');c.width=160;c.height=80;c.getContext('2d').drawImage(heldSVG,0,0);c.getContext('2d').getImageData(0,0,160,80);
 window.heldRaster=new Image();heldRaster.src='data:image/png;base64,'+png;await heldRaster.decode();c.getContext('2d').drawImage(heldRaster,0,0);c.getContext('2d').getImageData(0,0,160,80);
 window.heldNativeCanvas=document.createElement('canvas');heldNativeCanvas.width=160;heldNativeCanvas.height=80;
 const native=heldNativeCanvas.getContext('2d');native.fillStyle='#807060';native.fillRect(0,0,160,80);native.fillStyle='#204060';native.font='40px sans-serif';native.fillText('Native Ω',3,54);
 done({loaded:true});
})().catch(e=>done({error:String(e)}));
'''
SCRIPT=r'''
const done=arguments[arguments.length-1], gif=arguments[0], crossURL=arguments[1];
(async()=>{
 const equal=(a,b)=>a.length===b.length&&a.every((v,i)=>v===b[i]);
 function read(input,w=160,h=80){const c=document.createElement('canvas');c.width=w;c.height=h;c.getContext('2d').drawImage(input,0,0);return Array.from(c.getContext('2d').getImageData(0,0,w,h).data)}
 const source=document.createElement('canvas');source.width=160;source.height=80;const x=source.getContext('2d');
 x.fillStyle='#807060';x.fillRect(0,0,160,80);x.fillStyle='#204060';x.beginPath();x.arc(73,37,24,.1,6);x.fill();x.font='22px sans-serif';x.fillText('AV 😀 שלום',3,64);
 const expected=Array.from(x.getImageData(0,0,160,80).data);
 const image=new Image();image.src=source.toDataURL();await image.decode();
 const blob=await new Promise(r=>source.toBlob(r));
 const result={png:equal(read(image),expected),bitmaps:{}};
 const rawRaster=[128,112,96,255];
 const tiny=new OffscreenCanvas(1,1);tiny.getContext('2d').fillStyle='#807060';tiny.getContext('2d').fillRect(0,0,1,1);
 heldNativeCanvas.getContext('2d').drawImage(tiny,159,79);
 const inherited=read(heldNativeCanvas),direct=Array.from(heldNativeCanvas.getContext('2d').getImageData(0,0,160,80).data);
 result.nativeHeldGuard=inherited.slice(0,160*8*4).some((v,i)=>v!==rawRaster[i%4]);
 result.nativeHeldStableGuard=equal(inherited,direct);
 const held=read(heldRaster);result.rasterOldCache=held.every((v,i)=>v===rawRaster[i%4]);
 const sameRaster=new Image();sameRaster.src=heldRaster.src;await sameRaster.decode();result.rasterSameURL=equal(read(sameRaster),held);
 const cross=new Image();cross.src=crossURL;await cross.decode();try{read(cross);result.cors=false}catch(error){result.cors=error.name==='SecurityError'}
 const untracked=new Image();untracked.src='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="160" height="80"><foreignObject width="160" height="80"><div xmlns="http://www.w3.org/1999/xhtml" style="width:160px;height:80px;background:#807060"></div></foreignObject></svg>');await untracked.decode();
 const guarded=read(untracked);result.foreignObjectFallback=guarded.every((v,i)=>i%4!==3||v===255)&&guarded.some((v,i)=>i%4!==3&&v!==rawRaster[i%4]);
 for(const option of ['default','none']){
  const bitmap=await createImageBitmap(blob,{colorSpaceConversion:option});
  try{result.bitmaps[option]=equal(read(bitmap),expected)}finally{bitmap.close()}
 }
 const fresh=new Image();fresh.src='data:image/svg+xml,'+encodeURIComponent(svgSource.replace('</svg>','<!--fresh--></svg>'));await fresh.decode();
 await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame);
 const old=read(heldSVG),now=read(fresh);result.svgOldCache=equal(old,now);
 const sameSVG=new Image();sameSVG.src=heldSVG.src;await sameSVG.decode();result.svgSameURL=equal(read(sameSVG),old);
 result.svgExactFill=old.slice(0,160*8*4).every((v,i)=>v===[128,112,96,255][i%4]);
 const animation=new Image();animation.src='data:image/gif;base64,'+gif;await animation.decode();
 result.animation=[];
 for(let n=0;n<4;n++){
  await new Promise(r=>setTimeout(r,100));const pixels=read(animation,16,16);
  result.animation.push(pixels.every((v,i)=>i%4===3?v===255:[128,112,96][i%4]===v)||pixels.every((v,i)=>i%4===3?v===255:[32,64,96][i%4]===v));
 }
 done(result);
})().catch(e=>done({error:String(e),stack:e.stack}));
'''
def png_fixture():
 buffer=io.BytesIO();Image.new('RGB',(160,80),(128,112,96)).save(buffer,format='PNG');return buffer.getvalue()
class ImagePage(Page):
 def do_GET(self):
  if self.path.startswith('/fixture.png'):
   data=png_fixture();self.send_response(200);self.send_header('Content-Type','image/png');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
  else:super().do_GET()
def gif_fixture():
 a=Image.new('RGB',(16,16),(128,112,96));b=Image.new('RGB',(16,16),(32,64,96));buffer=io.BytesIO();a.save(buffer,format='GIF',save_all=True,append_images=[b],duration=100,loop=0);return base64.b64encode(buffer.getvalue()).decode()
def main():
 out=Path(os.environ.get('REPORT_DIR','/tmp/cfx-canonical-images'));out.mkdir(parents=True,exist_ok=True);report={'checks':[]}
 def check(ok,name):report['checks'].append({'pass':bool(ok),'name':name});print(('PASS 'if ok else'FAIL ')+name,flush=True)
 server=ThreadingHTTPServer(('127.0.0.1',0),ImagePage);threading.Thread(target=server.serve_forever,daemon=True).start()
 cross=ThreadingHTTPServer(('127.0.0.1',0),ImagePage);threading.Thread(target=cross.serve_forever,daemon=True).start()
 try:
  with tempfile.TemporaryDirectory(prefix='cfx-canonical-images-')as profile:
   opts=Options();opts.binary_location=os.environ['CLOAKFOX_BIN']
   for arg in ['-headless','-purgecaches','-profile',profile]:opts.add_argument(arg)
   opts.set_preference('cloakfox.experimental.canvas_pipeline',False)
   d=webdriver.Firefox(options=opts,service=Service(service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
   try:
    d.set_script_timeout(45);d.set_context('chrome');report['runtime']=d.execute_script('return{buildID:Services.appinfo.appBuildID,version:Services.appinfo.version}')
    d.execute_script("Services.prefs.setBoolPref('cloakfox.enabled',true);const key='cloakfox.s.cloak_cfg_0';const cfg=JSON.parse(Services.prefs.getStringPref(key,'{}'));cfg['canvas:seed']=111111;cfg['fonts:spacing_seed']=222222;cfg['fingerprint:secret']='ABEiM0RVZneImaq7zN3u/wARIjNEVWZ3iJmqu8zd7v8=';Services.prefs.setStringPref(key,JSON.stringify(cfg));")
    time.sleep(.4);d.set_context('content');d.get(f'http://127.0.0.1:{server.server_port}/');time.sleep(.4)
    initial=d.execute_async_script(INIT,base64.b64encode(png_fixture()).decode());check('error'not in initial,'pref-off SVG image and surface cache initialized')
    d.set_context('chrome');d.execute_script("Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',true);");time.sleep(.5);d.set_context('content')
    result=d.execute_async_script(SCRIPT,gif_fixture(),f'http://127.0.0.1:{cross.server_port}/fixture.png');check('error'not in result,'canonical image corpus completes');report['results']=result
    if'error'not in result:
     check(result['nativeHeldGuard'],'native context cannot inherit canonical producer proof from a tiny import')
     check(result['nativeHeldStableGuard'],'native held canvas and downstream import retain the same fallback guard')
     check(result['rasterOldCache'],'pref-off held PNG surface is decoded with fixed policy')
     check(result['rasterSameURL'],'same PNG URL reuses only matching fixed decode variant')
     check(result['svgSameURL'],'same SVG URL cache remains consistent after toggle')
     check(result['cors'],'verified raster proof preserves cross-origin taint')
     check(result['foreignObjectFallback'],'untracked foreignObject retains fallback extraction guard')
     check(result['png'],'canonical PNG encode/decode/draw/read remains exact')
     for mode,ok in result['bitmaps'].items():check(ok,'PNG Blob ImageBitmap '+mode+' color option remains exact')
     check(result['svgOldCache'],'pref-off cached SVG agrees with freshly loaded canonical SVG')
     check(result['svgExactFill'],'verified SVG exact opaque fill avoids fallback noise')
     check(all(result['animation']),'animated common raster compositor uses fixed decoded frames')
   finally:d.quit()
 finally:
  server.shutdown();server.server_close();cross.shutdown();cross.server_close();(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 return int(any(not c['pass']for c in report['checks']))
if __name__=='__main__':raise SystemExit(main())
