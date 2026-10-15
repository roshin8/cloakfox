"""Read-only installed-backend feasibility capture, not a profile implementation.

Uses generated BrowserForge data only inside disposable profiles. Records the
existing canonical backend's page-facing tuple under identical-persona owners.
No hardware labels are changed to imply emulation that does not exist.
"""
import hashlib
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
from probe_container_workflows import open_site, chrome
from probe_webgl_backend_profile import INSPECT

HTML = b'''<!doctype html><title>Container profile feasibility</title><style>
#fixed{position:absolute;left:0;top:0;width:100px;height:100px;transform:rotate(45deg)}
#intrinsic{display:inline-block;font:29px sans-serif}</style>
<div id=fixed></div><div id=intrinsic>Distinct owner typography 0123456789</div>'''
READ = INSPECT + r'''
const rect=e=>{const r=e.getBoundingClientRect();return [r.x,r.y,r.width,r.height]};
const gpu=['webgl','webgl2'].map(kind=>{const g=document.createElement('canvas').getContext(kind);const v=inspect(g);if(g)g.getExtension('WEBGL_lose_context')?.loseContext();return v});
const c=document.createElement('canvas');c.width=400;c.height=70;const x=c.getContext('2d');x.font='29px sans-serif';x.fillText('Distinct owner typography 0123456789',5,45);
return {gpu,fixed:rect(document.getElementById('fixed')),intrinsic:rect(document.getElementById('intrinsic')),canvas:c.toDataURL()};'''
GPU = r'''const done=arguments[arguments.length-1];(async()=>{if(!navigator.gpu)return {available:false};const a=await navigator.gpu.requestAdapter();if(!a)return {available:false};const info=a.info;return {available:true,info:[info.vendor,info.architecture,info.description,info.device],limits:Object.fromEntries(Object.keys(Object.getPrototypeOf(a.limits)).filter(k=>typeof a.limits[k]==='number').map(k=>[k,a.limits[k]]))}})().then(done,e=>done({error:String(e)}));'''

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(HTML)
    def log_message(self, *_):
        pass

