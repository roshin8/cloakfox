"""Disposable-profile route-choice tests, using only local TLS proxy fixtures."""
import http.server,json,ssl,subprocess,tempfile,threading,os
from pathlib import Path
from selenium.webdriver.support.ui import WebDriverWait
from probe_daily_defaults import launch
from probe_ip_conflicts import Proxy
class RouteProxy(Proxy):
    def do_CONNECT(self):
        if self.path not in ['api.ipify.org:443','api6.ipify.org:443','api64.ipify.org:443','httpbin.org:443']:
            self.send_error(502);return
        super().do_CONNECT()

with tempfile.TemporaryDirectory(prefix='cloakfox-ip-routes-') as tmp:
    root=Path(tmp);profile=root/'profile';profile.mkdir()
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(root/'key'),'-out',str(root/'cert'),'-days','1','-subj','/CN=api.ipify.org'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(root/'cert',root/'key')
    servers=[]
    for index in [1,2]:
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),RouteProxy)
        server.ip=f'192.0.2.{index}';server.ipv6=f'2001:db8::{index}';server.hits=0;server.tls=tls
        threading.Thread(target=server.serve_forever,daemon=True).start();servers.append(server)
    driver=launch(profile,root/'gecko.log')
    try:
        driver.set_context('chrome');driver.set_script_timeout(45)
        driver.execute_script('Cc["@mozilla.org/security/certoverride;1"].getService(Ci.nsICertOverrideService).setDisableAllSecurityChecksAndLetAttackersInterceptMyData(true);')
        driver.execute_script("window.__ipRoutes=ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs');")
        driver.execute_script("ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkPolicy.sys.mjs').setContainerNetwork(1,{mode:1,proxyURL:'http://127.0.0.1:'+arguments[0],webrtcMode:2});",servers[0].server_port)
        def check(mode):
            return driver.execute_async_script("const done=arguments[arguments.length-1];window.__ipRoutes.setIPCheckRoute(arguments[0]);window.__ipRoutes.checkContainerIP(1,{force:true}).then(done,e=>done({error:String(e)}));",mode)
        driver.execute_script("Services.prefs.setBoolPref('cloakfox.ip_conflicts.enabled',true)")
        baseline=driver.execute_script('return [gBrowser.tabs.length,gBrowser.selectedTab._tPos]')
        print('Checking native background route',flush=True)
        background=check('background');assert background['ipv4']=='192.0.2.1',background
        print('Checking native tab route',flush=True)
        tab=check('tab');assert tab['ipv4']=='192.0.2.1' and tab['ipv6']=='2001:db8::1',tab
        assert driver.execute_script('return [gBrowser.tabs.length,gBrowser.selectedTab._tPos]')==baseline,'probe tabs leaked or changed selection'
        assert driver.execute_script('return window.__ipRoutes.ipHistory().length')==0,'probe counted as a website visit'
        # A tab-based proxy extension deliberately chooses a different local proxy
        # for requests with a real tab ID. No external traffic is needed.
        addon=root/'addon';addon.mkdir()
        (addon/'manifest.json').write_text(json.dumps({'manifest_version':2,'name':'Local route fixture','version':'1.0','browser_specific_settings':{'gecko':{'id':'route-fixture@cloakfox.test'}},'permissions':['proxy','tabs','<all_urls>'],'background':{'scripts':['background.js']}}))
        (addon/'background.js').write_text("browser.proxy.onRequest.addListener(async d=>({type:'http',host:'127.0.0.1',port:d.tabId===-1?%d:((await browser.tabs.get(d.tabId)).hidden?%d:%d)}),{urls:['https://api.ipify.org/*','https://api6.ipify.org/*','https://api64.ipify.org/*','https://httpbin.org/*']});"%(servers[0].server_port,servers[1].server_port,servers[0].server_port))
        driver.execute_script("ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkPolicy.sys.mjs').setContainerNetwork(1,{mode:0,proxyURL:'',webrtcMode:2});Services.prefs.setIntPref('network.proxy.type',1);Services.prefs.setStringPref('network.proxy.http','127.0.0.1');Services.prefs.setIntPref('network.proxy.http_port',arguments[0]);Services.prefs.setStringPref('network.proxy.ssl','127.0.0.1');Services.prefs.setIntPref('network.proxy.ssl_port',arguments[0]);",servers[0].server_port)
        driver.install_addon(str(addon),temporary=True)
        print('Checking tab-ID-based proxy extension',flush=True)
        background=check('background');tab=check('tab')
        assert background['ipv4']=='192.0.2.1',background
        assert tab['ipv4']=='192.0.2.2' and tab['ipv6']=='2001:db8::2',tab
        driver.execute_script("window.__ipRoutes.setIPCheckRoute('background')")
        assert driver.execute_script('return window.__ipRoutes.ipConflictResults().length')==0
        driver.execute_script("ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkPolicy.sys.mjs').setContainerNetwork(1,{mode:2,proxyURL:'',webrtcMode:2});")
        blocked=check('tab');assert not blocked['ip'],blocked
        assert driver.execute_script('return [gBrowser.tabs.length,gBrowser.selectedTab._tPos]')==baseline
        driver.set_context('content');driver.get('about:cloakfox')
        WebDriverWait(driver,20).until(lambda _:driver.execute_script("return !!document.getElementById('cfx-ip-check-route')"))
        driver.execute_script("const s=document.getElementById('cfx-ip-check-route');s.value='background';s.dispatchEvent(new Event('change')); ")
        assert 'Cached results cleared' in driver.execute_script("return document.getElementById('cfx-ip-route-status').textContent")
        print(json.dumps({'passed':True,'native_proxy':'both modes','tab_proxy_extension':'correct distinct routes','cache_switch':'cleared','blocked_route':'unknown','probe_tabs':'cleaned up','ui':'wired'}))
    finally:
        driver.quit()
        for server in servers:server.shutdown()
