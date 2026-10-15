"""Actual cross-top-level transfer retains source ownership, independently of pixel standardization."""
import json,os,tempfile,threading,time
from pathlib import Path
from http.server import ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from probe_canvas_consistency import Page
SCRIPT=r'''
const done=arguments[arguments.length-1];(async()=>{
 const c=document.createElement('canvas');c.width=c.height=8;const x=c.getContext('2d');x.fillStyle='#807060';x.fillRect(0,0,8,8);const source=Array.from(x.getImageData(0,0,1,1).data),result={source};
 for(const [id,host]of [['same','127.0.0.1'],['foreign','localhost']]){
  let popup,recipient;const ready=new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('popup ready timeout')),20000);const handler=e=>{if(e.data.id===id&&e.data.ready&&e.origin===location.origin){recipient=e.source;clearTimeout(timer);removeEventListener('message',handler);resolve()}};addEventListener('message',handler)});
  const url=new URL((id==='foreign'?'/embedded':'/receiver')+'?id='+id,location.href);url.hostname=host;popup=window.open(url.href,'owner-'+id);
  try{await ready;const bitmap=await createImageBitmap(c);result[id]=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('popup result timeout '+id)),20000);const handler=e=>{if(e.source===recipient&&e.data.id===id&&!e.data.ready){clearTimeout(timer);removeEventListener('message',handler);resolve(e.data)}};addEventListener('message',handler);recipient.postMessage({id,bitmap},'*',[bitmap])})}finally{popup.close()}
 }
 done(result);
})().catch(e=>done({error:String(e),stack:e.stack}));
'''
class OwnerPage(Page):
 def do_GET(self):
  if self.path.startswith('/embedded'):
   data=('<!doctype html><iframe src="http://127.0.0.1:'+str(self.server.server_port)+'/receiver?id=foreign"></iframe>').encode()
   self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
  if not self.path.startswith('/receiver'):
   code=SCRIPT.replace('const done=arguments[arguments.length-1];','const done=result=>{window.ownerTransferResult=result};')
   data=('<!doctype html><script>'+code+'</script>').encode()
   self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
  data=b"""<!doctype html><script>const id=new URLSearchParams(location.search).get('id'),sender=opener||parent.opener;onmessageerror=e=>sender.postMessage({id,messageError:true},'*');onmessage=e=>{if(!e.data.bitmap)return;try{const c=document.createElement('canvas');c.width=c.height=8;const x=c.getContext('2d');x.drawImage(e.data.bitmap,0,0);e.data.bitmap.close();sender.postMessage({id,pixels:Array.from(x.getImageData(0,0,1,1).data)},'*')}catch(error){sender.postMessage({id,denied:true,error:error.name},'*')}};sender.postMessage({id,ready:true},'*');</script>"""
  self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

def main():
 out=Path(os.environ.get('REPORT_DIR','/tmp/cfx-owner-transfer'));out.mkdir(parents=True,exist_ok=True);report={'checks':[]}
 def check(ok,name):report['checks'].append({'pass':bool(ok),'name':name});print(('PASS 'if ok else'FAIL ')+name,flush=True)
 server=ThreadingHTTPServer(('127.0.0.1',0),OwnerPage);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with tempfile.TemporaryDirectory(prefix='cfx-owner-transfer-')as profile:
   opts=Options();opts.binary_location=os.environ['CLOAKFOX_BIN']
   for a in ['-headless','-purgecaches','-profile',profile]:opts.add_argument(a)
   opts.set_preference('cloakfox.experimental.canvas_pipeline',True);opts.set_preference('dom.disable_open_during_load',False)
   d=webdriver.Firefox(options=opts,service=Service(service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
   try:
    d.set_script_timeout(60);d.set_context('chrome');report['runtime']=d.execute_script('return{buildID:Services.appinfo.appBuildID,version:Services.appinfo.version}')
    d.execute_script("Services.prefs.setBoolPref('cloakfox.enabled',true);const k='cloakfox.s.cloak_cfg_0',c=JSON.parse(Services.prefs.getStringPref(k,'{}'));c['canvas:seed']=0;c['fingerprint:secret']='ABEiM0RVZneImaq7zN3u/wARIjNEVWZ3iJmqu8zd7v8=';Services.prefs.setStringPref(k,JSON.stringify(c));");time.sleep(.4)
    d.set_context('content');d.get(f'http://127.0.0.1:{server.server_port}/');r=WebDriverWait(d,60).until(lambda driver:driver.execute_script('return window.ownerTransferResult||null'));report['result']=r;check('error'not in r,'owner-transfer corpus completes')
    if'error'not in r:
     check(r['source']==[128,112,96,255],'source authored pixels remain exact')
     check(r['same'].get('pixels')==r['source'],'same top-level site preserves transferred producer ownership')
     check(r['foreign'].get('denied')or r['foreign'].get('messageError'),'different top-level site cannot expose transferred pixels')
   finally:d.quit()
 finally:server.shutdown();server.server_close();(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 return int(any(not c['pass']for c in report['checks']))
if __name__=='__main__':raise SystemExit(main())
