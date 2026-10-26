"""Check browser-only camera nicknames using a disposable profile and local origin.
Requires an active OBS Virtual Camera; never allows or records camera capture.
"""
import tempfile,json,threading,os
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(b'<!doctype html><title>Camera nickname check</title>Local camera picker check')
 def log_message(self,*args):pass
s=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=s.serve_forever,daemon=True).start()
with tempfile.TemporaryDirectory(prefix='cloakfox-camera-nicknames-') as p:
 Path(p,'user.js').write_text('user_pref("cloakfox.enabled", false);\n')
 o=Options();o.binary_location=os.environ['CLOAKFOX_BIN']
 for a in ['-profile',p,'-purgecaches','-no-remote']:o.add_argument(a)
 d=webdriver.Firefox(options=o,service=Service(service_args=['--allow-system-access'],log_output=str(Path(p)/'gecko.log')))
 def js(code,*args):return d.execute_script(code,*args)
 try:
  d.set_window_size(1100,850)
  d.get('about:cloakfox#sec-media')
  WebDriverWait(d,20).until(lambda _:js("return !!document.querySelector('[data-camera-field=name]')"))
  js("document.querySelector('[data-camera-field=name]').value='OBS Virtual Camera';document.querySelector('[data-camera-field=nickname]').value='Desk setup';document.getElementById('cfx-camera-save').click()")
  assert 'saved' in js("return document.getElementById('cfx-camera-status').textContent")
  d.refresh()
  WebDriverWait(d,20).until(lambda _:js("return document.querySelector('[data-camera-field=nickname]')?.value==='Desk setup'"))
  assert js("return document.querySelector('[data-camera-field=nickname]').getBoundingClientRect().width>0")
  print('PASS visible UI save and refresh persistence',flush=True)
  js("document.getElementById('cfx-camera-heading').scrollIntoView({block:'center'})")
  d.execute_async_script("const done=arguments[arguments.length-1];document.querySelector('.camera-nicknames').scrollIntoView({block:'start',behavior:'instant'});setTimeout(done,300)")
  if os.environ.get('REPORT_DIR'):
   Path(os.environ['REPORT_DIR']).mkdir(parents=True,exist_ok=True)
   d.find_element('css selector','.camera-nicknames').screenshot(str(Path(os.environ['REPORT_DIR'])/'camera-nicknames-desktop.png'))
  assert js("return [...document.querySelectorAll('.camera-nickname-row input')].every(x=>x.getBoundingClientRect().right<=innerWidth)")
  d.set_window_size(660,850)
  js("document.getElementById('cfx-camera-heading').scrollIntoView({block:'center'})")
  d.execute_async_script("const done=arguments[arguments.length-1];document.querySelector('.camera-nicknames').scrollIntoView({block:'start',behavior:'instant'});setTimeout(done,300)")
  if os.environ.get('REPORT_DIR'):
   Path(os.environ['REPORT_DIR']).mkdir(parents=True,exist_ok=True)
   d.find_element('css selector','.camera-nicknames').screenshot(str(Path(os.environ['REPORT_DIR'])/'camera-nicknames-narrow.png'))
  assert js("return [...document.querySelectorAll('.camera-nickname-row input')].every(x=>x.getBoundingClientRect().right<=innerWidth)")
  print('PASS desktop and narrow input layout',flush=True)
  d.get('http://127.0.0.1:'+str(s.server_port)+'/')
  js('navigator.mediaDevices.getUserMedia({video:true,audio:false}).then(s=>s.getTracks().forEach(t=>t.stop())).catch(()=>{});')
  d.set_context('chrome')
  labels=WebDriverWait(d,20).until(lambda _:js("return Array.from(document.getElementById('webRTC-selectCamera-menupopup')?.children||[]).map(x=>x.getAttribute('label'))") or False)
  assert 'Desk setup · OBS Virtual Camera' in labels,labels
  assert 'FaceTime HD Camera' in labels,labels
  print('PASS native picker labels '+json.dumps(labels),flush=True)
  d.set_context('content');d.get('about:cloakfox#sec-media')
  WebDriverWait(d,20).until(lambda _:js("return !!document.querySelector('[data-camera-field=name]')"))
  js("document.getElementById('cfx-camera-reset').click()")
  d.refresh()
  WebDriverWait(d,20).until(lambda _:js("return document.querySelector('[data-camera-field=nickname]')?.value===''") )
  print('PASS restore original names persists',flush=True)
 finally:d.quit();s.shutdown()
