"""Real canvas capture -> video -> VideoFrame/bitmap consumers, no device access."""
import json,os,tempfile,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_canvas_consistency import Page
SCRIPT=r'''
const done=arguments[arguments.length-1];
(async()=>{
 const source=document.createElement('canvas');source.width=64;source.height=48;
 const ctx=source.getContext('2d');function draw(){ctx.fillStyle='#807060';ctx.fillRect(0,0,64,48);
 ctx.fillStyle='#204060';ctx.fillRect(12,8,36,24);ctx.font='14px sans-serif';ctx.fillStyle='#e0d0c0';ctx.fillText('AV Ω',3,38);}draw();
 const reference=Array.from(ctx.getImageData(0,0,64,48).data);
 const stream=source.captureStream(10);const video=document.createElement('video');video.muted=true;video.srcObject=stream;
 const timer=setInterval(draw,50);
 try{
  const ready=new Promise((r,j)=>{const t=setTimeout(()=>j(Error('capture frame timeout')),15000);video.requestVideoFrameCallback(()=>{clearTimeout(t);r()})});await video.play();await ready;
  function read(input){const c=new OffscreenCanvas(64,48),x=c.getContext('2d');x.drawImage(input,0,0,64,48);return Array.from(x.getImageData(0,0,64,48).data)}
  const fromVideo=read(video),frame=new VideoFrame(video,{timestamp:1});
  try{const fromFrame=read(frame),bitmap=await createImageBitmap(frame);try{done({reference,fromVideo,fromFrame,fromBitmap:read(bitmap),frameFormat:frame.format})}finally{bitmap.close()}}
  finally{frame.close()}
 }finally{clearInterval(timer);stream.getTracks().forEach(t=>t.stop());video.srcObject=null}
})().catch(e=>done({error:String(e),stack:e.stack}));
'''
def main():
 out=Path(os.environ.get('REPORT_DIR','/tmp/cfx-canonical-capture'));out.mkdir(parents=True,exist_ok=True);report={'checks':[]}
 def check(ok,name):report['checks'].append({'pass':bool(ok),'name':name});print(('PASS 'if ok else'FAIL ')+name,flush=True)
 server=ThreadingHTTPServer(('127.0.0.1',0),Page);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with tempfile.TemporaryDirectory(prefix='cfx-canonical-capture-')as profile:
   opts=Options();opts.binary_location=os.environ['CLOAKFOX_BIN']
   for arg in ['-headless','-purgecaches','-profile',profile]:opts.add_argument(arg)
   opts.set_preference('cloakfox.experimental.canvas_pipeline',True);opts.set_preference('media.autoplay.default',0)
   Path(profile,'user.js').write_text('user_pref("cloakfox.enabled",true);\n')
   d=webdriver.Firefox(options=opts,service=Service(service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
   try:
    d.set_script_timeout(45);d.set_context('chrome');report['runtime']=d.execute_script('return{buildID:Services.appinfo.appBuildID,version:Services.appinfo.version}')
    d.set_context('content');d.get(f'http://127.0.0.1:{server.server_port}/');result=d.execute_async_script(SCRIPT);check('error'not in result,'capture/VideoFrame corpus completes')
    if'error'not in result:
     for key in ['fromVideo','fromFrame','fromBitmap']:
      mismatch=sum(a!=b for a,b in zip(result['reference'],result[key]));check(mismatch==0,key+' matches canonical source including text');report[key+'Mismatches']=mismatch
     report['frameFormat']=result['frameFormat']
    else:report['error']=result
   finally:d.quit()
 finally:
  server.shutdown();server.server_close();(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 return int(any(not c['pass']for c in report['checks']))
if __name__=='__main__':raise SystemExit(main())
