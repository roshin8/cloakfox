"""Route-scoped IP comparison using TLS proxy fixtures, with no external traffic."""
import http.server,json,ssl,subprocess,tempfile,threading
from pathlib import Path
from probe_daily_defaults import launch
from selenium.webdriver.support.ui import WebDriverWait
class Proxy(http.server.BaseHTTPRequestHandler):
 def do_CONNECT(self):
  assert self.path in ['api64.ipify.org:443','httpbin.org:443'],self.path
  host=self.path.split(':')[0]
  self.server.hits+=1
  self.send_response(200);self.end_headers()
  with self.server.tls.wrap_socket(self.connection,server_side=True) as conn:
   request=b''
   while b'\r\n\r\n' not in request: request+=conn.recv(4096)
   assert b'Cookie:' not in request
   body=json.dumps({'origin' if host=='httpbin.org' else 'ip':self.server.ip}).encode()
   if host=='api64.ipify.org' and getattr(self.server,'fail_primary',False):body=b'{}'
   conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body)
 def log_message(self,*a):pass
def main():
 with tempfile.TemporaryDirectory(prefix='cfx-ip-conflicts-') as t:
  root=Path(t);profile=root/'profile';profile.mkdir()
  subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(root/'key'),'-out',str(root/'cert'),'-days','1','-subj','/CN=api64.ipify.org'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(root/'cert',root/'key')
  servers=[]
  for _ in range(2):
   s=http.server.ThreadingHTTPServer(('127.0.0.1',0),Proxy);s.ip='192.0.2.1';s.hits=0;s.tls=tls
   threading.Thread(target=s.serve_forever,daemon=True).start();servers.append(s)
  d=launch(profile,root/'gecko.log')
  try:
   d.execute_script("Cc['@mozilla.org/security/certoverride;1'].getService(Ci.nsICertOverrideService).setDisableAllSecurityChecksAndLetAttackersInterceptMyData(true);")
   ids=d.execute_script("const c=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService;return [c.create('IP one','fingerprint','blue').userContextId,c.create('IP two','fingerprint','green').userContextId];")
   def route(id,mode,port=0):
    d.execute_script("ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkPolicy.sys.mjs').setContainerNetwork(arguments[0],{mode:arguments[1],proxyURL:arguments[1]===1?'http://127.0.0.1:'+arguments[2]:'',webrtcMode:2});",id,mode,port)
   def check(id):
    return d.execute_async_script("const done=arguments[arguments.length-1];ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs').checkContainerIP(arguments[0],{force:true}).then(r=>done({ip:r.ip,error:r.error}));",id)
   def rows():return d.execute_script("return ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs').ipConflictResults();")
   for id,s in zip(ids,servers):route(id,1,s.server_port);assert check(id)['ip']=='192.0.2.1'
   assert all(r['conflicts'] for r in rows()),rows()
   assert all(s.hits==1 for s in servers)
   d.execute_script("Services.prefs.setStringPref('cloakfox.ip_conflicts.response','notification');Services.prefs.setBoolPref('cloakfox.ip_conflicts.enabled',true);const w=Services.wm.getMostRecentWindow('navigator:browser');w.gBrowser.selectedTab=w.gBrowser.addTab('https://api64.ipify.org/?fixture=page',{userContextId:arguments[0],triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});",ids[1])
   # Settings measurements and a visit to another hostname cannot imply a visit here.
   WebDriverWait(d,15).until(lambda d:d.execute_script("return ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs').ipHistory().some(row=>row.ucid===arguments[0]&&row.hostname==='api64.ipify.org');",ids[1]))
   assert not d.execute_script("const w=Services.wm.getMostRecentWindow('navigator:browser');return !!w.gBrowser.getNotificationBox(w.gBrowser.selectedBrowser).getNotificationWithValue('cloakfox-ip-conflict');")
   assert d.execute_script("const m=ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs');m.recordIPAccess('192.0.2.1',arguments[0],'https://httpbin.org/ip');return m.conflictForIP(arguments[1],'192.0.2.1','https://api64.ipify.org/');",ids[0],ids[1]) == []
   assert d.execute_script("return ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs').conflictForIP(arguments[0],'192.0.2.1','https://api64.ipify.org/');",ids[1]) == []
   d.execute_script("const m=ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs');m.recordIPAccess('192.0.2.1',arguments[0],'https://api64.ipify.org/');Services.wm.getMostRecentWindow('navigator:browser').gBrowser.selectedBrowser.reload();",ids[0])
   WebDriverWait(d,15).until(lambda d:d.execute_script("const w=Services.wm.getMostRecentWindow('navigator:browser');return !!w.gBrowser.getNotificationBox(w.gBrowser.selectedBrowser).getNotificationWithValue('cloakfox-ip-conflict');"))
   d.execute_script("Services.prefs.setBoolPref('cloakfox.ip_conflicts.enabled',false)")
   # Full warning page keeps the original container and only continues after an explicit action.
   d.execute_script("const m=ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs');m.recordIPAccess('192.0.2.1',arguments[0],'https://api64.ipify.org/');Services.prefs.setStringPref('cloakfox.ip_conflicts.response','warning');Services.prefs.setBoolPref('cloakfox.ip_conflicts.enabled',true);const w=Services.wm.getMostRecentWindow('navigator:browser');w.gBrowser.selectedBrowser.loadURI(Services.io.newURI('https://api64.ipify.org/?fixture=warning'),{triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});",ids[0])
   WebDriverWait(d,15).until(lambda d:d.execute_script("return Services.wm.getMostRecentWindow('navigator:browser').gBrowser.selectedBrowser.currentURI.spec.startsWith('chrome://browser/content/cloakfox/ip-warning.html?token=');"))
   d.switch_to.window(d.window_handles[-1]);d.set_context('content')
   WebDriverWait(d,10).until(lambda d:d.find_element('id','warning-detail').text.startswith('IP two'))
   assert d.find_element('id','recheck').is_enabled()
   assert d.find_element('id','current-container').text == 'IP two'
   assert d.find_element('id','current-ip').text == '192.0.2.1'
   assert 'IP one' in d.find_element('id','conflicting-containers').text
   for width, theme in [(1100, 'light'), (420, 'dark')]:
    d.set_window_size(width, 900)
    d.execute_script('document.documentElement.dataset.theme=arguments[0]', theme)
    assert d.execute_script('return document.documentElement.scrollWidth <= innerWidth')
    d.save_screenshot('/tmp/cloakfox-ip-warning-' + theme + '.png')
   d.set_context('chrome')
   token=d.execute_script("return new URL(Services.wm.getMostRecentWindow('navigator:browser').gBrowser.selectedBrowser.currentURI.spec).searchParams.get('token');")
   warning=d.execute_script("return ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs').getIPWarning(arguments[0]);",token)
   assert warning['id']==ids[1] and warning['ip']=='192.0.2.1',warning
   result=d.execute_async_script("const done=arguments[arguments.length-1];ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs').resolveIPWarning(arguments[0],'recheck').then(done);",token)
   assert result['conflict'],result
   route(ids[1],2)
   failed=d.execute_async_script("const done=arguments[arguments.length-1];ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs').resolveIPWarning(arguments[0],'recheck').then(done);",token)
   assert failed.get('error') and not failed.get('continued'),failed
   route(ids[1],1,servers[1].server_port)
   result=d.execute_async_script("const done=arguments[arguments.length-1];ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs').resolveIPWarning(arguments[0],'once').then(done);",token)
   assert result['continued'],result
   WebDriverWait(d,10).until(lambda d:d.execute_script("return Services.wm.getMostRecentWindow('navigator:browser').gBrowser.selectedBrowser.currentURI.spec.includes('fixture=warning');"))
   assert d.execute_script("return Number(Services.wm.getMostRecentWindow('navigator:browser').gBrowser.selectedBrowser.getAttribute('usercontextid')); ")==ids[1]
   d.execute_script("Services.prefs.setBoolPref('cloakfox.ip_conflicts.enabled',false)")
   page_hits=servers[1].hits
   servers[1].ip='192.0.2.2';assert check(ids[1])['ip']=='192.0.2.2'
   assert all(not r['conflicts'] for r in rows())
   route(ids[1],2);assert not any(r['ucid']==ids[1] for r in rows())
   assert check(ids[1])['ip'] is None
   assert any(r['error'] for r in rows() if r['ucid']==ids[1])
   assert servers[1].hits==page_hits+1
   route(ids[1],1,servers[1].server_port);servers[1].fail_primary=True
   assert check(ids[1])['ip']=='192.0.2.2'
   print('PASS: routed measurements, notification, warning page, conflict/unknown recheck, temporary continue, retained container, route invalidation, httpbin fallback; no external requests')
  finally:
   d.quit()
   for s in servers:s.shutdown();s.server_close()
if __name__=='__main__':main()