def main():
    out=Path(os.environ.get('REPORT_DIR','/tmp/cloakfox-container-feasibility'));out.mkdir(parents=True,exist_ok=True)
    binary=os.environ.get('CLOAKFOX_BIN','/Applications/Cloakfox.app/Contents/MacOS/cloakfox')
    report={'binary':binary,'purpose':'feasibility baseline; no product change','cases':[],'checks':[]}
    xul=Path(binary).parent/'XUL';report['xulSHA256']=hashlib.sha256(xul.read_bytes()).hexdigest()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    def check(value,name):
        report['checks'].append({'pass':bool(value),'name':name});print(('PASS ' if value else 'FAIL ')+name,flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix='cfx-profile-feasibility-') as profile:
            options=Options();options.binary_location=binary
            for arg in ['-purgecaches','-profile',profile]:options.add_argument(arg)
            options.set_preference('cloakfox.enabled',True)
            options.set_preference('cloakfox.experimental.canvas_pipeline',True)
            options.set_preference('dom.webgpu.enabled',True)
            driver=webdriver.Firefox(options=options,service=Service('/opt/homebrew/bin/geckodriver',service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
            try:
                report['runtime']=chrome(driver,'return {buildID:Services.appinfo.appBuildID,version:Services.appinfo.version};')
                open_site(driver,f'http://127.0.0.1:{server.server_port}/raw-software-backend',0)
                chrome(driver,"const key='cloakfox.s.cloak_cfg_0',cfg=JSON.parse(Services.prefs.getStringPref(key));for(const name of Object.keys(cfg))if(/^webgl/i.test(name))delete cfg[name];cfg['webGl:backend_profile']=false;cfg['webgl:typed_readback:disabled']=true;Services.prefs.setStringPref(key,JSON.stringify(cfg));")
                driver.set_context('content');driver.refresh()
                report['rawSoftwareBackend']=driver.execute_script(INSPECT+"return ['webgl','webgl2'].map(k=>{const g=document.createElement('canvas').getContext(k),v=inspect(g);if(g)g.getExtension('WEBGL_lose_context')?.loseContext();return v;});")
                check(all(not v.get('missing') and v['below']==0 and v['above']==1281 for v in report['rawSoftwareBackend']),'software backend independently enforces its texture ceiling')
                for os_name,hardware in [('windows','nvidia'),('macos','apple'),('linux','software')]:
                    ids=chrome(driver,"return [cis.create('Profile A','fingerprint','blue').userContextId,cis.create('Profile B','fingerprint','red').userContextId];")
                    # Generate the same BrowserForge persona for both owners.
                    persona=chrome(driver,"const p=ChromeUtils.importESModule('resource:///modules/CloakfoxPersonas.sys.mjs');return p.fillPersonaKeys('B'.repeat(43)+'=',arguments[0],{os:arguments[1],hardware:arguments[2]});",ids[0],os_name,hardware)
                    pair=[]
                    for index,ucid in enumerate(ids):
                        url=f'http://127.0.0.1:{server.server_port}/?owner={ucid}'
                        _,actual=open_site(driver,url,ucid)
                        time.sleep(.3)
                        state=chrome(driver,"const key='cloakfox.s.cloak_cfg_'+arguments[0],prior=JSON.parse(Services.prefs.getStringPref(key)),cfg={...arguments[1]};for(const [name,value]of Object.entries(prior))if(/seed|secret/i.test(name))cfg[name]=value;cfg['navigator:webgpu:disabled']=false;Services.prefs.setStringPref(key,JSON.stringify(cfg));return {renderer:cfg['webGl:renderer'],vendor:cfg['webGl:vendor'],platform:cfg['navigator.platform'],canonical:cfg['canvas:canonical_2d'],profile:cfg['webGl:backend_profile'],canvasSeed:cfg['canvas:seed'],fontSeed:cfg['fonts:spacing_seed']};",ucid,persona)
                        driver.set_context('content');driver.refresh()
                        samples=[]
                        for host in ['127.0.0.1','localhost']:
                            driver.get(f'http://{host}:{server.server_port}/?owner={ucid}')
                            value=driver.execute_script(READ);value['webgpu']=driver.execute_async_script(GPU);samples.append({'host':host,'value':value})
                        row={'os':os_name,'hardware':hardware,'container':ucid,'actualContainer':actual,'requested':state,'samples':samples};report['cases'].append(row);pair.append(row)
                        check(actual==ucid,f'{os_name}/{index}: real owner matches')
                        check(state['canonical'] and state['profile'],f'{os_name}/{index}: existing protected pipeline active')
                        check(all(not x.get('missing') for s in samples for x in s['value']['gpu']),f'{os_name}/{index}: both WebGL contexts operate')
                        check(all(s['value']['webgpu'].get('available') for s in samples),f'{os_name}/{index}: WebGPU enabled and available')
                    a,b=pair
                    report.setdefault('comparisons',[]).append({'os':os_name,'personaRenderer':persona['webGl:renderer'],'identicalSavedPersona':a['requested']['renderer']==b['requested']['renderer'],'distinctOwnerSeeds':a['requested']['canvasSeed']!=b['requested']['canvasSeed'],'sameReportedGPUTuple':[(v['identity'],v['caps'])for v in a['samples'][0]['value']['gpu']]==[(v['identity'],v['caps'])for v in b['samples'][0]['value']['gpu']],'differentIntrinsicGeometry':a['samples'][0]['value']['intrinsic']!=b['samples'][0]['value']['intrinsic'],'differentCanvas':a['samples'][0]['value']['canvas']!=b['samples'][0]['value']['canvas']})
                    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
            finally:driver.quit()
    finally:
        server.shutdown();server.server_close();(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return int(any(not c['pass'] for c in report['checks']))

if __name__=='__main__':raise SystemExit(main())
