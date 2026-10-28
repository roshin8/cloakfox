"""Exercise native quick creation and persistence using only a disposable profile."""
import json,tempfile
from pathlib import Path
from selenium.webdriver.support.ui import WebDriverWait
from probe_daily_defaults import launch

with tempfile.TemporaryDirectory(prefix='cloakfox-quick-container-') as temp:
    root=Path(temp);profile=root/'profile';profile.mkdir()
    driver=launch(profile,root/'first.log')
    created=[]
    try:
        wait=WebDriverWait(driver,15)
        before=driver.execute_script('return gBrowser.tabs.length;')
        driver.execute_script("ChromeUtils.importESModule('resource:///modules/CloakfoxQuickContainer.sys.mjs').initQuickContainerButton();")
        assert driver.execute_script("return !!document.getElementById('cloakfox-quick-container-button');")
        driver.execute_script("const {CustomizableUI:ui}=ChromeUtils.importESModule('moz-src:///browser/components/customizableui/CustomizableUI.sys.mjs');const id='_c607c8df-14a7-4f28-894f-29e8722976af_-browser-action';ui.createWidget({id});ui.addWidgetToArea(id,ui.AREA_TABSTRIP);")
        assert driver.execute_script("return !ChromeUtils.importESModule('moz-src:///browser/components/customizableui/CustomizableUI.sys.mjs').CustomizableUI.getPlacementOfWidget('_c607c8df-14a7-4f28-894f-29e8722976af_-browser-action');")
        for iteration in range(2):
            if iteration == 0:
                driver.find_element('id','cloakfox-quick-container-button').click()
            else:
                driver.execute_async_script("const done=arguments[arguments.length-1];ChromeUtils.importESModule('chrome://browser/content/usercontext/ContainerCreationPanel.mjs').ContainerCreationPanel.open(window).then(()=>done(true),e=>done(e.message));")
                wait.until(lambda _:driver.execute_script("return document.getElementById('containerCreation-panel').state==='open';"))
                assert driver.execute_script("return !!document.getElementById('containerCreation-auto');"), 'automatic option must be a checkbox'
                assert driver.execute_script("const a=document.getElementById('containerCreation-auto'),f=document.querySelector('.container-editor'),field=f.querySelector('moz-input-text');return Math.abs(a.getBoundingClientRect().left-field.getBoundingClientRect().left)<1;"), 'checkbox must align with the Name field'
                assert driver.execute_script("return document.getElementById('containerCreation-create-button').disabled;")
                driver.execute_script("const c=document.getElementById('containerCreation-auto');c.checked=true;c.dispatchEvent(new Event('change',{bubbles:true}));")
                assert driver.execute_script("return !document.getElementById('containerCreation-create-button').disabled && document.querySelector('.container-editor').inert;")
                driver.execute_script("const c=document.getElementById('containerCreation-auto');c.checked=false;c.dispatchEvent(new Event('change',{bubbles:true}));")
                assert driver.execute_script("return document.getElementById('containerCreation-create-button').disabled && !document.querySelector('.container-editor').inert;")
                driver.execute_script("const c=document.getElementById('containerCreation-auto');c.checked=true;c.dispatchEvent(new Event('change',{bubbles:true}));document.getElementById('containerCreation-create-button').click();")
            wait.until(lambda _:driver.execute_script('return gBrowser.tabs.length;')==before+len(created)+1)
            item=driver.execute_script("const cis=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService;const id=Number(gBrowser.selectedTab.getAttribute('usercontextid'));return {...cis.getPublicIdentityFromId(id),tabId:id};")
            assert item['name'].startswith('Container #') and item['public'],item
            assert item['userContextId']==item['tabId']>0,item
            created.append(item)
        assert len({i['name'] for i in created})==2,created
        assert len({i['color'] for i in created})==2,created
    except Exception:
        print(driver.execute_script("return Services.console.getMessageArray().map(m=>m.message).filter(m=>/QuickContainer|TypeError|ReferenceError/.test(m)).slice(-10);"));raise
    finally:driver.quit()
    driver=launch(profile,root/'second.log')
    try:
        for item in created:
            assert driver.execute_script("const cis=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService;return cis.getPublicIdentityFromId(arguments[0])?.name;",item['userContextId'])==item['name']
        print(json.dumps({'passed':True,'created':[{'name':i['name'],'color':i['color']} for i in created],'tabs':'opened and selected in their own containers','permanent':'verified after restarting disposable profile'}))
    finally:driver.quit()
