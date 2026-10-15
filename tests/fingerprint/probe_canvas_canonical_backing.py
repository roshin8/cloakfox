"""Runtime policy/privacy gate for the internal canonical backing foundation.

No content-facing backend diagnostic is added. Actual native backend routing is
compiled/executed by test_canvas_canonical_backing.py; runtime pixel probes cover
consistency separately. This does not certify the full rendering pipeline.
"""
import hashlib,json,os,tempfile,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
class Page(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.end_headers();self.wfile.write(b'<!doctype html><title>Canonical backing policy</title>')
 def log_message(self,*_):pass
PIXELS="""const c=document.createElement('canvas');c.width=32;c.height=32;const x=c.getContext('2d');x.fillStyle='rgb(128,128,128)';x.fillRect(0,0,32,32);return Array.from(x.getImageData(0,0,32,32).data);"""
def main():
 out=Path(os.environ.get('REPORT_DIR','/tmp/cloakfox-canonical-backing'));out.mkdir(parents=True,exist_ok=True);checks=[];binary=os.environ['CLOAKFOX_BIN']
 def check(ok,name):
  checks.append({'pass':bool(ok),'name':name});print(('PASS 'if ok else 'FAIL ')+name,flush=True);assert ok,name
 server=ThreadingHTTPServer(('127.0.0.1',0),Page);threading.Thread(target=server.serve_forever,daemon=True).start()
 with tempfile.TemporaryDirectory(prefix='cfx-canonical-policy-') as profile:
  driver=None
  def launch():
   options=Options();options.binary_location=binary
   for arg in ['-headless','-purgecaches','-profile',profile]:options.add_argument(arg)
   return webdriver.Firefox(options=options,service=Service(service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
  def chrome(script,*args):
   driver.set_context('chrome')
   try:return driver.execute_script(script,*args)
   finally:driver.set_context('content')
  def cfg():return chrome("const c=JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_0'));delete c['timing:session_key_hi'];delete c['timing:session_key_lo'];return c")
  def pixels():driver.get(f'http://127.0.0.1:{server.server_port}/');return driver.execute_script(PIXELS)
  try:
   driver=launch();runtime=chrome('return {version:Services.appinfo.version,buildID:Services.appinfo.appBuildID}')
   chrome("Services.prefs.setBoolPref('cloakfox.enabled',true)")
   check(cfg()['canvas:canonical_2d'] is False,'internal experiment defaults off')
   chrome("const p='cloakfox.s.cloak_cfg_0';const c=JSON.parse(Services.prefs.getStringPref(p));c.sentinel={manual:'retained',network:'retained'};Services.prefs.setStringPref(p,JSON.stringify(c));")
   before=cfg();off=pixels()
   chrome("Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',true)")
   after=cfg();check(after=={**before,'canvas:canonical_2d':True,'canvas:canonical_gpu':True,'webGl:backend_profile':True,'webgl:typed_readback:disabled':True},'toggle changes only linked renderer policy fields')
   on=pixels();check(on==off,'known-color extraction protection remains unchanged')
   check(any(v!=128 for i,v in enumerate(on) if i%4!=3),'experimental backing does not remove RGB extraction guard')
   check(all(v==255 for i,v in enumerate(on) if i%4==3),'opaque author alpha remains exact')
   check(pixels()==on,'protected pixels remain deterministic on reload')
   created=chrome("const {ContextualIdentityService}=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');const id=ContextualIdentityService.create('Canonical backing test','fingerprint','blue').userContextId;return JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+id))")
   check(created['canvas:canonical_2d'] is True,'new containers inherit internal policy')
   chrome("const p='cloakfox.s.cloak_cfg_0';const c=JSON.parse(Services.prefs.getStringPref(p));c['canvas:canonical_2d']=false;Services.prefs.setStringPref(p,JSON.stringify(c));Services.prefs.savePrefFile(null);")
   driver.quit();driver=launch();check(cfg()==after,'restart repairs stale internal flag without changing identity or sentinel')
   check(pixels()==on,'policy and masked pixels survive browser restart')
   rejected=chrome("try {Services.prefs.setStringPref('cloakfox.experimental.canvas_pipeline','true');return false;}catch {return true;}")
   check(rejected and cfg()['canvas:canonical_2d'] is True,'preference service rejects wrong-type writes without changing policy')
   chrome("Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',false)")
   check(cfg()==before,'turning experiment off restores only policy field')
   chrome("Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',true);Services.prefs.setBoolPref('cloakfox.enabled',false)")
   native=pixels();check(all(v==128 for i,v in enumerate(native) if i%4!=3),'new master-off context uses native readback')
  finally:
   if driver:driver.quit()
   server.shutdown();server.server_close()
   (out/'result.json').write_text(json.dumps({'binary':binary,'runtime':runtime,'xulSHA256':hashlib.sha256(Path(binary).parent.joinpath('XUL').read_bytes()).hexdigest(),'scope':'internal backing foundation only','checks':checks},indent=2)+'\n')
if __name__=='__main__':main()
