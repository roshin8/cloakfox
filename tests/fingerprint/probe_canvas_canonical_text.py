"""Installed-runtime fixed-outline text checks; not full renderer acceptance."""
import json, os, tempfile, threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_canvas_consistency import Page
SCRIPT=r'''const done=arguments[arguments.length-1];
async function sample(c){
 c.width=240;c.height=100;const x=c.getContext('2d');x.font='40px sans-serif';
 const gradient=x.createLinearGradient(0,0,200,0);gradient.addColorStop(0,'red');gradient.addColorStop(1,'blue');
 x.fillStyle=gradient;x.fillText('A',150,60);const data=x.getImageData(0,0,240,100).data;
 let red=0,blue=0,n=0;for(let i=0;i<data.length;i+=4)if(data[i+3]>240){red+=data[i];blue+=data[i+2];n++;}
 const width=x.measureText('A').width,av=x.measureText('AV').width,empty=x.measureText('').width;
 const before=Array.from(data);x.font='40px serif';x.fillText('fallback Ω שלום 😀',0,95);
 return {width,av,empty,n,red,blue,bytes:before,fallback:x.measureText('fallback Ω שלום 😀').width};
}
(async()=>{
 const html=await sample(document.createElement('canvas'));
 const offscreen=await sample(new OffscreenCanvas(1,1));
 const worker=new Worker(URL.createObjectURL(new Blob([`const sample=${sample};onmessage=async()=>postMessage(await sample(new OffscreenCanvas(1,1)));`],{type:'text/javascript'})));
 const remote=await new Promise((r,j)=>{worker.onmessage=e=>r(e.data);worker.onerror=e=>j(Error(e.message));worker.postMessage(0)});worker.terminate();
 done({html,offscreen,worker:remote});
})().catch(e=>done({error:String(e),stack:e.stack}));'''
def main():
 out=Path(os.environ.get('REPORT_DIR','/tmp/cfx-canonical-text'));out.mkdir(parents=True,exist_ok=True)
 server=ThreadingHTTPServer(('127.0.0.1',0),Page);threading.Thread(target=server.serve_forever,daemon=True).start()
 checks=[];report={'checks':checks}
 def check(ok,name):checks.append({'pass':bool(ok),'name':name});print(('PASS ' if ok else 'FAIL ')+name,flush=True)
 try:
  with tempfile.TemporaryDirectory(prefix='cfx-canonical-text-') as profile:
   opts=Options();opts.binary_location=os.environ['CLOAKFOX_BIN']
   for arg in ['-headless','-purgecaches','-profile',profile]:opts.add_argument(arg)
   opts.set_preference('cloakfox.experimental.canvas_pipeline',True)
   opts.set_preference('cloakfox.opt.canvas_render_privacy',False)
   Path(profile,'user.js').write_text('user_pref("cloakfox.enabled",true);\n')
   d=webdriver.Firefox(options=opts,service=Service(service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
   try:
    d.set_script_timeout(30);d.set_context('chrome');report['runtime']=d.execute_script('return {buildID:Services.appinfo.appBuildID,version:Services.appinfo.version}')
    d.set_context('content');d.get(f'http://127.0.0.1:{server.server_port}/');results=d.execute_async_script(SCRIPT);report['results']=results
    check('error' not in results,'text sample completes')
    if 'error' not in results:
     for kind,v in results.items():
      check(v['n']>0 and v['blue']>3*v['red'],kind+' gradient remains in author coordinates')
      check(abs(v['width']-27.36328125)<.01,kind+' packaged DejaVu outline advance is used')
      check(v['av']<2*v['width'],kind+' kerning retained')
      check(v['empty']==0,kind+' empty text width remains zero')
      check(v['fallback']>0,kind+' unsupported script remains usable')
     check(results['html']['bytes']==results['offscreen']['bytes']==results['worker']['bytes'],'same canonical text pixels across realms')
    report['results']={k:{a:b for a,b in v.items() if a!='bytes'} for k,v in results.items()} if 'error' not in results else results
   finally:d.quit()
 finally:
  server.shutdown();server.server_close();(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 return int(any(not c['pass'] for c in checks))
if __name__=='__main__':raise SystemExit(main())
