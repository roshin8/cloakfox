import sys,tempfile,json
from pathlib import Path
sys.path.insert(0,'tests/fingerprint')
from probe_daily_defaults import launch
from http.server import BaseHTTPRequestHandler,HTTPServer
from threading import Thread
class Page(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(b'<style>body{color:rgb(0,0,0)}@media(prefers-color-scheme:dark){body{color:rgb(255,255,255)}}</style>Appearance')
 def log_message(self,*a):pass
server=HTTPServer(('127.0.0.1',0),Page);Thread(target=server.serve_forever,daemon=True).start()
with tempfile.TemporaryDirectory() as t:
 p=Path(t)/'profile';p.mkdir();d=launch(p,Path(t)/'log')
 try:
  d.set_context('content');d.get('about:cloakfox')
  for pref,dark in [(0,True),(1,False),(2,None)]:
   d.set_context('chrome');d.execute_script("Services.prefs.setIntPref('layout.css.prefers-color-scheme.content-override',arguments[0]);",pref)
   d.set_context('content');d.get('http://127.0.0.1:'+str(server.server_port))
   result=d.execute_script("return {dark:matchMedia('(prefers-color-scheme: dark)').matches,css:getComputedStyle(document.body).color}")
   assert (result['css']=='rgb(255, 255, 255)')==result['dark'],result
   if dark is not None: assert result['dark']==dark,result
   print(pref,result)
 finally:d.quit()
