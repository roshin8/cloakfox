"""Experimental glyph-mode behavior in a disposable Selenium profile.

Uses real pixels in HTML, Offscreen, worker-created and transferred contexts.
Legacy extraction remains enabled, so this does not assert backing/read identity.
Run the separate probe_canvas_consistency.py in both modes for PNG/crop equality.
"""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_canvas_consistency import Page

PROBE = r'''
const done=arguments[arguments.length-1];
(async()=>{
function sample(c,shapeOnly=false) {
 c.width=240;c.height=100;
 const x=c.getContext('2d',{willReadFrequently:true});
 x.fillStyle='#87a2bc';x.fillRect(0,0,240,100);
 if(!shapeOnly){
  x.save(); x.beginPath(); x.rect(3,3,232,94);x.clip();
  x.setTransform(1,.03,.02,1,1.25,1.5);x.font='21px serif';
  x.fillStyle='#142856';x.fillText('Arbitrary ink Ω',4.3,29.7);
  x.direction='rtl';x.strokeStyle='#8129ab';x.lineWidth=.7;
  x.strokeText('مرحبا שלום',220.4,59.2,135);
  x.direction='ltr';x.fillText('Color 😀',14.2,87.3,120);
  const stateBefore=Array.from(x.getTransform().toFloat64Array());
  x.fillText('bounded',130,85,31);
  const stateAfter=Array.from(x.getTransform().toFloat64Array());
  if(!stateBefore.every((v,i)=>Math.abs(v-stateAfter[i])<1e-6))throw Error('text changed author transform');
  x.restore();
 }
 const transform=x.getTransform();
 const state=[transform.a,transform.b,transform.c,transform.d,transform.e,transform.f];
 if(!state.every((v,i)=>Math.abs(v-[1,0,0,1,0,0][i])<1e-6))throw Error('restore lost transform');
 const bytes=x.getImageData(0,0,240,100).data;
 let hash=2166136261;for(const b of bytes)hash=Math.imul(hash^b,16777619)>>>0;
 const again=x.getImageData(0,0,240,100).data;
 if(!bytes.every((b,i)=>b===again[i]))throw Error('repeated read changed');
 const metrics=x.measureText('Arbitrary ink Ω');
 return {hash:hash.toString(16),metrics:[metrics.width,metrics.actualBoundingBoxLeft,metrics.actualBoundingBoxRight]};
}
const results={};
for(const [kind,c] of [['html',document.createElement('canvas')],['offscreen',new OffscreenCanvas(1,1)]]) {
 results[kind]=sample(c);results[kind+'-shape']=sample(c,true);
}
// Persist same context across policy edits and bitmap resize/reset.
window.renderPrivacyHeld??=document.createElement('canvas');
results.held=sample(window.renderPrivacyHeld);
// Create an unused HTML and Offscreen context while the current policy is on.
// Only their first drawing occurs after the policy changes in the same realm.
for(const [key,c] of [['renderPrivacyUnusedHTML',document.createElement('canvas')],
                     ['renderPrivacyUnusedOffscreen',new OffscreenCanvas(1,1)]]) {
 if(window[key])results[key]=sample(window[key]);
 else {window[key]=c;c.getContext('2d');}
}
const code=`const sample=${sample.toString()};onmessage=({data})=>{try{postMessage(sample(data||new OffscreenCanvas(1,1)))}catch(e){postMessage({error:String(e)})}}`;
const url=URL.createObjectURL(new Blob([code],{type:'application/javascript'}));
try{
 for(const kind of ['worker','transferred']){
  const w=new Worker(url);
  try{results[kind]=await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error(kind+' timeout')),15000);
   w.onmessage=({data})=>{clearTimeout(timer);data.error?reject(Error(data.error)):resolve(data)};
   w.onerror=e=>{clearTimeout(timer);reject(Error(e.message))};
   const c=kind==='transferred'?document.createElement('canvas').transferControlToOffscreen():null;
   w.postMessage(c,c?[c]:[]);
  });}finally{w.terminate()}
 }
}finally{URL.revokeObjectURL(url)}
done({results});
})().catch(e=>done({error:String(e),stack:e.stack}));
'''


