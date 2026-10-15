"""Pixel/ownership regressions through same-size bitmap/clone/worker transfers."""
import json,os,tempfile,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_canvas_consistency import Page
SCRIPT=r'''const done=arguments[arguments.length-1];
(async()=>{
 const make=()=>{const c=document.createElement('canvas');c.width=96;c.height=64;return c};
 const source=make(),ctx=source.getContext('2d');ctx.fillStyle='#487baf';ctx.fillRect(0,0,96,64);
 ctx.fillStyle='#e37141';ctx.beginPath();ctx.arc(40,30,20,.2,5);ctx.fill();ctx.font='14px sans-serif';ctx.fillText('AV ink',3,58);
 const bytes=c=>Array.from(c.getContext('2d').getImageData(0,0,96,64).data);
 const expected=bytes(source),checks=[];
 function compare(name,image,pattern=false){const c=make(),x=c.getContext('2d');if(pattern){x.fillStyle=x.createPattern(image,'no-repeat');x.fillRect(0,0,96,64)}else{x.drawImage(image,0,0)}const got=bytes(c);checks.push({name,pass:got.every((v,i)=>v===expected[i]),mismatches:got.reduce((n,v,i)=>n+(v!==expected[i]),0)});}
 compare('canvas drawImage',source);compare('canvas pattern',source,true);
 const bitmap=await createImageBitmap(source);compare('ImageBitmap drawImage',bitmap);compare('ImageBitmap pattern',bitmap,true);
 const cloned=structuredClone(bitmap);compare('structuredClone bitmap',cloned);
 const transferred=structuredClone(cloned,{transfer:[cloned]});compare('transferred bitmap',transferred);checks.push({name:'transferred source detached',pass:cloned.width===0});
 const cropped=await createImageBitmap(bitmap,0,0,96,64,{resizeWidth:96,resizeHeight:64,premultiplyAlpha:'premultiply'});compare('bitmap crop/resize/options',cropped);
 const renderer=make();renderer.getContext('bitmaprenderer').transferFromImageBitmap(await createImageBitmap(bitmap));compare('bitmaprenderer snapshot',renderer);
 const offscreen=new OffscreenCanvas(96,64);offscreen.getContext('2d').drawImage(source,0,0);compare('offscreen snapshot',offscreen);
 const worker=new Worker(URL.createObjectURL(new Blob([`onmessage=async({data})=>{const c=new OffscreenCanvas(96,64);c.getContext('2d').drawImage(data,0,0);const b=c.transferToImageBitmap();postMessage(b,[b]);}`],{type:'text/javascript'})));
 try{const fromWorker=await new Promise((r,j)=>{worker.onmessage=e=>r(e.data);worker.onerror=e=>j(Error(e.message));worker.postMessage(bitmap)});compare('worker cloned bitmap roundtrip',fromWorker);fromWorker.close();}finally{worker.terminate()}
 bitmap.close();transferred.close();cropped.close();done({checks});
})().catch(e=>done({error:String(e),stack:e.stack}));'''
def main():
 out=Path(os.environ.get('REPORT_DIR','/tmp/cfx-pixel-transfers'));out.mkdir(parents=True,exist_ok=True)
 server=ThreadingHTTPServer(('127.0.0.1',0),Page);threading.Thread(target=server.serve_forever,daemon=True).start()
 result={}
 try:
  with tempfile.TemporaryDirectory(prefix='cfx-pixel-transfers-') as profile:
   opts=Options();opts.binary_location=os.environ['CLOAKFOX_BIN']
   for arg in ['-headless','-purgecaches','-profile',profile]:opts.add_argument(arg)
   opts.set_preference('cloakfox.experimental.canvas_pipeline',True)
   Path(profile,'user.js').write_text('user_pref("cloakfox.enabled",true);\n')
   d=webdriver.Firefox(options=opts,service=Service(service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
   try:
    d.set_script_timeout(30);d.get(f'http://127.0.0.1:{server.server_port}/');result=d.execute_async_script(SCRIPT)
    for c in result.get('checks',[]):print(('PASS ' if c['pass'] else 'FAIL ')+c['name'],flush=True)
    if 'error' in result:print(result,flush=True)
   finally:d.quit()
 finally:server.shutdown();server.server_close();(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 return int('error' in result or not result.get('checks') or any(not c['pass'] for c in result['checks']))
if __name__=='__main__':raise SystemExit(main())
