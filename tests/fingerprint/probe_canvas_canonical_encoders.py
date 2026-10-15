"""Actual PNG/JPEG/WebP exports across HTML, OffscreenCanvas and workers."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import ThreadingHTTPServer
from PIL import Image
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_canvas_consistency import Page

SAMPLE = r'''
async function sample(kind){
 const c=kind==='html'?document.createElement('canvas'):new OffscreenCanvas(128,80);c.width=128;c.height=80;
 const x=c.getContext('2d');x.fillStyle='rgba(40,110,180,.5)';x.fillRect(0,0,128,80);
 x.fillStyle='#d6813f';x.beginPath();x.ellipse(60,30,38,22,.3,0,6.28);x.fill();
 x.font='16px sans-serif';x.fillStyle='#19325b';x.fillText('AV Ω مرحبا 😀',4,65);
 const raw=Array.from(x.getImageData(0,0,128,80).data),exports=[];
 for(const type of ['image/png','image/jpeg','image/webp']){
  const blob=kind==='html'?await new Promise(r=>c.toBlob(r,type,.83)):await c.convertToBlob({type,quality:.83});
  const bytes=new Uint8Array(await blob.arrayBuffer());let text='';for(const v of bytes)text+=String.fromCharCode(v);
  exports.push({type,actualType:blob.type,route:kind==='html'?'toBlob':'convertToBlob',bytes:btoa(text)});
  if(kind==='html'){const uri=c.toDataURL(type,.83);exports.push({type,actualType:uri.slice(5,uri.indexOf(';')),route:'toDataURL',bytes:uri.slice(uri.indexOf(',')+1)})}
 }
 return{raw,exports};
}
'''
SCRIPT = SAMPLE + r'''
const done=arguments[arguments.length-1];
(async()=>{
 const result={html:await sample('html'),offscreen:await sample('offscreen')};
 const url=URL.createObjectURL(new Blob([sample.toString()+';onmessage=()=>sample("offscreen").then(value=>postMessage(value)).catch(e=>postMessage({error:String(e)}))'],{type:'text/javascript'}));
 const worker=new Worker(url);
 try{result.worker=await new Promise((resolve,reject)=>{worker.onmessage=e=>resolve(e.data);worker.onerror=e=>reject(Error(e.message));worker.postMessage(1)})}finally{worker.terminate();URL.revokeObjectURL(url)}
 done(result);
})().catch(e=>done({error:String(e)}));
'''


def main():
    out = Path(os.environ.get('REPORT_DIR', '/tmp/cloakfox-encoders'))
    out.mkdir(parents=True, exist_ok=True)
    binary = Path(os.environ['CLOAKFOX_BIN']).resolve()
    report = {'binary': str(binary), 'xulSHA256': hashlib.sha256(binary.with_name('XUL').read_bytes()).hexdigest(), 'checks': [], 'exports': []}
    def check(value, name):
        report['checks'].append({'name': name, 'pass': bool(value)})
        print(('PASS ' if value else 'FAIL ') + name, flush=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-encoders-') as profile:
            options = Options()
            options.binary_location = str(binary)
            for arg in ['-headless', '-purgecaches', '-profile', profile]:
                options.add_argument(arg)
            options.set_preference('cloakfox.experimental.canvas_pipeline', True)
            driver = webdriver.Firefox(options=options, service=Service(service_args=['--allow-system-access'], log_output=str(out / 'gecko.log')))
            try:
                driver.set_script_timeout(45)
                driver.set_context('chrome')
                report['runtime'] = driver.execute_script('return {buildID:Services.appinfo.appBuildID,version:Services.appinfo.version}')
                driver.set_context('content')
                driver.get(f'http://127.0.0.1:{server.server_port}/')
                results = driver.execute_async_script(SCRIPT)
                assert 'error' not in results, results
                reference = bytes(results['html']['raw'])
                reference_formats = {}
                for realm, result in results.items():
                    assert 'error' not in result, result
                    check(bytes(result['raw']) == reference, realm + ': source backing agrees')
                    for entry in result['exports']:
                        label = realm + '/' + entry['route'] + '/' + entry['type']
                        encoded = base64.b64decode(entry['bytes'])
                        image = Image.open(io.BytesIO(encoded)).convert('RGBA')
                        pixels = image.tobytes()
                        check(entry['actualType'] == entry['type'] and image.size == (128, 80), label + ': requested format and dimensions')
                        if entry['type'] == 'image/png':
                            check(pixels == reference, label + ': PNG agrees with typed readback')
                        previous = reference_formats.setdefault(entry['type'], pixels)
                        check(pixels == previous, label + ': decoded pixels agree across export routes')
                        report['exports'].append({'realm': realm, 'route': entry['route'], 'type': entry['type'],
                                                  'encodedSHA256': hashlib.sha256(encoded).hexdigest(), 'pixelsSHA256': hashlib.sha256(pixels).hexdigest()})
            finally:
                driver.quit()
    finally:
        server.shutdown()
        (out / 'result.json').write_text(json.dumps(report, indent=2))
    return int(any(not check['pass'] for check in report['checks']))


if __name__ == '__main__':
    raise SystemExit(main())
