"""Disposable-profile DOM rectangle semantic/privacy regression.

Run against installed Cloakfox via CLOAKFOX_BIN. Native-off controls are
collected in the same process. --diagnose records failures without asserting.
"""
import hashlib
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from probe_daily_defaults import launch
from probe_container_workflows import open_site
from selenium.webdriver.support.ui import WebDriverWait

HTML = b'''<!doctype html><style>
body {margin:0} #known,#ghost {position:absolute;left:0;top:0;visibility:hidden}
#known {width:100px;height:100px;transform:rotate(45deg)}
#ghost {width:0;height:0} #wrap {position:absolute;left:40px;top:180px;width:130px}
#text {font:19px serif} #auto {display:inline-block;font:23px serif}
</style><div id=known></div><div id=ghost></div>
<div id=wrap><span id=text>Geometry wraps across several lines of text here.</span></div>
<div id=auto>Intrinsic font dimensions</div>'''
READ = r'''
const rect = r => Object.fromEntries(['x','y','width','height','left','top','right','bottom'].map(k=>[k,r[k]]));
const result={};
for(const id of ['known','ghost','text','auto']) {
 const e=document.getElementById(id), range=document.createRange();range.selectNodeContents(e);
 result[id]={element:{bound:rect(e.getBoundingClientRect()),list:[...e.getClientRects()].map(rect)},
 range:{bound:rect(range.getBoundingClientRect()),list:[...range.getClientRects()].map(rect)},
 offsets:[e.offsetLeft,e.offsetTop,e.offsetWidth,e.offsetHeight]};
}
const caret=document.createRange();caret.setStart(document.getElementById('text').firstChild,3);caret.collapse(true);
result.text.caret={bound:rect(caret.getBoundingClientRect()),list:[...caret.getClientRects()].map(rect)};
return result;
'''

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(HTML)
    def log_message(self,*args): pass

def violations(sample):
    failures=[]
    if sample['text']['caret']['bound']['width'] != 0: failures.append('collapsed caret has nonzero width')
    if any(sample['ghost']['element']['bound'].values()): failures.append('empty border box has nonzero geometry')
    if any(sample['ghost']['offsets']): failures.append('empty border box has nonzero offsets')
    for name, shapes in sample.items():
        for api in ['element','range']+(['caret'] if 'caret' in shapes else []):
            bound, entries = shapes[api]['bound'], shapes[api]['list']
            if any(abs((r['right']-r['left'])-r['width'])>1e-8 or abs((r['bottom']-r['top'])-r['height'])>1e-8 for r in [bound]+entries): failures.append(f'{name}/{api}: rectangle arithmetic differs')
            if any(r['width']<0 or r['height']<0 for r in [bound]+entries): failures.append(f'{name}/{api}: negative dimensions')
            nonempty=[r for r in entries if r['width'] and r['height']]
            if nonempty:
                expected=[min(r['left'] for r in nonempty),min(r['top'] for r in nonempty),max(r['right'] for r in nonempty),max(r['bottom'] for r in nonempty)]
                if any(abs(a-b)>1e-8 for a,b in zip(expected,[bound[k] for k in ['left','top','right','bottom']])): failures.append(f'{name}/{api}: bounding rectangle differs from client union')
    return failures

