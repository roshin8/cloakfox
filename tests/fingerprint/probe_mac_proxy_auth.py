"""Verify container popup auth fields and wire credentials in a disposable profile."""
import base64,http.server,json,ssl,subprocess,tempfile,threading,os,zipfile
from pathlib import Path
from selenium.webdriver.support.ui import WebDriverWait
from probe_daily_defaults import launch
class Proxy(http.server.BaseHTTPRequestHandler):
    def do_CONNECT(self):
        if self.path != 'api.ipify.org:443':self.send_error(502);return
        self.server.auth.append(self.headers.get('Proxy-Authorization'))
        self.send_response(200);self.end_headers()
        with self.server.tls.wrap_socket(self.connection,server_side=True) as conn:
            request=b''
            while b'\r\n\r\n' not in request:request+=conn.recv(4096)
            body=b'{"ip":"192.0.2.55"}'
            conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body)
    def log_message(self,*_):pass
with tempfile.TemporaryDirectory(prefix='cloakfox-mac-auth-') as tmp:
    root=Path(tmp);profile=root/'profile';profile.mkdir()
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(root/'key'),'-out',str(root/'cert'),'-days','1','-subj','/CN=api.ipify.org'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(root/'cert',root/'key')
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Proxy);server.tls=tls;server.auth=[]
    threading.Thread(target=server.serve_forever,daemon=True).start()
    addon=root/'addon';addon.mkdir()
    manifest={'manifest_version':2,'name':'Container proxy editor fixture','version':'1.0','browser_specific_settings':{'gecko':{'id':'@testpilot-containers'}},'browser_action':{'default_title':'Multi-Account Containers','default_popup':'popup.html'},'permissions':['proxy','tabs','contextualIdentities','storage','<all_urls>'],'background':{'scripts':['background.js']}}
    (addon/'manifest.json').write_text(json.dumps(manifest))
    (addon/'background.js').write_text("browser.proxy.onRequest.addListener(async d=>{const t=d.tabId<0?null:await browser.tabs.get(d.tabId);const s=await browser.storage.local.get('proxifiedContainersKey');return s.proxifiedContainersKey?.find(x=>x.cookieStoreId===t?.cookieStoreId)?.proxy||{type:'http',host:'127.0.0.1',port:%d};},{urls:['https://api.ipify.org/*']});"%server.server_port)
    with zipfile.ZipFile(Path(os.environ['CLOAKFOX_BIN']).parents[1]/'Resources/distribution/extensions/@testpilot-containers.xpi') as package:
        (addon/'popup.css').write_bytes(package.read('css/popup.css'))
    (addon/'popup.html').write_text('''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="popup.css"><title>Proxy editor fixture</title><div id="proxy-title-container-name">Proxy test</div><input id="edit-container-panel-name-input" value="Proxy test"><div id="advanced-proxy-settings-panel" class="panel"><form class="advanced-proxy-panel-content"><input id="edit-advanced-proxy-input" value="http://127.0.0.1:PORT"><button id="clear-advanced-proxy-input" type="button">Clear</button><button id="submit-advanced-proxy" type="submit">Apply to Container</button></form></div><script src="popup.js"></script>'''.replace('PORT',str(server.server_port)))
    (addon/'popup.js').write_text("window.originalSaveCalled=false;document.getElementById('submit-advanced-proxy').addEventListener('click',()=>{window.originalSaveCalled=true;});")
    driver=launch(profile,root/'gecko.log')
    try:
        driver.set_script_timeout(30)
        driver.execute_script("ChromeUtils.importESModule('resource:///modules/CloakfoxContainerProxyEditor.sys.mjs').initContainerProxyEditor();Cc['@mozilla.org/security/certoverride;1'].getService(Ci.nsICertOverrideService).setDisableAllSecurityChecksAndLetAttackersInterceptMyData(true);")
        driver.install_addon(str(addon),temporary=True)
        ident=driver.execute_script("return ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService.create('Proxy test','fingerprint','blue').userContextId;")
        password='p=ss:with@special/chars'
        driver.execute_async_script("const done=arguments[arguments.length-1];ChromeUtils.importESModule('resource:///modules/CloakfoxContainerProxyEditor.sys.mjs').saveMACProxy({cookieStoreId:'firefox-container-'+arguments[0],name:'Proxy test',server:'http://127.0.0.1:'+arguments[1],username:'customer-city-chicago',password:arguments[2]}).then(done,e=>done({error:String(e)}));",ident,server.server_port,password)
        driver.execute_script("ChromeUtils.importESModule('moz-src:///browser/components/customizableui/CustomizableUI.sys.mjs').CustomizableUI.addWidgetToArea('_testpilot-containers-browser-action','nav-bar');")
        driver.execute_script("ChromeUtils.importESModule('resource:///modules/CloakfoxProxyIndicator.sys.mjs').initProxyIndicator();window.__indicatorOriginalTab=gBrowser.selectedTab;window.__indicatorTab=gBrowser.addTab('about:blank',{userContextId:arguments[0],triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});gBrowser.selectedTab=window.__indicatorTab;",ident)
        WebDriverWait(driver,10).until(lambda _:driver.execute_script("const b=document.getElementById('cloakfox-container-proxy-indicator');return b && !b.hidden && b.getAttribute('value')==='Proxy' && b.getAttribute('tooltiptext').includes('127.0.0.1');"))
        WebDriverWait(driver,10).until(lambda _:driver.execute_script("const b=document.getElementById('cloakfox-mac-proxy-badge');return b && !b.hidden;"))
        assert driver.execute_script("const b=document.getElementById('cloakfox-mac-proxy-badge').getBoundingClientRect();const a=document.getElementById('_testpilot-containers-browser-action').getBoundingClientRect();return b.width===14 && b.height===14 && b.left>=a.left && b.right<=a.right && b.top>=a.top && b.bottom<=a.bottom;"), 'toolbar badge is outside its button'
        driver.execute_script('gBrowser.selectedTab=window.__indicatorOriginalTab;')
        WebDriverWait(driver,10).until(lambda _:driver.execute_script("return document.getElementById('cloakfox-container-proxy-indicator').hidden;"))
        assert driver.execute_script("return document.getElementById('cloakfox-mac-proxy-badge').hidden;")
        driver.execute_script('gBrowser.selectedTab=window.__indicatorTab;')
        url=driver.execute_script("return ChromeUtils.importESModule('resource://gre/modules/ExtensionParent.sys.mjs').ExtensionParent.GlobalManager.getExtension('@testpilot-containers').baseURI.resolve('popup.html');")
        driver.set_context('content');driver.get(url)
        WebDriverWait(driver,15).until(lambda _:driver.execute_script("return document.getElementById('cfx-mac-proxy-password')?.value === arguments[0]",password))
        assert driver.execute_script("return document.getElementById('cfx-mac-proxy-password').getBoundingClientRect().height>=36"),'password field is too short'
        assert driver.execute_script("return document.documentElement.getBoundingClientRect().height>=560"),'proxy popup is too short'
        assert driver.execute_script("return document.getElementById('edit-advanced-proxy-input').value").endswith(':'+str(server.server_port))
        assert driver.execute_script("return document.getElementById('cfx-mac-proxy-password').type")=='password'
        driver.find_element('id','cfx-mac-proxy-show-password').click()
        assert driver.execute_script("return document.getElementById('cfx-mac-proxy-password').type")=='text'
        driver.execute_script("document.getElementById('edit-advanced-proxy-input').value=arguments[0];",'http://localhost:'+str(server.server_port))
        driver.find_element('id','submit-advanced-proxy').click()
        WebDriverWait(driver,10).until(lambda _:'Authentication preserved' in driver.find_element('id','cfx-mac-proxy-auth-status').text)
        assert driver.execute_script('return window.originalSaveCalled') is False
        driver.refresh()
        WebDriverWait(driver,10).until(lambda _:driver.execute_script("return document.getElementById('cfx-mac-proxy-password')?.value === arguments[0]",password))
        assert driver.execute_script("return document.getElementById('edit-advanced-proxy-input').value").endswith(':'+str(server.server_port))
        assert driver.execute_script("return document.getElementById('cfx-mac-proxy-password').type")=='password'
        driver.set_context('chrome')
        driver.execute_script("gBrowser.selectedTab=gBrowser.addTab('https://api.ipify.org/?auth-fixture',{userContextId:arguments[0],triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});",ident)
        expected='Basic '+base64.b64encode(('customer-city-chicago:'+password).encode()).decode()
        WebDriverWait(driver,15).until(lambda _:expected in server.auth)
        # Reopen and explicitly clear auth; this must remove the saved header.
        driver.set_context('content');driver.switch_to.window(driver.window_handles[-1]);driver.get(url)
        WebDriverWait(driver,10).until(lambda _:driver.execute_script("return document.getElementById('cfx-mac-proxy-password')?.value === arguments[0]",password))
        driver.execute_script("document.getElementById('cfx-mac-proxy-username').value='';document.getElementById('cfx-mac-proxy-password').value='';")
        driver.find_element('id','submit-advanced-proxy').click()
        WebDriverWait(driver,10).until(lambda _:'No authentication' in driver.find_element('id','cfx-mac-proxy-auth-status').text)
        driver.refresh()
        WebDriverWait(driver,10).until(lambda _:'Editing proxy authentication' in driver.find_element('id','cfx-mac-proxy-auth-status').text)
        assert driver.execute_script("return document.getElementById('cfx-mac-proxy-password').value") == ''
        print(json.dumps({'passed':True,'fields':'masked with show-password','roundtrip':'preserved across server edit and reopen','wire_auth':'verified with special characters','clear_auth':'explicit removal works'}))
    except Exception:
        driver.set_context('chrome')
        print('proxy requests:',len(server.auth),'authenticated:',sum(bool(a) for a in server.auth))
        print(driver.execute_script("return Services.console.getMessageArray().map(m=>m.message).filter(m=>/AUTHFIX|ContainerProxy|Window protocol|actor|SyntaxError/.test(m)).slice(-12);"))
        raise
    finally:
        driver.quit();server.shutdown()
