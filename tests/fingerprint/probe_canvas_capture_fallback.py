"""Installed capture -> VideoFrame.copyTo coverage for unknown and canonical input.

Uses an unverified SVG foreignObject producer with known colors; no device access.
"""
import base64,json,os,struct,tempfile,threading,time,zlib
from pathlib import Path
from http.server import ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_canvas_consistency import Page
SCRIPT=r'''
const done=arguments[arguments.length-1], png=arguments[0];
(async()=>{
 const image=new Image();image.src='data:image/svg+xml;base64,'+png;await image.decode();
 const result={};
 for(const unknown of [false,true]){
  const source=document.createElement('canvas');source.width=64;source.height=48;
  const x=source.getContext('2d');
  function draw(){if(unknown)x.drawImage(image,0,0);else{x.fillStyle='#807060';x.fillRect(0,0,64,48)}}
  draw();const reference=Array.from(x.getImageData(0,0,64,48).data);
  const direct={};
  for(const kind of ['canvas','bitmap']){
   const input=kind==='canvas'?source:await createImageBitmap(source);
   const frame=new VideoFrame(input,{timestamp:1});
   try{
    const options={format:'RGBA'},buffer=new Uint8Array(frame.allocationSize(options));
    const layouts=await frame.copyTo(buffer,options),pixels=[];
    for(let y=0;y<48;y++)for(let i=0;i<64*4;i++)pixels.push(buffer[layouts[0].offset+y*layouts[0].stride+i]);
    direct[kind]={pixels};
   }catch(error){direct[kind]={copyDenied:error.name==='OperationError',error:String(error)}}
   finally{frame.close();if(kind==='bitmap')input.close()}
  }
  const stream=source.captureStream(30),video=document.createElement('video');video.muted=true;video.srcObject=stream;
  const timer=setInterval(draw,30);
  try{
   await video.play();await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(Error('capture frame timeout')),10000);video.requestVideoFrameCallback(()=>{clearTimeout(timeout);resolve()})});
   const frame=new VideoFrame(video,{timestamp:1});
   try{
    const options={format:'RGBA'},buffer=new Uint8Array(frame.allocationSize(options));
    const layout=await frame.copyTo(buffer,options),pixels=[];
    for(let y=0;y<48;y++)for(let i=0;i<64*4;i++)pixels.push(buffer[layout[0].offset+y*layout[0].stride+i]);
    const again=new Uint8Array(frame.allocationSize(options));await frame.copyTo(again,options);
    result[unknown?'unknown':'canonical']={reference,pixels,repeat:buffer.every((v,i)=>v===again[i]),format:frame.format,direct};
   }catch(error){result[unknown?'unknown':'canonical']={copyDenied:error.name==='OperationError',error:String(error),direct}}finally{frame.close()}
  }finally{clearInterval(timer);stream.getTracks().forEach(t=>t.stop());video.srcObject=null}
 }
 done(result);
})().catch(e=>done({error:String(e),stack:e.stack}));
'''
def unknown_fixture():
 source='<svg xmlns="http://www.w3.org/2000/svg" width="64" height="48"><foreignObject width="64" height="48"><div xmlns="http://www.w3.org/1999/xhtml" style="width:64px;height:48px;background:#807060"></div></foreignObject></svg>'
 return base64.b64encode(source.encode()).decode()
def main():
 out=Path(os.environ.get('REPORT_DIR','/tmp/cfx-capture-fallback'));out.mkdir(parents=True,exist_ok=True);report={'checks':[]}
 def check(ok,name):report['checks'].append({'pass':bool(ok),'name':name});print(('PASS 'if ok else'FAIL ')+name,flush=True)
 server=ThreadingHTTPServer(('127.0.0.1',0),Page);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with tempfile.TemporaryDirectory(prefix='cfx-capture-fallback-')as profile:
   opts=Options();opts.binary_location=os.environ['CLOAKFOX_BIN']
   for arg in ['-headless','-purgecaches','-profile',profile]:opts.add_argument(arg)
   opts.set_preference('cloakfox.experimental.canvas_pipeline',True);opts.set_preference('media.autoplay.default',0)
   d=webdriver.Firefox(options=opts,service=Service(service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
   try:
    d.set_script_timeout(45);d.set_context('chrome');report['runtime']=d.execute_script('return{buildID:Services.appinfo.appBuildID,version:Services.appinfo.version}')
    d.execute_script("const key='cloakfox.s.cloak_cfg_0';const cfg=JSON.parse(Services.prefs.getStringPref(key,'{}'));cfg['canvas:seed']=111111;cfg['fingerprint:secret']='ABEiM0RVZneImaq7zN3u/wARIjNEVWZ3iJmqu8zd7v8=';Services.prefs.setStringPref(key,JSON.stringify(cfg));")
    raw=[128,112,96,255]*(64*48)
    for label,enabled,pipeline in [('enabled',True,True),('disabled',False,True),('legacy',True,False)]:
     d.set_context('chrome');d.execute_script("Services.prefs.setBoolPref('cloakfox.enabled',arguments[0]);Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',arguments[1]);",enabled,pipeline);time.sleep(.4)
     d.set_context('content');d.get(f'http://127.0.0.1:{server.server_port}/');time.sleep(.4)
     result=d.execute_async_script(SCRIPT,unknown_fixture());check('error'not in result,label+' capture copyTo completes')
     if'error'in result:report[label]=result;continue
     for name,value in result.items():
      for kind,direct in value['direct'].items():
       if enabled and pipeline and name=='unknown':
        check(direct.get('copyDenied'),label+' unknown '+kind+' direct VideoFrame copyTo denied')
       else:
        check(direct.get('pixels')==raw,label+' '+name+' '+kind+' direct VideoFrame pixels remain exact')
      if value.get('copyDenied'):
       check(enabled and pipeline and name=='unknown',label+' '+name+' only unverified fullmode copy is refused')
       continue
      check(value['repeat'],label+' '+name+' repeated copyTo stable')
      check(all(v==255 for v in value['pixels'][3::4]),label+' '+name+' alpha retained')
     check(result['canonical']['pixels']==raw,label+' qualifying authored capture remains exact')
     if enabled and pipeline:
      check(result['unknown'].get('copyDenied'),'unknown source direct copyTo bypass is refused')
     else:check(result['unknown']['pixels']==raw,label+' unknown capture remains native')
     report[label]={name:{'format':v.get('format'),'rawMismatches':sum(a!=b for a,b in zip(raw,v.get('pixels',[]))),'referenceMismatches':sum(a!=b for a,b in zip(v.get('reference',[]),v.get('pixels',[]))),'copyDenied':v.get('copyDenied',False),'direct':{k:{'copyDenied':x.get('copyDenied',False),'rawMismatches':sum(a!=b for a,b in zip(raw,x.get('pixels',[])))}for k,x in v['direct'].items()}}for name,v in result.items()}
   finally:d.quit()
 finally:
  server.shutdown();server.server_close();(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 return int(any(not c['pass']for c in report['checks']))
if __name__=='__main__':raise SystemExit(main())
