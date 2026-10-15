"""Authored raw VideoFrame bytes remain exact; rendering has one fixed color path."""
import json,os,tempfile,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_canvas_consistency import Page
SCRIPT=r'''
const done=arguments[arguments.length-1];
async function sample(){
 const cases=[['srgb','RGBA',Uint8Array.from(Array(4).fill([40,110,180,255]).flat()),{primaries:'bt709',transfer:'iec61966-2-1',matrix:'rgb',fullRange:true}],['pq','RGBA',Uint8Array.from(Array(4).fill([40,110,180,255]).flat()),{primaries:'bt2020',transfer:'pq',matrix:'rgb',fullRange:true}],['alpha','RGBA',Uint8Array.from(Array(4).fill([40,110,180,128]).flat()),{primaries:'bt709',transfer:'iec61966-2-1',matrix:'rgb',fullRange:true}],['pqAlpha','RGBA',Uint8Array.from(Array(4).fill([40,110,180,128]).flat()),{primaries:'bt2020',transfer:'pq',matrix:'rgb',fullRange:true}],['yuv','I420',new Uint8Array([128,128,128,128,128,128]),{primaries:'bt709',transfer:'bt709',matrix:'bt709',fullRange:false}]];
 const out={};for(const[name,format,bytes,colorSpace]of cases){const frame=new VideoFrame(bytes,{format,codedWidth:2,codedHeight:2,timestamp:0,colorSpace});try{
  const copy=new Uint8Array(frame.allocationSize());await frame.copyTo(copy);
  function draw(input){const c=new OffscreenCanvas(2,2),x=c.getContext('2d');x.drawImage(input,0,0);return Array.from(x.getImageData(0,0,2,2).data)}
  const rendered=draw(frame),options={format:'BGRA',colorSpace:'srgb'},converted=new Uint8Array(frame.allocationSize(options));
  const layouts=await frame.copyTo(converted,options),straight=[];
  for(let y=0;y<2;y++)for(let x=0;x<2;x++){const i=layouts[0].offset+y*layouts[0].stride+x*4;straight.push(converted[i+2],converted[i+1],converted[i],converted[i+3])}
  const bitmap=await createImageBitmap(frame);try{out[name]={original:Array.from(bytes),copy:Array.from(copy),rendered,straight,bitmap:draw(bitmap),colorSpace:frame.colorSpace.toJSON()}}finally{bitmap.close()}
 }finally{frame.close()}}return out;
}
(async()=>{const main=await sample();const url=URL.createObjectURL(new Blob(['const sample='+sample+';onmessage=async()=>{try{postMessage(await sample())}catch(e){postMessage({error:String(e),stack:e.stack})}}'],{type:'text/javascript'})),w=new Worker(url);try{const worker=await new Promise((r,j)=>{const t=setTimeout(()=>j(Error('worker timeout')),20000);w.onmessage=e=>{clearTimeout(t);r(e.data)};w.onerror=e=>j(Error(e.message));w.postMessage(1)});done({main,worker})}finally{w.terminate();URL.revokeObjectURL(url)}})().catch(e=>done({error:String(e),stack:e.stack}));
'''
def main():
 out=Path(os.environ.get('REPORT_DIR','/tmp/cfx-raw-video'));out.mkdir(parents=True,exist_ok=True);report={'checks':[]}
 def check(ok,name):report['checks'].append({'pass':bool(ok),'name':name});print(('PASS 'if ok else'FAIL ')+name,flush=True)
 server=ThreadingHTTPServer(('127.0.0.1',0),Page);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with tempfile.TemporaryDirectory(prefix='cfx-raw-video-')as profile:
   opts=Options();opts.binary_location=os.environ['CLOAKFOX_BIN']
   for arg in ['-headless','-purgecaches','-profile',profile]:opts.add_argument(arg)
   opts.set_preference('cloakfox.experimental.canvas_pipeline',True)
   d=webdriver.Firefox(options=opts,service=Service(service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
   try:
    d.set_script_timeout(60);d.set_context('chrome');report['runtime']=d.execute_script('return{buildID:Services.appinfo.appBuildID,version:Services.appinfo.version}')
    d.set_context('content');d.get(f'http://127.0.0.1:{server.server_port}/');result=d.execute_async_script(SCRIPT);check('error'not in result,'raw video corpus completes')
    if'error'not in result:
     for realm,values in result.items():
      check('error'not in values,realm+' completes')
      if'error'in values:continue
      for name,v in values.items():
       check(v['copy']==v['original'],realm+' '+name+' copyTo retains original authored planes')
       check(v['rendered']==v['bitmap'],realm+' '+name+' bitmap/render color paths agree')
       expected_alpha=128 if name in ('alpha','pqAlpha') else 255
       check(all(x==expected_alpha for x in v['rendered'][3::4]),realm+' '+name+' render alpha retained')
       check(all(x==expected_alpha for x in v['straight'][3::4]),realm+' '+name+' explicit converted alpha retained')
       check(all(abs(a-b)<=1 for a,b in zip(v['straight'],v['rendered'])),realm+' '+name+' explicit RGB conversion returns straight components')
      check(values['srgb']['rendered']==values['srgb']['original'],realm+' sRGB opaque author colors remain exact')
      check(values['pq']['rendered']!=values['pq']['original'],realm+' HDR authored colors converted for sRGB rendering')
     check(result['main']==result['worker'],'window and worker raw video paths agree')
    report['result']=result
   finally:d.quit()
 finally:
  server.shutdown();server.server_close();(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 return int(any(not c['pass']for c in report['checks']))
if __name__=='__main__':raise SystemExit(main())