def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    report={}; failures=[]
    xul=Path(os.environ['CLOAKFOX_BIN']).parent / 'XUL'
    if not xul.exists(): xul=Path(os.environ['CLOAKFOX_BIN']).parents[1] / 'Resources' / 'XUL'
    with xul.open('rb') as source: xul_hash=hashlib.file_digest(source,'sha256').hexdigest()
    report['binary']={'path':os.environ['CLOAKFOX_BIN'], 'xulSHA256':xul_hash}
    with tempfile.TemporaryDirectory(prefix='cloakfox-dom-geometry-') as temp:
        profile=Path(temp)/'profile';profile.mkdir()
        d=launch(profile,Path(temp)/'gecko.log')
        report['binary']['buildID']=d.execute_script('return Services.appinfo.appBuildID')
        pipeline = os.environ.get('CLOAKFOX_TEST_CANVAS_PIPELINE', '0') == '1'
        d.execute_script("Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',arguments[0])",pipeline)
        report['canonicalPipeline'] = pipeline
        def configure(enabled,seed=12345):
            d.set_context('chrome')
            d.execute_script("Services.prefs.setBoolPref('dom.security.https_only_mode',false);Services.prefs.setBoolPref('cloakfox.enabled',arguments[0]);Services.prefs.setStringPref('cloakfox.s.cloak_cfg_0',JSON.stringify({'canvas:seed':arguments[1],'fingerprint:secret':'A'.repeat(43)+'='}));",enabled,seed)
            d.set_context('content')
        try:
            url=f'http://127.0.0.1:{server.server_port}/'
            configure(False);d.get(url);report['native']=d.execute_script(READ)
            configure(True);d.refresh();report['protected']=d.execute_script(READ)
            d.refresh();report['reload']=d.execute_script(READ)
            configure(True,54321);d.refresh();report['otherIdentity']=d.execute_script(READ)
            configure(True);d.get(url.replace('127.0.0.1','localhost'));report['otherSite']=d.execute_script(READ)
            d.get(url);report['siteReturn']=d.execute_script(READ)
            d.set_context('chrome')
            ids=d.execute_script('''const {ContextualIdentityService:C}=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');return [C.create('Geometry A','fingerprint','blue').userContextId,C.create('Geometry B','fingerprint','red').userContextId];''')
            for index, ucid in enumerate(ids):
                d.execute_script("const pref='cloakfox.s.cloak_cfg_'+arguments[0],cfg=JSON.parse(Services.prefs.getStringPref(pref,'{}'));cfg['canvas:seed']=arguments[1];cfg['fingerprint:secret']='A'.repeat(43)+'=';Services.prefs.setStringPref(pref,JSON.stringify(cfg));",ucid,12345+index*11111)
                open_site(d,url,ucid)
                WebDriverWait(d,15).until(lambda driver: driver.execute_script('return !!document.getElementById("known")'))
                # Reapply after container initialization has populated its persona.
                d.set_context('chrome')
                d.execute_script("const pref='cloakfox.s.cloak_cfg_'+arguments[0],cfg=JSON.parse(Services.prefs.getStringPref(pref,'{}'));cfg['canvas:seed']=arguments[1];cfg['fingerprint:secret']='A'.repeat(43)+'=';Services.prefs.setStringPref(pref,JSON.stringify(cfg));",ucid,12345+index*11111)
                d.set_context('content');d.refresh()
                report['container'+str(index)]=d.execute_script(READ)
                d.refresh();report['container'+str(index)+'Reload']=d.execute_script(READ)
                d.set_context('chrome')
                report['container'+str(index)+'Owner']=d.execute_script('''const win=Services.wm.getMostRecentWindow('navigator:browser');return {ucid:win.gBrowser.selectedBrowser.browsingContext.originAttributes.userContextId,cfg:JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+arguments[0],'{}'))['canvas:seed']};''',ucid)
            d.set_context('content')
            failures+=violations(report['protected'])
            report['authorGeometryChanged']=report['protected']['known']['element']['list']!=report['native']['known']['element']['list']
            failures += ['native control: '+failure for failure in violations(report['native'])]
            if report['protected']!=report['reload']: failures.append('reload changed geometry')
            if report['protected']!=report['siteReturn']: failures.append('return to owning site changed geometry')
            for index in range(2):
                if report['container'+str(index)]!=report['container'+str(index)+'Reload']: failures.append('container reload changed geometry')
                failures+=['container '+str(index)+': '+item for item in violations(report['container'+str(index)])]
            for api in ['element','range']:
                if report['container0']['text'][api]==report['container1']['text'][api]: failures.append(f'{api}: font-derived text lacked container isolation')
                if report['protected']['text'][api]==report['native']['text'][api]: failures.append(f'{api}: font-derived text returned native geometry')
                if report['protected']['text'][api]==report['otherIdentity']['text'][api]: failures.append(f'{api}: font-derived text lacked identity variation')
                if report['protected']['text'][api]==report['otherSite']['text'][api]: failures.append(f'{api}: font-derived text lacked site isolation')
            report['failures']=failures
            print(json.dumps(report,indent=2))
        finally: d.quit();server.shutdown()
    if failures and '--diagnose' not in sys.argv: raise AssertionError(failures)

if __name__=='__main__': main()
