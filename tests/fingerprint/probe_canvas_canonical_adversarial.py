"""Mac-only adversarial corpus; distinguishes authored pixels from host glyphs.

Uses a disposable profile. Retains all extraction guards while testing whether a
known-fill calibration recovers native system-font output. No detector-specific
branches and no claim about an untested host/architecture.
"""
import hashlib,json,os,tempfile,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_canvas_consistency import Page
SCRIPT=r'''
const done=arguments[arguments.length-1];
function sample(make){
 const c=make();c.width=256;c.height=96;const x=c.getContext('2d');
 x.fillStyle='rgb(128,128,128)';x.fillRect(0,0,256,96);
 const calibration=Array.from(x.getImageData(0,0,256,96).data).map((v,i)=>i%4===3?0:v-128);
 x.font='32px "Helvetica Neue",Arial,sans-serif';x.fillStyle='rgb(40,70,100)';
 x.fillText('AV fi Ω مرحبا 😀',6,50);
 const observed=Array.from(x.getImageData(0,0,256,96).data);
 const corrected=observed.map((v,i)=>v-calibration[i]);
 const repeat=Array.from(x.getImageData(0,0,256,96).data);
 return{observed,corrected,repeat,width:x.measureText('AV fi Ω مرحبا 😀').width};
}
(async()=>{
 const html=sample(()=>document.createElement('canvas'));
 const offscreen=sample(()=>new OffscreenCanvas(1,1));
 const url=URL.createObjectURL(new Blob(['const sample='+sample+';onmessage=()=>postMessage(sample(()=>new OffscreenCanvas(1,1)));'],{type:'text/javascript'}));const w=new Worker(url);
 try{const worker=await new Promise((r,j)=>{const t=setTimeout(()=>j(Error('worker timeout')),30000);w.onmessage=e=>{clearTimeout(t);r(e.data)};w.onerror=e=>j(Error(e.message));w.postMessage(1)});done({html,offscreen,worker})}
 finally{w.terminate();URL.revokeObjectURL(url)}
})().catch(e=>done({error:String(e),stack:e.stack}));
'''
def main():
 out=Path(os.environ.get('REPORT_DIR','/tmp/cfx-canonical-attacks'));out.mkdir(parents=True,exist_ok=True)
 binary=os.environ['CLOAKFOX_BIN'];report={'binary':binary,'checks':[],'scope':'installed macOS only; no cross-host assertion'}
 def check(ok,name):report['checks'].append({'pass':bool(ok),'name':name});print(('PASS 'if ok else'FAIL ')+name,flush=True)
 server=ThreadingHTTPServer(('127.0.0.1',0),Page);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with tempfile.TemporaryDirectory(prefix='cfx-canonical-attacks-')as profile:
   opts=Options();opts.binary_location=binary
   for arg in ['-headless','-purgecaches','-profile',profile]:opts.add_argument(arg)
   opts.set_preference('cloakfox.opt.canvas_render_privacy',False)
   d=webdriver.Firefox(options=opts,service=Service(service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
   try:
    d.set_script_timeout(90);samples={}
    for mode,master,pipeline in [('native',False,False),('legacy',True,False),('canonical',True,True),('canonical-repeat',True,True)]:
     d.set_context('chrome');d.execute_script("Services.prefs.setBoolPref('cloakfox.enabled',arguments[0]);Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',arguments[1]);",master,pipeline)
     report['runtime']=d.execute_script('return {buildID:Services.appinfo.appBuildID,version:Services.appinfo.version}')
     d.set_context('content');d.get(f'http://127.0.0.1:{server.server_port}/');samples[mode]=d.execute_async_script(SCRIPT);check('error'not in samples[mode],mode+' corpus completes')
    if all('error'not in v for v in samples.values()):
     for realm in ['html','offscreen','worker']:
      native=samples['native'][realm]['observed'];current=samples['canonical'][realm]
      mismatch=sum(a!=b for a,b in zip(native,current['corrected']))
      check(mismatch>100,realm+' known-fill inversion does not recover native glyph raster')
      check(current['observed']==current['repeat'],realm+' repeated reads stable')
      check(current==samples['canonical-repeat'][realm],realm+' canonical reload stable')
      report.setdefault('recovery',{})[realm]={'nativeGlyphMismatches':mismatch,'channels':len(native),'canonicalSHA256':hashlib.sha256(bytes(current['observed'])).hexdigest()}
     check(samples['canonical']['html']==samples['canonical']['offscreen']==samples['canonical']['worker'],'canonical font corpus agrees across realms')
    report['errors']={k:v for k,v in samples.items()if'error'in v}
   finally:d.quit()
 finally:
  server.shutdown();server.server_close();(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 return int(any(not c['pass']for c in report['checks']))
if __name__=='__main__':raise SystemExit(main())
