"""A deliberately zero legacy seed cannot expose unverified fullmode pixels."""
import json,os,tempfile,threading,time
from pathlib import Path
from http.server import ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_canvas_consistency import Page
SCRIPT=r'''
const done=arguments[arguments.length-1];(async()=>{
 const result={};const c=document.createElement('canvas');c.width=c.height=16;const x=c.getContext('2d');x.fillStyle='#807060';x.fillRect(0,0,16,16);try{result.known=Array.from(x.getImageData(0,0,1,1).data)}catch(e){result.knownError=String(e)}
 const i=new Image();i.src='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><foreignObject width="16" height="16"><div xmlns="http://www.w3.org/1999/xhtml" style="width:16px;height:16px;background:#807060"></div></foreignObject></svg>');await i.decode();x.drawImage(i,0,0);
 try{x.getImageData(0,0,16,16);result.readDenied=false}catch(e){result.readDenied=true;result.readError=e.name}
 try{const url=c.toDataURL();result.encodeDenied=!url||url==='data:,'}catch(e){result.encodeDenied=true;result.encodeError=e.name}
 const gc=document.createElement('canvas');gc.width=gc.height=16;const g=gc.getContext('webgl',{preserveDrawingBuffer:true});result.gl=!!g;if(g){const t=g.createTexture();g.bindTexture(g.TEXTURE_2D,t);g.texImage2D(g.TEXTURE_2D,0,g.RGBA,g.RGBA,g.UNSIGNED_BYTE,c);g.clearColor(.4,.5,.6,1);g.clear(g.COLOR_BUFFER_BIT);while(g.getError()){}const bytes=new Uint8Array(16*16*4);bytes.fill(37);g.readPixels(0,0,16,16,g.RGBA,g.UNSIGNED_BYTE,bytes);result.glReadError=g.getError();result.glReadUntouched=bytes.every(v=>v===37);try{const url=gc.toDataURL();result.glEncodeDenied=!url||url==='data:,'}catch(e){result.glEncodeDenied=true}}
 done(result);
})().catch(e=>done({error:String(e),stack:e.stack}));
'''
def main():
 out=Path(os.environ.get('REPORT_DIR','/tmp/cfx-zero-seed'));out.mkdir(parents=True,exist_ok=True);report={'checks':[]}
 def check(ok,name):report['checks'].append({'pass':bool(ok),'name':name});print(('PASS 'if ok else'FAIL ')+name,flush=True)
 server=ThreadingHTTPServer(('127.0.0.1',0),Page);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with tempfile.TemporaryDirectory(prefix='cfx-zero-seed-')as profile:
   opts=Options();opts.binary_location=os.environ['CLOAKFOX_BIN']
   for a in ['-headless','-purgecaches','-profile',profile]:opts.add_argument(a)
   opts.set_preference('cloakfox.experimental.canvas_pipeline',True)
   d=webdriver.Firefox(options=opts,service=Service(service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
   try:
    d.set_script_timeout(60);d.set_context('chrome');report['runtime']=d.execute_script('return{buildID:Services.appinfo.appBuildID,version:Services.appinfo.version}')
    d.execute_script("Services.prefs.setBoolPref('cloakfox.enabled',true);const k='cloakfox.s.cloak_cfg_0',c=JSON.parse(Services.prefs.getStringPref(k,'{}'));c['canvas:seed']=0;c['fingerprint:secret']='ABEiM0RVZneImaq7zN3u/wARIjNEVWZ3iJmqu8zd7v8=';Services.prefs.setStringPref(k,JSON.stringify(c));");time.sleep(.4)
    d.set_context('content');d.get(f'http://127.0.0.1:{server.server_port}/');r=d.execute_async_script(SCRIPT);report['result']=r;check('error'not in r,'zero-seed corpus completes')
    if'error'not in r:
     check(r.get('known')==[128,112,96,255],'qualified authored fill remains exact with zero legacy seed')
     check(r['readDenied']and r['encodeDenied'],'unverified 2D reads and encoders fail closed')
     check(r['gl'],'canonical GL creates with zero legacy seed')
     if r['gl']:check(r['glReadError']==1282 and r['glReadUntouched']and r['glEncodeDenied'],'unverified GL read refuses before modifying destination and encoder refuses')
   finally:d.quit()
 finally:server.shutdown();server.server_close();(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 return int(any(not c['pass']for c in report['checks']))
if __name__=='__main__':raise SystemExit(main())
