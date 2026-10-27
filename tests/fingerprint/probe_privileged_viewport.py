"""System settings keep native geometry; ordinary sites retain configured masks."""
import json,os,tempfile,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from probe_daily_defaults import launch
from selenium.webdriver.support.ui import WebDriverWait
READ='return [innerWidth,innerHeight,outerWidth,outerHeight]'
class Page(BaseHTTPRequestHandler):
 def do_GET(self):
  body=b'<!doctype html><title>Viewport policy</title>';self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass
def main():
 out=Path(os.environ.get('REPORT_DIR','/tmp/cfx-privileged-viewport'));out.mkdir(parents=True,exist_ok=True)
 server=ThreadingHTTPServer(('127.0.0.1',0),Page);threading.Thread(target=server.serve_forever,daemon=True).start()
 report={}
 try:
  with tempfile.TemporaryDirectory(prefix='cfx-viewport-') as directory:
   profile=Path(directory)/'profile';profile.mkdir();d=launch(profile,out/'gecko.log')
   try:
    d.execute_script("Services.prefs.setBoolPref('cloakfox.enabled',false);Services.prefs.setBoolPref('privacy.resistFingerprinting.letterboxing',false)")
    d.set_context('content');d.get('about:cloakfox');WebDriverWait(d,15).until(lambda d:d.execute_script('return document.readyState')=='complete')
    report['nativeSystem']=d.execute_script(READ)
    d.set_context('chrome');report['systemPrincipal']=d.execute_script('return gBrowser.selectedBrowser.contentPrincipal.isSystemPrincipal')
    d.execute_script("const key='cloakfox.s.cloak_cfg_0',cfg=JSON.parse(Services.prefs.getStringPref(key,'{}'));for(const [k,v]of Object.entries({'window.innerWidth':333,'window.innerHeight':222,'window.outerWidth':444,'window.outerHeight':555}))cfg[k]=v;Services.prefs.setStringPref(key,JSON.stringify(cfg));Services.prefs.setBoolPref('cloakfox.enabled',true);")
    time.sleep(.3);d.set_context('content');report['protectedSystem']=d.execute_script(READ)
    d.get(f'http://127.0.0.1:{server.server_port}/');report['protectedWeb']=d.execute_script(READ)
    report['opaque']=d.execute_async_script(r"""const done=arguments[arguments.length-1],frame=document.createElement('iframe');
      frame.sandbox='allow-scripts';const receive=e=>{if(e.source===frame.contentWindow&&e.data?.kind==='cfx-opaque-viewport'){window.removeEventListener('message',receive);frame.remove();done(e.data);}};
      window.addEventListener('message',receive);frame.srcdoc="<script>parent.postMessage({kind:'cfx-opaque-viewport',origin,values:[innerWidth,innerHeight,outerWidth,outerHeight]},'*')<\/script>";document.body.append(frame);""")
    d.set_context('chrome');report['webPrincipalIsSystem']=d.execute_script('return gBrowser.selectedBrowser.contentPrincipal.isSystemPrincipal')
   finally:d.quit()
 finally:
  server.shutdown();server.server_close();(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 assert report['systemPrincipal'] and not report['webPrincipalIsSystem'],report
 assert report['protectedWeb']==[333,222,444,555],report
 assert report['opaque']['origin']=='null' and report['opaque']['values']==[333,222,444,555],report
 assert report['protectedSystem']==report['nativeSystem'],report
 print('PASS: privileged geometry stays native while web viewport masks remain enforced')
if __name__=='__main__':main()
