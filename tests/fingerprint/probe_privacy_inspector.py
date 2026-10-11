"""Local runtime coverage for site policy, actual inspector, repairs, and settings mounts."""
import http.server, threading, tempfile, json
from pathlib import Path
from probe_daily_defaults import launch
from probe_container_workflows import open_site

class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  body=b'<!doctype html><title>Policy probe</title><div id="target" style="width:120px;height:40px">Text</div>'
  self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass

MEASURE="""const c=document.createElement('canvas');c.width=64;c.height=32;const x=c.getContext('2d');x.fillStyle='#3b7fab';x.fillRect(0,0,64,32);let hash=2166136261;for(const b of x.getImageData(0,0,64,32).data)hash=Math.imul(hash^b,16777619)>>>0;const r=document.getElementById('target').getBoundingClientRect();return {canvas:hash,rect:[r.x,r.y,r.width,r.height],text:x.measureText('Policy').width};"""

def main():
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with tempfile.TemporaryDirectory(prefix='cloakfox-policy-') as temp:
   profile=Path(temp)/'profile';profile.mkdir()
   profile.joinpath('user.js').write_text('user_pref("network.dns.localDomains","one.test,two.test");\nuser_pref("network.trr.mode",5);\nuser_pref("dom.security.https_only_mode",false);\n')
   d=launch(profile,Path(temp)/'gecko.log')
   try:
    d.set_script_timeout(15)
    ids=d.execute_script("const {ContextualIdentityService:C}=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');return [C.create('A','fingerprint','blue').userContextId,C.create('B','fingerprint','red').userContextId];")
    before=d.execute_script("return Services.prefs.getStringPref('cloakfox.container.'+arguments[0]+'.math_seed');",ids[0])
    def sample(host,ucid):
     d.set_context('chrome');open_site(d,f'http://{host}:{server.server_port}/',ucid);return d.execute_script(MEASURE)
    def policy(p):
     d.set_context('chrome');d.execute_script("ChromeUtils.importESModule('resource:///modules/CloakfoxPrivacyPolicy.sys.mjs').setPrivacyPolicy(arguments[0],arguments[1]);",ids[0],p)
    a=sample('one.test',ids[0]);b=sample('two.test',ids[0]);other=sample('one.test',ids[1])
    policy(dict(version=1,preset='standard',exceptions=[dict(site='http://one.test',vectors=['geometry'],expiresAt=4102444800000)]))
    exempt=sample('one.test',ids[0]);assert a['canvas']==exempt['canvas'];assert a['rect']!=exempt['rect'];assert a['text']!=exempt['text']
    assert sample('two.test',ids[0])==b;assert sample('one.test',ids[1])==other
    policy(dict(version=1,preset='standard',exceptions=[dict(site='http://one.test',vectors=['geometry'],expiresAt=1)]));assert sample('one.test',ids[0])==a
    policy(dict(version=1,preset='standard',exceptions=[]));assert sample('one.test',ids[0])==a
    d.set_context('chrome')
    measured=d.execute_async_script("const cb=arguments[arguments.length-1];ChromeUtils.importESModule('resource:///modules/CloakfoxInspector.sys.mjs').measureContainer(arguments[0]).then(cb,e=>cb({error:String(e)}));",ids[0])
    assert 'error' not in measured,measured
    assert 'window' in measured and 'worker' in measured,measured
    assert measured['window']['language']==measured['worker']['language'],measured
    repair=d.execute_script("""const id=arguments[0],pref='cloakfox.s.cloak_cfg_'+id,raw=Services.prefs.getStringPref(pref),cfg=JSON.parse(raw);cfg['headers.User-Agent']='bad';Services.prefs.setStringPref(pref,JSON.stringify(cfg));const I=ChromeUtils.importESModule('resource:///modules/CloakfoxInspector.sys.mjs');const expected=Services.prefs.getStringPref(pref),issue=I.inspectConsistency(cfg).find(x=>x.code==='header-ua'),undo=I.repairConsistency(id,issue,expected),after=JSON.parse(Services.prefs.getStringPref(pref));I.undoConsistencyRepair(undo);const restored=Services.prefs.getStringPref(pref)===expected;Services.prefs.setStringPref(pref,raw);return {restored,repaired:after['headers.User-Agent']===after['navigator.userAgent'],seed:Services.prefs.getStringPref('cloakfox.container.'+id+'.math_seed')};""",ids[0])
    assert repair==dict(restored=True,repaired=True,seed=before),repair
    d.set_context('content');d.get('about:cloakfox')
    from selenium.webdriver.support.ui import WebDriverWait
    WebDriverWait(d,15).until(lambda driver:driver.execute_script("return !!document.getElementById('cfx-inspect-run');"))
    ui=d.execute_script("return ['region-settings','privacy-settings','proxy-manager','template-settings','consistency-inspector'].map(x=>({id:x,children:document.getElementById('cfx-'+x).childElementCount}));")
    assert isinstance(ui,list) and all(x['children'] for x in ui),ui
    print(json.dumps(dict(policy='PASS',inspector=measured,repair='PASS',ui=ui),indent=2))
   finally:d.quit()
 finally:server.shutdown();server.server_close()
if __name__=='__main__':main()
