"""Exercise checkbox tab closing with disposable tabs, container cookies and login."""
import json,os,tempfile,zipfile
from pathlib import Path
from selenium.webdriver.support.ui import WebDriverWait
from probe_daily_defaults import launch
with tempfile.TemporaryDirectory(prefix='cloakfox-tab-selection-') as tmp:
    root=Path(tmp);profile=root/'profile';profile.mkdir();addon=root/'addon';addon.mkdir()
    (addon/'manifest.json').write_text(json.dumps({'manifest_version':2,'name':'Tab selection fixture','version':'1.0','browser_specific_settings':{'gecko':{'id':'@testpilot-containers'}},'permissions':['tabs','contextualIdentities'],'background':{'scripts':['background.js']}}))
    (addon/'background.js').write_text('')
    with zipfile.ZipFile(Path(os.environ['CLOAKFOX_BIN']).parents[1]/'Resources/distribution/extensions/@testpilot-containers.xpi') as package:(addon/'popup.css').write_bytes(package.read('css/popup.css'))
    driver=launch(profile,root/'gecko.log',purge_caches=True)
    try:
        driver.set_script_timeout(30)
        ids=driver.execute_script("const s=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService;return ['Tab test','Other container'].map(n=>s.create(n,'fingerprint','blue').userContextId);")
        driver.install_addon(str(addon),temporary=True)
        tab_ids=driver.execute_script("const ext=ChromeUtils.importESModule('resource://gre/modules/ExtensionParent.sys.mjs').ExtensionParent.GlobalManager.getExtension('@testpilot-containers');window.__tabSelectionFixture=[arguments[0],arguments[0],arguments[0],arguments[1]].map(id=>gBrowser.addTab('about:blank',{userContextId:id,triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()}));return window.__tabSelectionFixture.map(t=>ext.tabManager.getWrapper(t).id);",*ids)
        driver.execute_script("return Services.cookies.add('keep.example','/','session','fixture',true,true,false,Date.now()+3600000,{userContextId:arguments[0]},Ci.nsICookie.SAMESITE_NONE,Ci.nsICookie.SCHEME_HTTPS).errorString;",ids[0])
        assert driver.execute_script("return Services.cookies.getCookiesFromHost('keep.example',{userContextId:arguments[0]}).some(c=>c.name==='session'&&c.value==='fixture');",ids[0]),'fixture cookie was not created'
        driver.execute_async_script("const done=arguments[arguments.length-1];const login=Cc['@mozilla.org/login-manager/loginInfo;1'].createInstance(Ci.nsILoginInfo);login.init('https://keep.example','https://keep.example',null,'fixture-user','fixture-password','','');Services.logins.addLoginAsync(login).then(()=>done(true));")
        rows=''.join(f'<tr class="menu-item" tabindex="0"><td><span class="menu-text">Test tab {i+1}</span><img id="{id}" class="trash-button"></td></tr>' for i,id in enumerate(tab_ids[:3]))
        (addon/'popup.html').write_text('''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="popup.css"><div id="container-info-panel" class="panel"><h3 class="title" id="container-info-title">Tab test</h3><div class="sub-header-wrapper">Open tabs</div><div class="scrollable"><table id="container-info-table">ROWS</table></div></div><div id="advanced-proxy-settings-panel" class="hide"><form class="advanced-proxy-panel-content"><input id="edit-advanced-proxy-input"><button id="submit-advanced-proxy"></button></form></div>'''.replace('ROWS',rows))
        driver.install_addon(str(addon),temporary=True)  # Refresh the packaged fixture after tab IDs are known.
        url=driver.execute_script("ChromeUtils.importESModule('resource:///modules/CloakfoxContainerProxyEditor.sys.mjs').initContainerProxyEditor();return ChromeUtils.importESModule('resource://gre/modules/ExtensionParent.sys.mjs').ExtensionParent.GlobalManager.getExtension('@testpilot-containers').baseURI.resolve('popup.html');")
        driver.set_context('content');driver.get(url);wait=WebDriverWait(driver,15)
        wait.until(lambda _:driver.execute_script("return !!document.getElementById('cfx-tab-select')"))
        driver.find_element('id','cfx-tab-select').click()
        driver.find_element('id','cfx-tab-all').click()
        assert driver.execute_script("return document.querySelectorAll('#container-info-table tr[aria-checked=true]').length")==3
        driver.find_element('css selector',f'tr:has(img[id="{tab_ids[2]}"])').click()
        assert driver.execute_script("return document.getElementById('cfx-tab-all').indeterminate")
        driver.find_element('id','cfx-tab-close').click()
        wait.until(lambda _:'Closed 2 of 2' in driver.find_element('id','cfx-tab-status').text)
        driver.set_context('chrome')
        live=driver.execute_script('return window.__tabSelectionFixture.map(t=>t.isConnected&&!t.closing);')
        assert live==[False,False,True,True],live
        assert driver.execute_script("return Services.cookies.getCookiesFromHost('keep.example',{userContextId:arguments[0]}).some(c=>c.name==='session'&&c.value==='fixture');",ids[0])
        assert driver.execute_async_script("const done=arguments[arguments.length-1];Services.logins.getAllLogins().then(items=>done(items.some(l=>l.hostname==='https://keep.example'&&l.username==='fixture-user')));")
        assert driver.execute_script("return !!ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService.getPublicIdentityFromId(arguments[0]);",ids[0])
        print(json.dumps({'passed':True,'select_all':'checked and indeterminate states','closed':'two selected tabs only','unselected':'same-container tab and other container retained','preserved':'container, session cookie and saved login'}))
    except Exception:
        driver.set_context('chrome');print(driver.execute_script("return Services.console.getMessageArray().map(m=>m.message).filter(m=>/ContainerTabs|ContainerProxy|TypeError|SyntaxError/.test(m)).slice(-10);"));raise
    finally:driver.quit()
