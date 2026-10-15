"""Read-only installed-binary baseline for the complete-renderer proposal.

Records known-color modification and calibrated path-raster recovery. A passing
probe means diagnostics collected, not that privacy acceptance passes. It changes
only a disposable profile, never the installed app or personal settings.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

DRAW = r'''
function sample(kind) {
 const make=()=>kind==='html'?document.createElement('canvas'):new OffscreenCanvas(64,64);
 const c=make();c.width=64;c.height=64;const x=c.getContext('2d',{willReadFrequently:true});
 x.fillStyle='rgb(128,128,128)';x.fillRect(0,0,64,64);
 const known=Array.from(x.getImageData(0,0,64,64).data);
 const delta=known.map((v,i)=>i%4===3?0:v-128);
 const g=x.createLinearGradient(0,0,64,64);g.addColorStop(0,'rgb(30,70,110)');g.addColorStop(1,'rgb(210,170,130)');
 x.fillStyle=g;x.fillRect(0,0,64,64);x.fillStyle='rgb(60,100,140)';x.beginPath();x.ellipse(32,32,18,13,.3,0,2*Math.PI);x.fill();
 const observed=Array.from(x.getImageData(0,0,64,64).data);
 const recovered=observed.map((v,i)=>i%4===3?v:v-delta[i]);
 return {knownModified:known.filter((v,i)=>i%4!==3&&v!==128).length,observed,recovered};
}
'''
SCRIPT = DRAW + r'''
const done=arguments[arguments.length-1];
(async()=>{
 const workerSource='const sample='+sample.toString()+';onmessage=()=>postMessage(sample("offscreen"));';
 const u=URL.createObjectURL(new Blob([workerSource],{type:'text/javascript'}));const w=new Worker(u);
 try {
  const worker=await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('worker timeout')),10000);w.onmessage=e=>{clearTimeout(t);resolve(e.data)};w.onerror=e=>{clearTimeout(t);reject(Error(e.message))};w.postMessage(1)});
  done({html:sample('html'),offscreen:sample('offscreen'),worker});
 }finally{w.terminate();URL.revokeObjectURL(u)}
})().catch(e=>done({error:String(e)}));
'''
class Page(BaseHTTPRequestHandler):
 def do_GET(self):
  b=b'<!doctype html><title>Canvas pipeline baseline</title>';self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def log_message(self,*_):pass

def main():
 out=Path(os.environ.get('REPORT_DIR','/tmp/cloakfox-canvas-pipeline-baseline'));out.mkdir(parents=True,exist_ok=True)
 binary=os.environ.get('CLOAKFOX_BIN','/Applications/Cloakfox.app/Contents/MacOS/cloakfox');measurements={}
 server=ThreadingHTTPServer(('127.0.0.1',0),Page);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with tempfile.TemporaryDirectory(prefix='cfx-pipeline-baseline-') as profile:
   options=Options();options.binary_location=binary
   options.set_preference('cloakfox.experimental.canvas_pipeline',os.environ.get('CLOAKFOX_TEST_CANVAS_PIPELINE','0')=='1')
   for arg in ['-headless','-purgecaches','-profile',profile]:options.add_argument(arg)
   driver=webdriver.Firefox(options=options,service=Service(service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
   try:
    for mode,enabled,render in [('native',False,False),('legacy',True,False),('glyph',True,True)]:
     driver.set_context('chrome');driver.execute_script("Services.prefs.setBoolPref('cloakfox.enabled',arguments[0]);Services.prefs.setBoolPref('cloakfox.opt.canvas_render_privacy',arguments[1]);",enabled,render)
     runtime=driver.execute_script('return {version:Services.appinfo.version,buildID:Services.appinfo.appBuildID}')
     driver.set_context('content');driver.get(f'http://127.0.0.1:{server.server_port}/');driver.set_script_timeout(20)
     measurements[mode]=driver.execute_async_script(SCRIPT);assert 'error' not in measurements[mode],measurements[mode]
   finally:driver.quit()
  summary=[]
  for mode in ['legacy','glyph']:
   for realm,v in measurements[mode].items():
    native=measurements['native'][realm]['observed'];recovered=v['recovered']
    summary.append({'mode':mode,'realm':realm,'knownColorModifiedChannels':v['knownModified'],'nativeRasterRecoveryMismatches':sum(a!=b for a,b in zip(native,recovered)),'sampleChannels':len(native),'nativeRasterRecoveredExactly':native==recovered})
  result={'binary':binary,'runtime':runtime,'xulSHA256':hashlib.sha256(Path(binary).parent.joinpath('XUL').read_bytes()).hexdigest(),'purpose':'diagnostic baseline, not privacy acceptance','canonicalExperiment':os.environ.get('CLOAKFOX_TEST_CANVAS_PIPELINE','0')=='1','measurements':summary}
  (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
 finally:server.shutdown();server.server_close()
if __name__=='__main__':main()
