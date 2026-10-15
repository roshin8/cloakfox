"""Actual bitmaprenderer encoders must not release unqualified native pixels."""
import base64,hashlib,io,json,os,tempfile,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from PIL import Image
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_canvas_consistency import Page
SETUP="""window.source=document.createElement('canvas');source.width=128;source.height=64;const alpha=arguments[0],opaque=arguments[1];window.sx=source.getContext('2d',{alpha:!opaque});sx.fillStyle=`rgba(128,128,128,${alpha})`;sx.fillRect(0,0,128,64);sx.font='19px serif';sx.fillStyle=`rgba(0,0,0,${alpha})`;sx.fillText('Native glyph Ω AV',3,36);return Array.from(sx.getImageData(0,0,128,64).data);"""
EXPORT=r'''const done=arguments[arguments.length-1];(async()=>{
 const bytes=async b=>{if(!b)return null;const a=new Uint8Array(await b.arrayBuffer());let s='';for(const v of a)s+=String.fromCharCode(v);return btoa(s)};
 const result={expected:Array.from(sx.getImageData(0,0,128,64).data),exports:[]};
 for(const type of ['image/png','image/jpeg','image/webp']){
  const c=document.createElement('canvas');c.width=128;c.height=64;c.getContext('bitmaprenderer').transferFromImageBitmap(await createImageBitmap(source));
  result.exports.push({route:'toDataURL',type,bytes:c.toDataURL(type,.83).split(',')[1]});
  result.exports.push({route:'toBlob',type,bytes:await bytes(await new Promise(r=>c.toBlob(r,type,.83)))});
  const o=new OffscreenCanvas(128,64);o.getContext('bitmaprenderer').transferFromImageBitmap(await createImageBitmap(source));
  result.exports.push({route:'convertToBlob',type,bytes:await bytes(await o.convertToBlob({type,quality:.83}))});
 }
 const worker=new Worker(URL.createObjectURL(new Blob([`onmessage=async e=>{try{const c=new OffscreenCanvas(128,64);c.getContext('bitmaprenderer').transferFromImageBitmap(e.data);const b=await c.convertToBlob({type:'image/png'});const a=new Uint8Array(await b.arrayBuffer());let s='';for(const v of a)s+=String.fromCharCode(v);postMessage({route:'worker/convertToBlob',type:'image/png',bytes:btoa(s)})}catch(e){postMessage({error:String(e)})}}`],{type:'text/javascript'})));
 try{const b=await createImageBitmap(source);result.exports.push(await new Promise((r,j)=>{worker.onmessage=e=>r(e.data);worker.onerror=e=>j(Error(e.message));worker.postMessage(b,[b])}))}finally{worker.terminate()}
 return result;
})().then(done,e=>done({error:String(e),stack:e.stack}));'''
def main():
 out=Path(os.environ.get('REPORT_DIR','/tmp/cfx-bitmap-export'));out.mkdir(parents=True,exist_ok=True)
 report={'binary':os.environ['CLOAKFOX_BIN'],'checks':[],'cases':[]}
 def check(ok,name):report['checks'].append({'pass':bool(ok),'name':name});print(('PASS 'if ok else'FAIL ')+name,flush=True)
 server=ThreadingHTTPServer(('127.0.0.1',0),Page);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with tempfile.TemporaryDirectory(prefix='cfx-bitmap-export-')as profile:
   o=Options();o.binary_location=report['binary']
   for arg in ['-headless','-profile',profile,'-purgecaches']:o.add_argument(arg)
   o.set_preference('privacy.resistFingerprinting',False)
   d=webdriver.Firefox(options=o,service=Service('/opt/homebrew/bin/geckodriver',service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
   def chrome(s,*a):d.set_context('chrome');v=d.execute_script(s,*a);d.set_context('content');return v
   try:
    d.set_script_timeout(45);report['runtime']=chrome('return {buildID:Services.appinfo.appBuildID,version:Services.appinfo.version};')
    for mode,label,alpha,opaque in [(m,n,a,o)for m in [False,True]for n,a,o in [('opaque',1,False),('low-alpha',.05,False),('transparent',0,False),('opaque-x8',.3,True)]]:
     chrome("Services.prefs.setBoolPref('cloakfox.enabled',false);Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',false);")
     d.get(f'http://127.0.0.1:{server.server_port}/');native=bytes(d.execute_script(SETUP,alpha,opaque))
     chrome("Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',arguments[0]);Services.prefs.setBoolPref('cloakfox.enabled',true);",mode)
     result=d.execute_async_script(EXPORT);assert 'error'not in result,result
     expected=bytes(result['expected']);check(expected!=native if alpha else expected==native and not any(native),f'mode{mode}/{label}: legacy readback protection or empty-transparent invariants')
     formats={}
     for entry in result['exports']:
      routeLabel=f'mode{mode}/{label}/'+entry.get('route','worker')+'/'+entry.get('type','')
      check('error'not in entry and bool(entry.get('bytes')),routeLabel+' export succeeds')
      if not entry.get('bytes'):continue
      pixels=Image.open(io.BytesIO(base64.b64decode(entry['bytes']))).convert('RGBA').tobytes()
      if entry['type']=='image/png':check(pixels==expected and (pixels!=native or not alpha),routeLabel+' matches protected typed readback, not native pixels')
      reference=formats.setdefault(entry['type'],pixels);check(pixels==reference,routeLabel+' same-format routes agree')
     repeat=d.execute_async_script(EXPORT);check(repeat==result,f'mode{mode}/{label}: repeated serialization stays deterministic')
     report['cases'].append({'canonical':mode,'nativeSHA256':hashlib.sha256(native).hexdigest(),'protectedSHA256':hashlib.sha256(expected).hexdigest()})
    chrome("const k='cloakfox.s.cloak_cfg_0',c=JSON.parse(Services.prefs.getStringPref(k));c['canvas:seed']=0;Services.prefs.setStringPref(k,JSON.stringify(c));")
    zero=d.execute_async_script(r"""const done=arguments[arguments.length-1];(async()=>{const rows=[];const c=document.createElement('canvas');c.width=128;c.height=64;c.getContext('bitmaprenderer').transferFromImageBitmap(await createImageBitmap(source));try{rows.push({route:'toDataURL',uri:c.toDataURL()})}catch(e){rows.push({route:'toDataURL',refused:e.name})}try{const b=await new Promise(r=>c.toBlob(r));rows.push({route:'toBlob',uri:b?await new Promise(r=>{const f=new FileReader;f.onload=()=>r(f.result);f.readAsDataURL(b)}):null})}catch(e){rows.push({route:'toBlob',refused:e.name})}try{const o=new OffscreenCanvas(128,64);o.getContext('bitmaprenderer').transferFromImageBitmap(await createImageBitmap(source));const b=await o.convertToBlob();rows.push({route:'convertToBlob',uri:await new Promise(r=>{const f=new FileReader;f.onload=()=>r(f.result);f.readAsDataURL(b)})})}catch(e){rows.push({route:'convertToBlob',refused:e.name})}return rows})().then(done,e=>done({error:String(e)}));""")
    assert isinstance(zero,list),zero
    for row in zero:
     uri=row.get('uri');blank=False
     if uri and uri!='data:,':
      pixels=Image.open(io.BytesIO(base64.b64decode(uri.split(',')[1]))).convert('RGBA').tobytes();blank=not any(pixels)
     check(row.get('refused')or not uri or uri=='data:,'or blank,row['route']+': canonical unknown input with zero seed never releases source pixels')
    # A verified fresh canonical source remains exact, including low alpha.
    chrome("const k='cloakfox.s.cloak_cfg_0',c=JSON.parse(Services.prefs.getStringPref(k));c['canvas:seed']=42;Services.prefs.setStringPref(k,JSON.stringify(c));")
    canonical=bytes(d.execute_script(SETUP,.05,False));qualified=d.execute_async_script(EXPORT);assert 'error'not in qualified,qualified
    for row in qualified['exports']:
     if row.get('type')!='image/png':continue
     pixels=Image.open(io.BytesIO(base64.b64decode(row['bytes']))).convert('RGBA').tobytes()
     check(pixels==canonical,row['route']+': verified same-owner canonical pixels remain exact without double noise')
    # Retained canonical pixels cannot borrow a recipient's new owner proof.
    chrome("const k='cloakfox.s.cloak_cfg_0',c=JSON.parse(Services.prefs.getStringPref(k));c['canvas:seed']=43;Services.prefs.setStringPref(k,JSON.stringify(c));")
    foreignExpected=bytes(d.execute_script("const c=document.createElement('canvas');c.width=128;c.height=64;const x=c.getContext('2d');x.drawImage(source,0,0);return Array.from(x.getImageData(0,0,128,64).data);"))
    foreign=d.execute_async_script(EXPORT);assert 'error'not in foreign,foreign
    for row in foreign['exports']:
     if row.get('type')!='image/png':continue
     pixels=Image.open(io.BytesIO(base64.b64decode(row['bytes']))).convert('RGBA').tobytes()
     check(pixels==foreignExpected and pixels!=canonical,row['route']+': foreign-owner canonical bitmap receives recipient protection')
   finally:d.quit()
 finally:server.shutdown();(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 return int(any(not c['pass']for c in report['checks']))
if __name__=='__main__':raise SystemExit(main())
