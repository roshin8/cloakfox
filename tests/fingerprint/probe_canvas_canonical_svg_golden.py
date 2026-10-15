"""Mac-only SVG producer regression with pinned author bytes and owner identities.

Goldens are raw straight RGBA SHA256 from the pre-geometry installed build.
SVG and Canvas use different text-positioning APIs; their equality is diagnostic.
Same-SVG URL variants and pixel transfers must remain exactly equal.
"""
import base64
import hashlib
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from http.server import ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_canvas_consistency import Page

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fingerprint/fixtures/canonical-svg-bidi-macos.json'
SCRIPT = r'''const encoded=arguments[0],done=arguments[arguments.length-1];
(async()=>{
 const face=await new FontFace('FixedAuthor',Uint8Array.from(atob(encoded),c=>c.charCodeAt(0))).load();document.fonts.add(face);
 const text='abc שלום 123 سلام',W=400,H=100;
 const source=`<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100"><style>@font-face{font-family:FixedAuthor;src:url(data:font/ttf;base64,${encoded})}</style><text x="5" y="65" font-family="FixedAuthor" font-size="32" fill="#303030">${text}</text></svg>`;
 const hash=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
 const canvas=()=>{const c=document.createElement('canvas');c.width=W;c.height=H;return c;};
 const pixels=c=>c.getContext('2d').getImageData(0,0,W,H).data;
 const reference=canvas(),x=reference.getContext('2d');x.font='32px FixedAuthor';x.fillStyle='#303030';x.fillText(text,5,65);
 const expected=pixels(reference),result={canvasSHA256:await hash(expected),canvasWidth:x.measureText(text).width,sources:{}};
 const blob=new Blob([source],{type:'image/svg+xml'});
 for(const kind of ['data','blob']){
  const url=kind==='data'?'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(source):URL.createObjectURL(blob);
  try{
   const image=new Image();await new Promise((r,j)=>{image.onload=r;image.onerror=j;image.src=url;});await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame);
   const c=canvas();c.getContext('2d').drawImage(image,0,0);const actual=pixels(c),entry={pixelSHA256:await hash(actual),canvasEqual:actual.every((v,i)=>v===expected[i]),ink:actual.filter((v,i)=>i%4===3&&v>128).length};
   const bitmap=await createImageBitmap(image),off=new OffscreenCanvas(W,H);off.getContext('2d').drawImage(bitmap,0,0);entry.offscreenSHA256=await hash(pixels(off));
   const worker=new Worker(URL.createObjectURL(new Blob([`onmessage=e=>{try{const c=new OffscreenCanvas(400,100);c.getContext('2d').drawImage(e.data,0,0);e.data.close();postMessage(c.getContext('2d').getImageData(0,0,400,100).data);}catch(error){postMessage({error:String(error)})}};`],{type:'text/javascript'})));
   const transferred=await new Promise((r,j)=>{worker.onmessage=e=>r(e.data);worker.onerror=j;worker.postMessage(bitmap,[bitmap]);});worker.terminate();
   if(transferred.error)throw Error(transferred.error);entry.workerSHA256=await hash(transferred);result.sources[kind]=entry;
  }finally{if(kind==='blob')URL.revokeObjectURL(url);}
 }
 return result;
})().then(done,e=>done({error:String(e),stack:e.stack}));'''


def collect(binary, out):
    out.mkdir(parents=True, exist_ok=True)
    font = ROOT / 'bundle/fonts/macos/DejaVuSans.ttf'
    report = {'scope': 'Mac-only installed SVG producer regression',
              'fontSHA256': hashlib.sha256(font.read_bytes()).hexdigest(), 'cases': []}
    server = ThreadingHTTPServer(('127.0.0.1', 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='cfx-svg-golden-') as profile:
            opts = Options()
            opts.binary_location = binary
            for arg in ['-headless', '-purgecaches', '-profile', profile]:
                opts.add_argument(arg)
            opts.set_preference('cloakfox.experimental.canvas_pipeline', True)
            opts.set_preference('cloakfox.opt.canvas_render_privacy', False)
            Path(profile, 'user.js').write_text('user_pref("cloakfox.enabled",true);\n')
            driver = webdriver.Firefox(options=opts, service=Service(
                service_args=['--allow-system-access'], log_output=str(out / 'gecko.log')))
            try:
                driver.set_script_timeout(90)
                driver.set_context('chrome')
                report['runtime'] = driver.execute_script("return {buildID:Services.appinfo.appBuildID,full:Services.prefs.getBoolPref('cloakfox.experimental.canvas_pipeline'),master:Services.prefs.getBoolPref('cloakfox.enabled')}")
                driver.set_context('content')
                driver.get(f'http://127.0.0.1:{server.server_port}/')
                time.sleep(.7)
                for seed in [0, 42, 123456789]:
                    driver.set_context('chrome')
                    identity = driver.execute_script("""const key='cloakfox.s.cloak_cfg_0',cfg=JSON.parse(Services.prefs.getStringPref(key,'{}'));cfg['fonts:spacing_seed']=arguments[0];cfg['canvas:seed']=1234567;cfg['fingerprint:secret']='Z'.repeat(43)+'=';Services.prefs.setStringPref(key,JSON.stringify(cfg));return {userContextId:0,partitionSite:'http://127.0.0.1','fonts:spacing_seed':cfg['fonts:spacing_seed'],'canvas:seed':cfg['canvas:seed'],'fingerprint:secret':cfg['fingerprint:secret']};""", seed)
                    driver.set_context('content')
                    driver.get(f'http://127.0.0.1:{server.server_port}/?seed={seed}')
                    result = driver.execute_async_script(SCRIPT, base64.b64encode(font.read_bytes()).decode())
                    report['cases'].append({'identity': identity, 'result': result})
            finally:
                driver.quit()
    finally:
        server.shutdown()
    (out / 'observations.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    out = Path(os.environ.get('REPORT_DIR', '/tmp/cfx-svg-golden'))
    report = collect(os.environ['CLOAKFOX_BIN'], out)
    fixture = json.loads(FIXTURE.read_text())
    checks = []

    def check(ok, label):
        checks.append({'pass': bool(ok), 'name': label})
        print(('PASS ' if ok else 'FAIL ') + label, flush=True)

    check(report['fontSHA256'] == fixture['fontSHA256'], 'pinned explicit author font bytes')
    check(report['runtime']['full'] and report['runtime']['master'], 'native full renderer and master active')
    for case in report['cases']:
        seed = str(case['identity']['fonts:spacing_seed'])
        result = case['result']
        check('error' not in result, seed + ' SVG producer completes')
        if 'error' in result:
            continue
        expected = fixture['seeds'][seed]
        check(case['identity'] == expected['identity'], seed + ' exact owning identity')
        data, blob = result['sources']['data'], result['sources']['blob']
        check(data['pixelSHA256'] == blob['pixelSHA256'], seed + ' same SVG data/blob pixels exact')
        for kind, value in result['sources'].items():
            check(value['pixelSHA256'] == expected['pixelSHA256'], seed + ' ' + kind + ' SVG raw RGBA golden exact')
            check(value['offscreenSHA256'] == value['pixelSHA256'], seed + ' ' + kind + ' OffscreenCanvas exact')
            check(value['workerSHA256'] == value['pixelSHA256'], seed + ' ' + kind + ' transferred worker exact')
    report['checks'] = checks
    report['fixture'] = str(FIXTURE)
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0 if all(c['pass'] for c in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
