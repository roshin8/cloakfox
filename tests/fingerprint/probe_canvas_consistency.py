"""Native canvas crop/export coherence and text-geometry regression.

Requires selenium, Pillow, geckodriver and CLOAKFOX_BIN. Local disposable
profile only. PNGs are decoded outside the browser to avoid a second canvas
privacy transformation during verification. No known-renderer allowlists.
"""
import base64
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

PROBE = r'''
const done=arguments[arguments.length-1];
(async()=>{
async function sampleCanvas(c,kind,opaque) {
 const offscreen=typeof c.convertToBlob==='function';
 c.width=23;c.height=17;const x=c.getContext('2d',{willReadFrequently:true,alpha:!opaque});
 // Nontrivial colours, varying alpha, true antialiased edges and glyphs.
 for(let y=0;y<17;y++)for(let z=0;z<23;z++){
  x.fillStyle=`rgba(${31+(z*29)%220},${21+(y*37)%230},${41+(z*y*13)%210},${[1,.5,.125,.875][(z+y)%4]})`;
  x.fillRect(z,y,1,1);
 }
 x.fillStyle='rgba(73,152,219,.625)';x.beginPath();x.arc(9.4,8.2,6.3,.2,5.8);x.fill();
 x.font='9px sans-serif';x.fillStyle='rgba(231,87,43,.75)';x.fillText('ink',2.3,12.1);
 const whole=Array.from(x.getImageData(0,0,23,17).data);
 const crops=[];
 for(const [sx,sy,w,h] of [[7,5,9,6],[-3,-2,11,8],[19,13,9,7],[3,2,-8,-7]]){
  const pixels=x.getImageData(sx,sy,w,h).data;
  const ox=w<0?sx+w:sx,oy=h<0?sy+h:sy,aw=Math.abs(w),ah=Math.abs(h);
  let mismatches=0;
  for(let y=0;y<ah;y++)for(let z=0;z<aw;z++)for(let ch=0;ch<4;ch++){
   const px=ox+z,py=oy+y;
   const expected=px>=0&&px<23&&py>=0&&py<17?whole[(py*23+px)*4+ch]:0;
   mismatches+=pixels[(y*aw+z)*4+ch]!==expected;
  }
  crops.push({sx,sy,w,h,mismatches});
 }
 const blob=offscreen?await c.convertToBlob():await new Promise(r=>c.toBlob(r));
 const png=btoa(String.fromCharCode(...new Uint8Array(await blob.arrayBuffer())));
 const dataURL=offscreen?null:c.toDataURL().split(',')[1];
 x.textAlign='left';x.textBaseline='alphabetic';
 const names=['width','actualBoundingBoxLeft','actualBoundingBoxRight','actualBoundingBoxAscent','actualBoundingBoxDescent',
 'fontBoundingBoxAscent','fontBoundingBoxDescent','emHeightAscent','emHeightDescent',
 'hangingBaseline','alphabeticBaseline','ideographicBaseline'];
 const metric=s=>{const m=x.measureText(s);return Object.fromEntries(names.map(n=>[n,m[n]]));};
 const empty=metric(''),spaces=metric('   '),ink=metric('arbitrary glyphs');
 x.textAlign='right';const right=metric('arbitrary glyphs');
 x.textAlign='left';const baselines={};
 for(const baseline of ['top','hanging','middle','ideographic','bottom']) {
  x.textBaseline=baseline;baselines[baseline]=metric('arbitrary glyphs');
 }
 x.clearRect(0,0,23,17);const cleared=x.getImageData(0,0,23,17).data.every((v,i)=>v===(opaque&&i%4===3?255:0));
 return {kind,offscreen,opaque,whole,crops,png,dataURL,empty,spaces,ink,right,baselines,cleared};
}
const results=[];
for(const [offscreen,opaque] of [[false,false],[true,false],[false,true],[true,true]]) {
 const c=offscreen?new OffscreenCanvas(23,17):document.createElement('canvas');
 results.push(await sampleCanvas(c,offscreen?'window-offscreen':'window-html',opaque));
}
// Reuse the exact drawing/readback/metric code across realms. A transferred
// canvas is never initialized in the window before worker ownership begins.
const workerSource=`const sampleCanvas=${sampleCanvas.toString()};
self.onmessage=async({data})=>{
 try {postMessage(await sampleCanvas(data.canvas||new OffscreenCanvas(23,17),data.kind,data.opaque));}
 catch(e){postMessage({error:String(e),stack:e.stack});}
};`;
const workerURL=URL.createObjectURL(new Blob([workerSource],{type:'application/javascript'}));
try {
 for(const kind of ['worker-offscreen','worker-transferred'])for(const opaque of [false,true]) {
  const worker=new Worker(workerURL);
  try {
   results.push(await new Promise((resolve,reject)=>{
    const timeout=setTimeout(()=>reject(new Error(kind+' timed out')),15000);
    worker.onmessage=({data})=>{clearTimeout(timeout);data.error?reject(new Error(data.error)):resolve(data);};
    worker.onerror=e=>{clearTimeout(timeout);reject(new Error(e.message));};
    let canvas;
    if(kind==='worker-transferred') {
     const element=document.createElement('canvas');element.width=23;element.height=17;
     canvas=element.transferControlToOffscreen();
    }
    worker.postMessage({kind,opaque,canvas},canvas?[canvas]:[]);
   }));
  } finally {worker.terminate();}
 }
} finally {URL.revokeObjectURL(workerURL);}
done({results});
})().catch(e=>done({error:String(e),stack:e.stack}));
'''


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'<!doctype html><title>Canvas consistency</title>')

    def log_message(self, *_):
        pass


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    results, checks = {}, []

    def check(ok, name):
        checks.append({'pass': bool(ok), 'name': name})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)

    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-canvas-consistency-') as profile:
            options = Options()
            options.binary_location = os.environ['CLOAKFOX_BIN']
            for pref, variable in [
                ('canvas_render_privacy', 'CLOAKFOX_TEST_CANVAS_RENDER_PRIVACY'),
                ('gpu_backend_profiles', 'CLOAKFOX_TEST_GPU_BACKEND_PROFILES'),
            ]:
                options.set_preference('cloakfox.opt.' + pref,
                                       os.environ.get(variable, '0') == '1')
            options.set_preference('cloakfox.experimental.canvas_pipeline',
                                   os.environ.get('CLOAKFOX_TEST_CANVAS_PIPELINE', '0') == '1')
            for argument in ['-headless', '-profile', profile, '-purgecaches']:
                options.add_argument(argument)
            Path(profile, 'user.js').write_text('user_pref("cloakfox.enabled",true);\n')
            driver = webdriver.Firefox(options=options, service=Service(
                service_args=['--allow-system-access'], log_output=profile+'/gecko.log'))
            driver.set_script_timeout(30)
            try:
                base = f'http://127.0.0.1:{server.server_port}/'
                driver.get(base)
                time.sleep(1)
                # Two actual containers; ownership must come from the canvas/global.
                driver.set_context('chrome')
                containers = driver.execute_script('''
const {ContextualIdentityService}=ChromeUtils.importESModule(
 'moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
return [0,1].map(n=>ContextualIdentityService.create('Canvas '+n,'fingerprint','blue').userContextId);
''')
                driver.set_context('content')
                for name, ucid, seed, enabled, other_site in [
                    ('a', containers[0], 111111, True, False),
                    ('repeat', containers[0], 111111, True, False),
                    ('b', containers[1], 999999, True, False),
                    ('other-site', containers[0], 111111, True, True),
                    ('native', containers[0], 111111, False, False),
                ]:
                    before = set(driver.window_handles)
                    driver.set_context('chrome')
                    driver.execute_script('''
Services.prefs.setBoolPref('cloakfox.enabled',arguments[2]);
const key='cloakfox.s.cloak_cfg_'+arguments[0];
const cfg=JSON.parse(Services.prefs.getStringPref(key,'{}'));
cfg['canvas:seed']=arguments[1];Services.prefs.setStringPref(key,JSON.stringify(cfg));
const win=Services.wm.getMostRecentWindow('navigator:browser');
const tab=win.gBrowser.addTab('about:blank',{userContextId:arguments[0],
 triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
win.gBrowser.selectedTab=tab;
''', ucid, seed, enabled)
                    driver.set_context('content')
                    driver.switch_to.window((set(driver.window_handles)-before).pop())
                    driver.get(base.replace('127.0.0.1', 'localhost') if other_site else base)
                    time.sleep(.75)
                    results[name] = driver.execute_async_script(PROBE)
            finally:
                driver.quit()
        for name, result in results.items():
            check('error' not in result, name+': probe completed')
            for entry in result.get('results', []):
                label = name+': '+entry['kind']+(' opaque' if entry['opaque'] else '')
                check(all(c['mismatches']==0 for c in entry['crops']), label+': absolute and clipped crops agree')
                for field in ['png', 'dataURL']:
                    if name != 'native' and entry[field] is not None:
                        image = Image.open(io.BytesIO(base64.b64decode(entry[field]))).convert('RGBA')
                        check(list(image.tobytes()) == entry['whole'], label+': decoded '+field+' equals readback')
                check(entry['cleared'], label+': clear remains exact')
                check(all(entry['empty'][k]==0 for k in ['actualBoundingBoxLeft','actualBoundingBoxRight',
                    'actualBoundingBoxAscent','actualBoundingBoxDescent']),label+': empty retains zero ink bounds')
                check(entry['spaces']['actualBoundingBoxAscent']==0 and entry['spaces']['actualBoundingBoxDescent']==0
                    and entry['spaces']['actualBoundingBoxLeft']+entry['spaces']['actualBoundingBoxRight']==0,
                    label+': whitespace retains zero ink extent')
                check(entry['empty']['width']==0 and entry['spaces']['width']>0,label+': empty and whitespace advances')
                check(abs(entry['right']['actualBoundingBoxLeft']-entry['ink']['actualBoundingBoxLeft']-
                    entry['ink']['width']) < 1e-5,label+': alignment and advance agree')
                for baseline, metric in entry['baselines'].items():
                    # The font ascent delta independently describes the native
                    # baseline translation. Glyph ink must follow that shift.
                    shift=entry['ink']['fontBoundingBoxAscent']-metric['fontBoundingBoxAscent']
                    check(abs(metric['actualBoundingBoxAscent']+shift-entry['ink']['actualBoundingBoxAscent'])<1e-8
                        and abs(metric['actualBoundingBoxDescent']-shift-entry['ink']['actualBoundingBoxDescent'])<1e-8
                        and metric['width']==entry['ink']['width'],label+': '+baseline+' keeps native baseline translation')
            for entry in result.get('results', []):
                if not entry['kind'].startswith('worker-'):
                    continue
                window=next(e for e in result['results'] if e['kind']=='window-offscreen' and e['opaque']==entry['opaque'])
                label=name+': '+entry['kind']+(' opaque' if entry['opaque'] else '')
                check(entry['whole']==window['whole'],label+': readback matches window owner')
                if name != 'native':
                    worker_png=Image.open(io.BytesIO(base64.b64decode(entry['png']))).convert('RGBA').tobytes()
                    window_png=Image.open(io.BytesIO(base64.b64decode(window['png']))).convert('RGBA').tobytes()
                    check(worker_png==window_png,label+': decoded PNG matches window owner')
                check(entry['ink']==window['ink'] and entry['baselines']==window['baselines'],
                    label+': metric geometry matches window owner')
        if all('error' not in r for r in results.values()):
            a=results['a']['results']
            for i, entry in enumerate(a):
                label=entry['kind']+(' opaque' if entry['opaque'] else '')
                check(a[i]['whole']==results['repeat']['results'][i]['whole'],label+': repeat deterministic')
                canonical=os.environ.get('CLOAKFOX_TEST_CANVAS_PIPELINE','0')=='1'
                for name in ['b','other-site','native']:
                    equal=a[i]['whole']==results[name]['results'][i]['whole']
                    # Per-owner font scaling can quantize to equal or unequal pixels.
                    if not canonical or name == 'native':
                        check(not equal,label+': protected pixels differ from '+name)
                check(a[i]['ink']==results['repeat']['results'][i]['ink'],label+': metric repeat deterministic')
                check(a[i]['ink']!=results['b']['results'][i]['ink'],label+': metric privacy isolated')
                if canonical:
                    check(a[i]['ink']!=results['other-site']['results'][i]['ink'],label+': metric site isolation')
        report=Path(os.environ.get('CANVAS_CONSISTENCY_REPORT','/tmp/cloakfox-canvas-consistency.json'))
        report.write_text(json.dumps({'binary':str(Path(os.environ['CLOAKFOX_BIN']).resolve()),'checks':checks,'results':results},indent=2))
        print(report)
        return 0 if all(c['pass'] for c in checks) else 1
    finally:
        server.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
