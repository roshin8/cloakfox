#!/usr/bin/env python3
"""Headless native regression: privileged sliders stay native; content touch stays owned.

Run against the rebuilt candidate only with MOZ_REMOTE_ALLOW_SYSTEM_ACCESS=1. Uses a disposable profile and loopback
content, never installed applications or personal settings. No global privacy
controls are weakened outside this temporary test profile.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from probe_container_workflows import chrome,open_site

LAYOUT=r'''
const area=document.createElement('section');area.style.cssText='display:block;width:180px;height:40px;overflow:scroll;';
const content=document.createElementNS('http://www.w3.org/1999/xhtml','div');content.style.cssText='width:1200px;height:500px';
const range=document.createElementNS('http://www.w3.org/1999/xhtml','input');range.type='range';range.min='0';range.max='100';range.value='30';content.append(range);area.append(content);document.body.append(area);
const bounds=area.getBoundingClientRect(),rangeBounds=range.getBoundingClientRect();
area.scrollTop=75;range.value='60';range.dispatchEvent(new Event('input',{bubbles:true}));
const result={touchEvent:typeof TouchEvent,touch:typeof Touch,touchList:typeof TouchList,width:bounds.width,height:bounds.height,rangeWidth:rangeBounds.width,rangeValue:range.value,scroll:area.scrollTop,ready:document.readyState};
area.remove();return result;
'''
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b'<!doctype html><title>Owned touch policy probe</title><body>Owned native touch policy</body>')
 def log_message(self,*args):pass

def main():
 binary=Path(os.environ['CLOAKFOX_BIN']).resolve();out=Path(os.environ.get('REPORT_DIR','/tmp/cloakfox-touch-document-policy'));out.mkdir(parents=True,exist_ok=True)
 report={'binary':str(binary),'xulSHA256':hashlib.sha256((binary.parent/'XUL').read_bytes()).hexdigest(),'checks':[],'settings':[],'content':[],'completed':False}
 def check(ok,name):report['checks'].append({'pass':bool(ok),'name':name});print(('PASS ' if ok else 'FAIL ')+name,flush=True)
 def save():(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with tempfile.TemporaryDirectory(prefix='cloakfox-touch-doc-') as temp:
   options=Options();options.binary_location=str(binary);options.page_load_strategy='none'
   for arg in ['-headless','-purgecaches','-profile',temp]:options.add_argument(arg)
   options.set_preference('cloakfox.enabled',True)
   driver=webdriver.Firefox(options=options,service=Service(os.environ.get('GECKODRIVER','/opt/homebrew/bin/geckodriver'),service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
   try:
    driver.set_script_timeout(15);driver.set_page_load_timeout(15);wait=WebDriverWait(driver,15)
    driver.set_context('content');base=driver.current_window_handle
    report['runtime']=chrome(driver,'return {version:Services.appinfo.version,buildID:Services.appinfo.appBuildID};')
    check(report['runtime']['version'].startswith('159.'),'actual Firefox159 native touch candidate')
    ids=chrome(driver,"return Array.from({length:3},(_,i)=>cis.create('Touch document '+i,'fingerprint','blue').userContextId);")
    # Force privileged layout to disagree with content policy in both directions.
    for native_pref,persona_touch in [(1,0),(0,5)]:
     chrome(driver,"Services.prefs.setIntPref('dom.w3c_touch_events.enabled',arguments[0]);const key='cloakfox.s.cloak_cfg_0',config=JSON.parse(Services.prefs.getStringPref(key));config['navigator:maxTouchPoints']=arguments[1];Services.prefs.setStringPref(key,JSON.stringify(config));",native_pref,persona_touch)
     driver.set_context('content');driver.get(f'about:cloakfox?touch-policy-native={native_pref}#sec-identity')
     wait.until(lambda d:d.execute_script("return !!document.querySelector('[data-category=identity]') && !!document.getElementById('grp-navigator')"))
     driver.execute_script("document.querySelector('[data-category=identity]').click();")
     wait.until(lambda d:d.execute_script("const node=document.getElementById('sec-identity');return !!node && !node.hidden && node.getBoundingClientRect().width>0;"))
     system=chrome(driver,"return Services.wm.getMostRecentWindow('navigator:browser').gBrowser.selectedBrowser.contentPrincipal.isSystemPrincipal;")
     driver.set_context('content');value=driver.execute_script(LAYOUT)
     check(system,'about Identity uses actual system document principal')
     check(value['width']>0 and value['height']>0 and value['rangeWidth']>0 and value['scroll']>0 and value['rangeValue']=='60',f'privileged Identity native scrollbar and range stay responsive with persona touch{persona_touch}')
     check(value['touchEvent']==('function' if native_pref else 'undefined') and value['touch']==('function' if native_pref else 'undefined'),f'privileged Touch interfaces follow native preference{native_pref}, independent of content mask{persona_touch}')
     report['settings'].append({'nativePreference':native_pref,'personaTouch':persona_touch,'system':system,'measurement':value});save()
    cases=[('own zero',ids[0],0,1,False),('own positive',ids[1],5,0,True),('own zero beside positive default',ids[0],0,1,False),('missing key',ids[2],'missing',1,False),('malformed key',ids[2],'malformed-key',1,False),('unknown exact owner config',ids[2],'unknown',1,False),('malformed exact owner config',ids[2],'malformed-config',1,False)]
    for label,owner,value,native_pref,expected in cases:
     chrome(driver,r'''const key='cloakfox.s.cloak_cfg_'+arguments[0];Services.prefs.setIntPref('dom.w3c_touch_events.enabled',arguments[2]);
      const defaults=JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_0'));defaults['navigator:maxTouchPoints']=9;Services.prefs.setStringPref('cloakfox.s.cloak_cfg_0',JSON.stringify(defaults));
      if(arguments[1]==='unknown'){Services.prefs.clearUserPref(key);return;}
      if(arguments[1]==='malformed-config'){Services.prefs.setStringPref(key,'not-json');return;}
      const config=JSON.parse(Services.prefs.getStringPref(key,JSON.stringify(defaults)));
      if(arguments[1]==='missing')delete config['navigator:maxTouchPoints'];else config['navigator:maxTouchPoints']=arguments[1]==='malformed-key'?'5':arguments[1];
      Services.prefs.setStringPref(key,JSON.stringify(config));''',owner,value,native_pref)
     _,actual=open_site(driver,f'http://127.0.0.1:{server.server_port}/?case={label.replace(" ","-")}',owner)
     driver.set_context('content');wait.until(lambda d:d.execute_script('return document.readyState')=='complete');measurement=driver.execute_script(LAYOUT)
     check(actual==owner,label+': actual container owner')
     check(measurement['touchEvent']==('function' if expected else 'undefined') and measurement['touch']==('function' if expected else 'undefined'),label+': Touch exposure uses exact owner mask or denies, never foreign/default/native capability')
     if isinstance(value,int):
      points=driver.execute_script('return navigator.maxTouchPoints;');measurement['navigatorMaxTouchPoints']=points;check(points==value,label+': native Navigator touch count agrees with Touch interface exposure')
     check(measurement['rangeWidth']>0 and measurement['scroll']>0,label+': ordinary content native widgets remain usable')
     report['content'].append({'case':label,'owner':owner,'nativePreference':native_pref,'measurement':measurement});save()
     driver.close();driver.switch_to.window(base)
    # The explicit master-off control restores native content behavior.
    chrome(driver,"Services.prefs.setBoolPref('cloakfox.enabled',false);Services.prefs.setIntPref('dom.w3c_touch_events.enabled',1);")
    _,actual=open_site(driver,f'http://127.0.0.1:{server.server_port}/?master-off',ids[0]);driver.set_context('content');wait.until(lambda d:d.execute_script('return document.readyState')=='complete');native=driver.execute_script(LAYOUT)
    check(actual==ids[0] and native['touchEvent']=='function','master off preserves native content Touch preference')
    report['masterOff']=native;report['completed']=True
   finally:driver.quit()
 finally:server.shutdown();server.server_close();save()
 return 1 if not report['completed'] or any(not c['pass'] for c in report['checks']) else 0
if __name__=='__main__':raise SystemExit(main())
