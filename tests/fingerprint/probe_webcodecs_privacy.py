"""Own-global WebCodecs hardware preference normalization and real encode checks.

Uses disposable profiles and a loopback page. No camera or microphone access.
"""
import json,os,tempfile,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from selenium.webdriver.support.ui import WebDriverWait
from probe_daily_defaults import launch

PROBE=r'''const done=arguments[arguments.length-1];(async()=>{
const result={encoders:[],decoders:[]};
for(const codec of ['av01.0.08M.08','vp09.00.10.08','avc1.42001e','vp8']){
 for(const hardwareAcceleration of ['no-preference','prefer-hardware','prefer-software']){
  const config={codec,width:64,height:64,hardwareAcceleration};
  try{const s=await VideoEncoder.isConfigSupported(config);result.encoders.push({codec,hardwareAcceleration,supported:s.supported})}catch(e){result.encoders.push({codec,hardwareAcceleration,error:e.name})}
  try{const s=await VideoDecoder.isConfigSupported({codec,hardwareAcceleration});result.decoders.push({codec,hardwareAcceleration,supported:s.supported})}catch(e){result.decoders.push({codec,hardwareAcceleration,error:e.name})}
 }
}
try{await VideoEncoder.isConfigSupported({codec:'vp8',width:0,height:64});result.invalid='resolved'}catch(e){result.invalid=e.name}
try{result.unsupported=(await VideoEncoder.isConfigSupported({codec:'not-a-real-codec',width:64,height:64})).supported}catch(e){result.unsupported=e.name}
result.encode=[];
for(const hardwareAcceleration of ['no-preference','prefer-hardware','prefer-software']){
 const config={codec:'vp8',width:64,height:64,hardwareAcceleration};
 if(!(await VideoEncoder.isConfigSupported(config)).supported){result.encode.push({hardwareAcceleration,unsupported:true});continue}
 let count=0,error=null;const enc=new VideoEncoder({output(){count++},error(e){error=e.name}});
 const canvas=new OffscreenCanvas(64,64);canvas.getContext('2d').fillRect(0,0,64,64);
 const frame=new VideoFrame(canvas,{timestamp:0});
 try{enc.configure(config);enc.encode(frame,{keyFrame:true});await enc.flush();result.encode.push({hardwareAcceleration,count,error})}catch(e){result.encode.push({hardwareAcceleration,error:e.name})}finally{frame.close();if(enc.state!=='closed')enc.close()}
}
done(result)})().catch(e=>done({error:e.name,message:e.message}));'''
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  b=b'<!doctype html><meta charset=utf-8><title>WebCodecs privacy fixture</title>';self.send_response(200);self.end_headers();self.wfile.write(b)
 def log_message(self,*args):pass

def main():
 out=Path(os.environ.get('REPORT_DIR',Path(__file__).parent/'reports/158-fingerprint-repairs/webcodecs'));out.mkdir(parents=True,exist_ok=True)
 server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();rows=[];failures=[]
 try:
  with tempfile.TemporaryDirectory(prefix='cfx-webcodecs-') as t:
   profile=Path(t)/'profile';profile.mkdir();d=launch(profile,out/'gecko.log');d.set_script_timeout(90)
   def config(id,spoof):
    d.set_context('chrome');d.execute_script("const k='cloakfox.s.cloak_cfg_'+arguments[0];const c=JSON.parse(Services.prefs.getStringPref(k,'{}'));c['mediaCapabilities:spoof']=arguments[1];Services.prefs.setStringPref(k,JSON.stringify(c));",id,spoof);d.set_context('content')
   def check(ok,label):
    print(('PASS ' if ok else 'FAIL ')+label,flush=True)
    if not ok:failures.append(label)
   try:
    d.set_context('chrome');other=d.execute_script("return ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService.create('Native codecs','fingerprint','blue').userContextId");d.set_context('content');config(0,True);config(other,False)
    for mode,id,spoof in [('protected',0,True),('other-native',other,False),('optout',0,False),('master-off',0,True)]:
     config(id,spoof)
     before=set(d.window_handles)
     d.set_context('chrome');d.execute_script("Services.prefs.setBoolPref('cloakfox.enabled',arguments[0]);const w=Services.wm.getMostRecentWindow('navigator:browser');w.gBrowser.selectedTab=w.gBrowser.addTab('about:blank',{userContextId:arguments[1],triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});",mode!='master-off',id);d.set_context('content')
     handle=WebDriverWait(d,10).until(lambda d:next(iter(set(d.window_handles)-before),False));d.switch_to.window(handle)
     url=f'http://127.0.0.1:{server.server_port}/?mode={mode}';d.get(url)
     # Chrome-created tabs can still expose their initial about:blank global
     # after get() returns. A callback injected there is lost on navigation,
     # producing None instead of a WebCodecs result. Wait for the exact owning
     # document, not just readyState (about:blank is already complete).
     WebDriverWait(d,15).until(lambda d:d.execute_script("return location.href===arguments[0] && document.readyState==='complete'",url))
     for kind in ['window','worker']:
      if kind=='window':r=d.execute_async_script(PROBE)
      else:r=d.execute_async_script("const done=arguments[arguments.length-1];const code=arguments[0].replace('const done=arguments[arguments.length-1];','const done=x=>postMessage(x);');const u=URL.createObjectURL(new Blob([code],{type:'text/javascript'}));const w=new Worker(u);w.onmessage=e=>{w.terminate();URL.revokeObjectURL(u);done(e.data)};w.onerror=e=>{w.terminate();URL.revokeObjectURL(u);done({error:e.message})};",PROBE)
      if not isinstance(r,dict):r={'error':'HarnessResultError','message':'Expected object from exact-document probe','value':r}
      rows.append({'mode':mode,'kind':kind,'result':r});(out/'results.json').write_text(json.dumps(rows,indent=2));check('error' not in r,mode+'/'+kind+' API available')
      if 'error' in r:continue
      check(r['invalid']=='TypeError',mode+'/'+kind+' invalid dimensions reject');check(r['unsupported'] is False,mode+'/'+kind+' unsupported codec stays unsupported')
      if mode=='protected':
       for key in ['encoders','decoders']:
        for codec in ['av01.0.08M.08','vp09.00.10.08','avc1.42001e','vp8']:
         values=[x.get('supported',x.get('error')) for x in r[key] if x['codec']==codec];check(len(set(values))==1,kind+'/'+key+'/'+codec+' preference-independent support')
       check(all(x.get('count',0)>0 and not x.get('error') for x in r['encode']),kind+' actual VP8 encode works for every normalized preference')
    for kind in ['window','worker']:
     native=next(x['result'] for x in rows if x['mode']=='master-off' and x['kind']==kind)
     for mode in ['other-native','optout']:
      value=next(x['result'] for x in rows if x['mode']==mode and x['kind']==kind);check(value.get('encoders')==native.get('encoders'),mode+'/'+kind+' retains native capability choices')
   finally:d.quit()
 finally:server.shutdown();server.server_close()
 (out/'summary.json').write_text(json.dumps({'failures':failures,'cases':len(rows)},indent=2));assert not failures,failures
if __name__=='__main__':main()
