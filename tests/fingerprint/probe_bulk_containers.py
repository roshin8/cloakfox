"""Bulk container UI/bridge checks, exclusively in a disposable native profile."""
import json,os,tempfile,zipfile
from pathlib import Path
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from probe_daily_defaults import launch
with tempfile.TemporaryDirectory(prefix='cloakfox-bulk-test-') as tmp:
    root=Path(tmp);profile=root/'profile';profile.mkdir();addon=root/'addon';addon.mkdir()
    (addon/'manifest.json').write_text(json.dumps({'manifest_version':2,'name':'Bulk container test','version':'1.0','browser_specific_settings':{'gecko':{'id':'@testpilot-containers'}},'permissions':['proxy','storage','contextualIdentities'],'background':{'scripts':['background.js']}}))
    (addon/'background.js').write_text('')
    with zipfile.ZipFile(Path(os.environ['CLOAKFOX_BIN']).parents[1]/'Resources/distribution/extensions/@testpilot-containers.xpi') as package:
        (addon/'popup.css').write_bytes(package.read('css/popup.css'))
    driver=launch(profile,root/'gecko.log',purge_caches=True)
    try:
        driver.set_script_timeout(90)
        ids=driver.execute_script("const s=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService;return ['Source','Target A','Target B','Unselected'].map(n=>s.create(n,'fingerprint','blue').userContextId);")
        rows=''.join(f'<tr data-cookie-store-id="firefox-container-{i}" data-container-id="firefox-container-{i}" tabindex="0"><td><span class="menu-text">{name}</span><span class="move-button">Move</span></td></tr>' for i,name in zip(ids,['Source','Target A','Target B','Unselected']))
        (addon/'popup.html').write_text('''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="popup.css"><div id="container-picker-panel" class="panel"><h3 class="title">Manage Containers</h3><div id="new-container-div"><button id="new-container">New Container</button></div><div class="scrollable"><table id="picker-identities-list">ROWS</table></div></div><div id="advanced-proxy-settings-panel" class="hide"><form class="advanced-proxy-panel-content"><input id="edit-advanced-proxy-input"><button id="submit-advanced-proxy"></button></form></div>'''.replace('ROWS',rows))
        driver.install_addon(str(addon),temporary=True)
        seed=driver.execute_async_script("const done=arguments[arguments.length-1];ChromeUtils.importESModule('resource:///modules/CloakfoxContainerProxyEditor.sys.mjs').saveMACProxy({cookieStoreId:'firefox-container-'+arguments[0],name:'Source',server:'http://127.0.0.1:7777',username:'fixture-user',password:'special=password'}).then(done,e=>done({error:String(e)}));",ids[0])
        assert 'error' not in seed,seed
        driver.execute_script("ChromeUtils.importESModule('resource:///modules/CloakfoxContainerProxyEditor.sys.mjs').initContainerProxyEditor();")
        url=driver.execute_script("return ChromeUtils.importESModule('resource://gre/modules/ExtensionParent.sys.mjs').ExtensionParent.GlobalManager.getExtension('@testpilot-containers').baseURI.resolve('popup.html');")
        driver.set_context('content');driver.get(url)
        wait=WebDriverWait(driver,15)
        wait.until(lambda _:driver.execute_script("return !!document.getElementById('cfx-bulk-select');"))
        driver.find_element('id','cfx-bulk-select').click()
        def row(index):
            return driver.find_element('css selector',f'tr[data-cookie-store-id="firefox-container-{ids[index]}"]')
        def shift_click(index):
            ActionChains(driver).key_down(Keys.SHIFT).click(row(index)).key_up(Keys.SHIFT).perform()
        row(0).click()
        shift_click(3)
        assert driver.execute_script("return document.querySelectorAll('tr[aria-checked=true]').length") == 4, 'Shift-click must select the intervening rows'
        driver.find_element('id','cfx-bulk-clear').click()
        row(3).click()
        shift_click(0)
        assert driver.execute_script("return document.querySelectorAll('tr[aria-checked=true]').length") == 4, 'reverse ranges must work'
        row(1).click()
        shift_click(3)
        assert driver.execute_script("return document.querySelectorAll('tr[aria-checked=true]').length") == 1, 'a deselected anchor must clear its range'
        driver.find_element('id','cfx-bulk-clear').click()
        shift_click(2)
        assert driver.execute_script("return document.querySelectorAll('tr[aria-checked=true]').length") == 1, 'Clear must reset the range anchor'
        driver.find_element('id','cfx-bulk-clear').click()
        for i in ids[1:3]:driver.find_element('css selector',f'tr[data-cookie-store-id="firefox-container-{i}"]').click()
        assert driver.execute_script("return document.querySelectorAll('tr[aria-checked=true]').length") == 2
        driver.find_element('id','cfx-bulk-apply-open').click()
        wait.until(lambda _:driver.execute_script("return document.getElementById('cfx-bulk-source').options.length>1;"))
        driver.execute_script("document.getElementById('cfx-bulk-source').value=arguments[0];",str(ids[0]))
        driver.find_element('id','cfx-bulk-apply').click()
        wait.until(lambda _:'Proxy applied to 2' in driver.execute_script("return document.getElementById('cfx-bulk-tools').textContent"))
        driver.set_context('chrome')
        result=driver.execute_async_script("const done=arguments[arguments.length-1];ChromeUtils.importESModule('resource:///modules/CloakfoxContainerProxyEditor.sys.mjs').macProxyStorage().then(async s=>done((await s.db.get('proxifiedContainersKey')).proxifiedContainersKey));")
        source=next(r['proxy'] for r in result if r['cookieStoreId']==f'firefox-container-{ids[0]}')
        copied=[next(r['proxy'] for r in result if r['cookieStoreId']==f'firefox-container-{i}') for i in ids[1:3]]
        assert all(p['proxyAuthorizationHeader']==source['proxyAuthorizationHeader'] for p in copied)
        assert len({p['connectionIsolationKey'] for p in [source]+copied})==3
        assert not any(r['cookieStoreId']==f'firefox-container-{ids[3]}' for r in result)
        driver.set_context('content')
        driver.find_element('id','cfx-bulk-remove').click()
        wait.until(lambda _:'Removed proxy assignments from 2' in driver.execute_script("return document.getElementById('cfx-bulk-tools').textContent"))
        driver.find_element('id','cfx-bulk-delete-open').click()
        wait.until(lambda _:'Target A' in driver.find_element('id','cfx-bulk-delete-names').text)
        assert 'Target B' in driver.find_element('id','cfx-bulk-delete-names').text
        driver.set_context('chrome')
        assert driver.execute_script("const s=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService;return arguments[0].every(id=>!!s.getPublicIdentityFromId(id));",ids)
        driver.set_context('content')
        driver.find_element('id','cfx-bulk-delete-confirm').click()
        wait.until(lambda _:'Deleted 2 containers.' in driver.execute_script("return document.getElementById('cfx-bulk-tools').textContent"))
        driver.set_context('chrome')
        existing=driver.execute_script("const s=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService;return arguments[0].map(id=>!!s.getPublicIdentityFromId(id));",ids)
        assert existing==[True,False,False,True],existing
        print(json.dumps({'passed':True,'selection':'two target containers','proxy':'auth copied and connections isolated','unselected':'unchanged','remove':'selected assignments only','delete':'review first, selected containers only'}))
    except Exception:
        driver.set_context('chrome')
        print(driver.execute_script("return Services.console.getMessageArray().map(m=>m.message).filter(m=>/Bulk|ContainerProxy|SyntaxError/.test(m)).slice(-10);"))
        raise
    finally:driver.quit()
