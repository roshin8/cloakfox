"""Exercise category navigation, search, drafts and container context in the app."""
import json
import tempfile
from pathlib import Path
from selenium.webdriver.support.ui import WebDriverWait
from probe_daily_defaults import launch

def main():
    with tempfile.TemporaryDirectory(prefix='cloakfox-navigation-') as temp:
        profile=Path(temp)/'profile';profile.mkdir()
        driver=launch(profile,Path(temp)/'gecko.log')
        try:
            driver.set_context('content');driver.get('about:cloakfox')
            WebDriverWait(driver,15).until(lambda d:d.execute_script("return !!document.querySelector('.settings-sidebar')"))
            assert driver.execute_script("return [...document.querySelectorAll('.advanced-fields')].length > 0 && [...document.querySelectorAll('.advanced-fields')].every(el=>el.open)")
            driver.execute_script("document.getElementById('cfx-collapse-advanced').click()")
            assert driver.execute_script("return [...document.querySelectorAll('.advanced-fields')].every(el=>!el.open)")
            driver.refresh()
            WebDriverWait(driver,10).until(lambda d:d.execute_script("return !!document.getElementById('cfx-collapse-advanced')"))
            assert driver.execute_script("return document.getElementById('cfx-collapse-advanced').checked && [...document.querySelectorAll('.advanced-fields')].every(el=>!el.open)")
            driver.execute_script("document.getElementById('cfx-collapse-advanced').click()")
            assert driver.execute_script("return [...document.querySelectorAll('.advanced-fields')].every(el=>el.open && getComputedStyle(el).borderTopWidth==='0px')")
            def category(name):
                driver.execute_script("document.querySelector('[data-category=\"'+arguments[0]+'\"]').click()",name)
            assert driver.execute_script("return document.querySelectorAll('.settings-sidebar nav a').length")==11
            assert driver.execute_script("return !document.querySelector('.hero').hidden && document.getElementById('cfx-proxy-manager').hidden")
            container=driver.execute_script("return document.getElementById('cfx-container-select').value")
            category('region')
            assert not driver.find_element('id','cfx-chromium-status').is_displayed(), 'Chromium status must stay inside its settings section'
            driver.execute_script("document.getElementById('cfx-region-locale').value='fr-CA'")
            def appearance(layout, theme):
                driver.execute_script("for(const [id,value] of [['cfx-layout',arguments[0]],['cfx-theme',arguments[1]]]){const s=document.getElementById(id);s.value=value;s.dispatchEvent(new Event('change'));}",layout,theme)
            appearance('grouped','dark')
            assert driver.execute_script("return document.body.dataset.layout === 'grouped' && document.documentElement.dataset.theme === 'dark'")
            driver.execute_script("document.getElementById('cfx-region-settings').closest('.settings-group').open=false")
            appearance('console','light')
            assert driver.execute_script("return document.getElementById('cfx-region-settings').getBoundingClientRect().height > 0")
            category('connections');category('region')
            assert driver.execute_script("return document.getElementById('cfx-region-locale').value")=='fr-CA'
            assert driver.execute_script("return document.getElementById('cfx-container-select').value")==container
            driver.execute_script("const s=document.getElementById('cfx-settings-search');s.value='saved proxies';s.dispatchEvent(new Event('input'))")
            assert driver.execute_script("return !document.getElementById('cfx-proxy-manager').hidden")
            assert not driver.find_element('id','cfx-chromium-status').is_displayed(), 'Unrelated search must hide Chromium status'
            driver.execute_script("const s=document.getElementById('cfx-settings-search');s.value='zzzz-no-setting';s.dispatchEvent(new Event('input'))")
            assert driver.execute_script("return !document.querySelector('.settings-empty').hidden")
            category('display')
            assert driver.execute_script("const d=document.querySelector('#grp-screen details');d.open=true;return [...d.querySelectorAll('.spoof-row')].every(r=>getComputedStyle(r).display==='grid' && r.getBoundingClientRect().width>d.getBoundingClientRect().width*.9)")
            driver.execute_script("location.hash='cfx-proxy-manager'")
            WebDriverWait(driver,5).until(lambda d:d.execute_script("return document.querySelector('[data-category=connections]').getAttribute('aria-current')==='page'"))
            assert driver.execute_script("return document.getElementById('cfx-settings-search').value")==''
            appearance('grouped','dark')
            driver.refresh()
            WebDriverWait(driver,10).until(lambda d:d.execute_script("return document.body.dataset.layout === 'grouped'"))
            assert driver.execute_script("return document.documentElement.dataset.theme") == 'dark'
            category('display')
            assert driver.execute_script("return !document.getElementById('sec-display').hidden && !document.getElementById('sec-graphics').hidden")
            appearance('console','light')
            driver.find_element('css selector', '[data-panel="sec-graphics"]').click()
            assert driver.execute_script("return document.getElementById('sec-display').hidden && !document.getElementById('sec-graphics').hidden")
            for layout in ('console','grouped'):
                appearance(layout,'light')
                for name in ('region','connections','containers','media','privacy','display'):
                    category(name)
                    assert not driver.find_element('id','cfx-chromium-status').is_displayed(), (layout,name)
            category('display')
            for width in (1280,848,600):
                driver.set_window_size(width,1000)
                assert driver.execute_script("return document.documentElement.scrollWidth <= innerWidth"), f'overflow at {width}'
            driver.set_window_size(1280,1000)
            category('identity')
            driver.set_context('chrome')
            driver.save_screenshot(str(Path(__file__).resolve().parents[2]/'docs/font-ui-fix/layout-console-light.png'))
            driver.set_context('content')
            appearance('grouped','dark')
            driver.refresh()
            WebDriverWait(driver,10).until(lambda d:d.execute_script("return document.body.dataset.layout === 'grouped' && document.documentElement.dataset.theme === 'dark'"))
            driver.set_context('chrome')
            driver.save_screenshot(str(Path(__file__).resolve().parents[2]/'docs/font-ui-fix/layout-grouped-dark.png'))
            driver.set_context('content')
            print(json.dumps({'ok':True,'categories':11,'draftRetained':True,'searchAndEmptyState':True,'deepLink':True,'advancedLayout':True,'layoutAndThemePersist':True,'layoutDraftRetained':True,'tabs':True,'responsiveWidths':[1280,848,600]}))
        finally:driver.quit()

if __name__=='__main__':main()