def main():
    checks=[]
    results={}
    def check(ok,name):
        checks.append({'pass':bool(ok),'name':name})
        print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),Page)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-render-privacy-') as profile:
            options=Options();options.binary_location=os.environ['CLOAKFOX_BIN']
            options.set_preference('cloakfox.experimental.canvas_pipeline',os.environ.get('CLOAKFOX_TEST_CANVAS_PIPELINE','0')=='1')
            for arg in ['-headless','-profile',profile,'-purgecaches']:options.add_argument(arg)
            Path(profile,'user.js').write_text('user_pref("cloakfox.enabled",true);\n')
            driver=webdriver.Firefox(options=options,service=Service(service_args=['--allow-system-access'],log_output=profile+'/gecko.log'))
            driver.set_script_timeout(30)
            try:
                base=f'http://127.0.0.1:{server.server_port}/'
                driver.get(base);time.sleep(1)
                # Policy set directly after each central pref update, also
                # exercising wrong-type policy defensively at the native layer.
                for name,policy,master,reload in [
                    ('off',False,True,True),('on',True,True,True),
                    ('on-repeat',True,True,True),('held-off',False,True,False),
                    ('wrong-type','true',True,True),
                    ('native-off',False,False,True),('native-on',True,False,True)]:
                    driver.set_context('chrome')
                    driver.execute_script('''
Services.prefs.setBoolPref('cloakfox.enabled',arguments[1]);
Services.prefs.setBoolPref('cloakfox.opt.canvas_render_privacy',arguments[0]===true);
const key='cloakfox.s.cloak_cfg_0';const cfg=JSON.parse(Services.prefs.getStringPref(key,'{}'));
cfg['canvas:render_privacy']=arguments[0];Services.prefs.setStringPref(key,JSON.stringify(cfg));
''',policy,master)
                    driver.set_context('content')
                    if reload:driver.get(base)
                    time.sleep(.3)
                    results[name]=driver.execute_async_script(PROBE)
            finally:driver.quit()
        for name,result in results.items():check('error' not in result,name+': probe completed')
        if all('results' in r for r in results.values()):
            for kind in ['html','offscreen','worker','transferred']:
                entry=lambda name:results[name]['results'][kind]
                check(entry('off')['hash']!=entry('on')['hash'],kind+': rendering opt-in changes glyph pixels')
                check(entry('on')==entry('on-repeat'),kind+': deterministic across reload')
                check(entry('off')==entry('wrong-type'),kind+': wrong type selects legacy')
                check(entry('off')==entry('held-off'),kind+': new context follows changed policy')
                check(entry('native-off')==entry('native-on'),kind+': master-off native rendering')
                check(entry('off')['metrics']==entry('on')['metrics'],kind+': metric privacy unchanged')
                check(entry('off')==results['off']['results']['html'],kind+': first legacy draw matches owning identity across realms')
                check(entry('on')==results['on']['results']['html'],kind+': same owning identity across realms')
            for kind in ['html-shape','offscreen-shape']:
                check(results['off']['results'][kind]==results['on']['results'][kind],kind+': non-text legacy behavior unchanged')
            check(results['held-off']['results']['held']==results['on-repeat']['results']['held'],'existing context retains opt-in through bitmap reset')
            for kind in ['renderPrivacyUnusedHTML','renderPrivacyUnusedOffscreen']:
                check(results['held-off']['results'][kind]==results['on-repeat']['results']['html'],kind+': unused context retains creation policy after toggle and bitmap reset')
        report=Path(os.environ.get('CANVAS_RENDER_REPORT','/tmp/cloakfox-canvas-render-privacy.json'))
        report.write_text(json.dumps({'binary':str(Path(os.environ['CLOAKFOX_BIN']).resolve()),'checks':checks,'results':results},indent=2));print(report)
        return 0 if all(c['pass'] for c in checks) else 1
    finally:server.shutdown()


if __name__=='__main__':raise SystemExit(main())
