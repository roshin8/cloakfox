"""Local AudioWorklet regression, disposable profiles and no media grants.

CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox python ...
REPORT_DIR retains JSON and geckodriver logs. Reload/recreate worklet nodes after
policy changes: native engines intentionally retain their construction snapshot.
"""
from __future__ import annotations
import json
import os
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait

PROCESSOR = r"""
class Capture extends AudioWorkletProcessor {
 static get parameterDescriptors() { return [{name:'control', defaultValue:.25},{name:'capture',defaultValue:0},{name:'ramp',defaultValue:-.5}]; }
 constructor(options) { super(); this.kind=options.processorOptions.kind; this.samples=[]; this.constants=[]; this.ramp=[]; }
 process(inputs, outputs, parameters) {
  const input=this.kind==='parameter'?[parameters.capture]:inputs[0];
  if (!input.length) return true;
  // Channel zero in the constant graph is deliberate exact silence.
  // Hash the nonzero .25 channel while retaining every channel for bounds.
  this.samples.push(...input[this.kind==='constant'?1:0]);
  this.ramp.push(...parameters.ramp);
  if (!this.constants.length) this.constants.push(...input.map(c=>Array.from(c)));
  for(let c=0;c<input.length;c++) outputs[0][c].set(input[c]);
  if(this.samples.length>=44160) {
   this.port.postMessage({samples:this.samples, constants:this.constants,
     control:Array.from(parameters.control),ramp:this.ramp});
   return false;
  }
  return true;
 }
}
registerProcessor('capture',Capture);
"""
PAGE = r"""<!doctype html><meta charset=utf-8><script>
async function capture(kind) {
 const c=new OfflineAudioContext(kind==='constant'?6:1,44160,44100);
 await c.audioWorklet.addModule('/processor.js');
 const node=new AudioWorkletNode(c,'capture',{outputChannelCount:[kind==='constant'?6:1],processorOptions:{kind}});
 node.parameters.get('ramp').setValueAtTime(-.5,0);
 node.parameters.get('ramp').linearRampToValueAtTime(.5,1);
 const result=new Promise((resolve,reject)=>{
  node.port.onmessage=e=>resolve(e.data);
  node.onprocessorerror=()=>reject(new Error('processor error'));
 });
 if(kind==='constant') {
  const merger=c.createChannelMerger(6);
  [0,.25,-1,1e30,1e-40,3e38].forEach((value,index)=>{
   const s=c.createConstantSource();s.offset.value=value;s.connect(merger,0,index);s.start();
  });merger.connect(node);
 } else {
  const s=c.createOscillator();s.type='triangle';s.frequency.value=10000;
  const compressor=c.createDynamicsCompressor();s.connect(compressor);compressor.connect(kind==='parameter'?node.parameters.get('capture'):node);s.start();
 }
 node.connect(c.destination);
 const buffer=await c.startRendering();
 const raw=await result;
 async function hash(values) {
  const bytes=new Float32Array(values);
  const digest=await crypto.subtle.digest('SHA-256',bytes.buffer);
  return Array.from(new Uint8Array(digest),v=>v.toString(16).padStart(2,'0')).join('');
 }
 return {hash:await hash(raw.samples), bufferHash:await hash(buffer.getChannelData(0)),
  constants:raw.constants,control:raw.control,rampHash:await hash(raw.ramp), finite:raw.samples.every(Number.isFinite)};
}
window.run=async()=>({oscillator:await capture('oscillator'),constant:await capture('constant'),parameter:await capture('parameter')});
</script>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        script=self.path=='/processor.js'
        body=(PROCESSOR if script else PAGE).encode()
        self.send_response(200)
        self.send_header('Content-Type','text/javascript' if script else 'text/html')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def log_message(self,*args):
        pass


def main():
    report=Path(os.environ.get('REPORT_DIR',tempfile.mkdtemp(prefix='cfx-worklet-report-')))
    report.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    results={}
    try:
        for mode in ('protected','off','exception'):
            with tempfile.TemporaryDirectory(prefix='cfx-worklet-profile-') as temp:
                opts=Options()
                opts.binary_location=os.environ['CLOAKFOX_BIN']
                opts.add_argument('--headless'); opts.add_argument('-profile'); opts.add_argument(temp)
                opts.set_preference('cloakfox.enabled',mode!='off')
                opts.set_preference('privacy.userContext.enabled',True)
                with webdriver.Firefox(options=opts,service=Service(service_args=['--allow-system-access'],log_output=str(report/f'{mode}-geckodriver.log'))) as driver:
                    driver.set_script_timeout(40)
                    # Set complete exact-container overlays after startup persona creation.
                    driver.set_context('chrome')
                    driver.execute_script(r"""
                      const mode=arguments[0];
                      for(const ucid of [1,2]) {
                       const key='cloakfox.s.cloak_cfg_'+ucid;
                       let cfg=JSON.parse(Services.prefs.getStringPref(key,'{}'));
                       Object.assign(cfg,{'audio:seed':1000+ucid,'fingerprint:secret':(ucid===1?'a':'b').repeat(43)+'=',
                         fonts:['Arial'],'fonts:spacing_seed':1000+ucid});
                       cfg['privacy:policy']={version:1,preset:'standard',exceptions:mode==='exception'?
                         ['http://127.0.0.1','http://localhost'].map(site=>({site,expiresAt:Date.now()+3600000,vectors:['audio']})):[]};
                       Services.prefs.setStringPref(key,JSON.stringify(cfg));
                      }
                    """,mode)
                    driver.set_context('content')
                    def sample(host,ucid):
                        before=set(driver.window_handles)
                        driver.set_context('chrome')
                        driver.execute_script("""
                         const tab=gBrowser.addTab(arguments[0],{userContextId:arguments[1],
                          triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
                         gBrowser.selectedTab=tab;
                        """,f'http://{host}:{server.server_port}/',ucid)
                        driver.set_context('content')
                        deadline=time.monotonic()+15
                        while not (set(driver.window_handles)-before):
                            assert time.monotonic()<deadline,'container tab missing'
                            time.sleep(.05)
                        driver.switch_to.window((set(driver.window_handles)-before).pop())
                        def read():
                            WebDriverWait(driver,15).until(lambda d:d.execute_script("return typeof window.run === 'function'"))
                            return driver.execute_async_script("const cb=arguments[0];run().then(cb,e=>cb({error:String(e)}));")
                        first=read(); second=read(); driver.refresh(); reload=read()
                        assert 'error' not in first,first
                        assert first==second==reload,'same graph/container/site/reload must be stable'
                        driver.close(); driver.switch_to.window(next(iter(before)))
                        return first
                    results[mode]={name:sample(host,ucid) for name,host,ucid in (
                        ('a','127.0.0.1',1),('b','127.0.0.1',2),('site','localhost',1))}
                    (report/'results.json').write_text(json.dumps(results,indent=2))
        failures=[]
        def check(condition,message):
            if not condition: failures.append(message)
        for mode,records in results.items():
            for name,record in records.items():
                for value in record.values():
                    check(value['finite'],f'{mode}/{name}: nonfinite samples')
                    check(all(v==.25 for v in value['control']),f'{mode}/{name}: intrinsic constant changed')
                    check(value['rampHash']==results['off']['a']['oscillator']['rampHash'],f'{mode}/{name}: intrinsic automation changed')
                constants=record['constant']['constants']
                check(all(v==0 for v in constants[0]),f'{mode}/{name}: silence changed')
                for index,samples in enumerate(constants[1:],1):
                    # Gecko flushes subnormal source samples before the worklet;
                    # compare to its native graph output rather than inventing
                    # stronger subnormal guarantees than the audio engine has.
                    expected=results['off']['a']['constant']['constants'][index][0]
                    check(all(v==0 if expected==0 else
                              v*expected>0 and abs(v)<=abs(expected) and
                              abs(v-expected)<=abs(expected)*1.1e-6 for v in samples),
                          f'{mode}/{name}: sample bounds changed on channel {index}')
        check(results['protected']['a']['oscillator']['bufferHash']!=results['protected']['b']['oscillator']['bufferHash'],
              'harness: AudioBuffer control does not prove active container policy')
        for key in ('oscillator','constant','parameter'):
            p=results['protected']
            check(p['a'][key]['hash']!=p['b'][key]['hash'],f'{key}: cross-container raw hash identical')
            check(p['a'][key]['hash']!=p['site'][key]['hash'],f'{key}: cross-site raw hash identical')
            native=results['off']['a'][key]['hash']
            check(p['a'][key]['hash']!=native,f'{key}: protected raw hash identical to native')
            check(all(v[key]['hash']==native for v in results['off'].values()),f'{key}: master-off did not restore native')
            check(all(v[key]['hash']==native for v in results['exception'].values()),f'{key}: policy exception did not restore native')
        (report/'summary.json').write_text(json.dumps({'failures':failures,'report':str(report)},indent=2))
        assert not failures,'; '.join(failures)
        print(f'PASS AudioWorklet privacy: {report}')
    finally:
        server.shutdown();server.server_close()

if __name__=='__main__':
    main()
