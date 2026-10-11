"""Smoke-test actual about:cloakfox controls and release-status disclosures."""
from pathlib import Path
import tempfile
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from probe_daily_defaults import launch

def main():
    with tempfile.TemporaryDirectory(prefix='cloakfox-settings-ui-') as temp:
        profile=Path(temp)/'profile'; profile.mkdir()
        driver=launch(profile,Path(temp)/'gecko.log')
        try:
            driver.set_context('content'); driver.get('about:cloakfox')
            wait=WebDriverWait(driver,15)
            def category(name):
                wait.until(lambda d: d.find_elements(By.CSS_SELECTOR,'.settings-sidebar nav a'))
                driver.execute_script("document.querySelector('[data-category=\"'+arguments[0]+'\"]').click()",name)
            category('diagnostics')
            driver.execute_script("const layout=document.getElementById('cfx-layout');layout.value='grouped';layout.dispatchEvent(new Event('change'));")
            wait.until(lambda d: d.find_element(By.ID,'cfx-provider-readiness').text)
            wait.until(lambda d: d.find_element(By.ID,'cfx-container-workflows'))
            assert not driver.find_element(By.ID,'cfx-ip-lookup').is_selected()
            assert 'Firefox engine' in driver.find_element(By.ID,'cfx-engine-version').text
            assert 'unavailable' in driver.find_element(By.ID,'cfx-update-readiness').text
            # Exercise each new settings script: classic-script bindings must not collide.
            wait.until(lambda d: d.find_element(By.ID,'cfx-dns-save'))
            wait.until(lambda d: d.find_element(By.ID,'cfx-tracking-save'))
            category('privacy')
            assert 'Site permission grants' in driver.find_element(By.ID,'cfx-permission-settings').text
            category('workspaces')
            assert 'Create workspace' in driver.find_element(By.ID,'cfx-workspace-settings').text
            category('network')
            driver.execute_script("document.getElementById('cfx-dns-mode').value='system';document.getElementById('cfx-dns-save').click();document.getElementById('cfx-tracking-save').click();")
            wait.until(lambda d: d.find_element(By.ID,'cfx-dns-status').text.startswith('Saved'))
            wait.until(lambda d: d.find_element(By.ID,'cfx-tracking-status').text.startswith('Saved'))
            # Invoke the actual DOM click handler; spoofed geometry makes Selenium's
            # scroll-into-view hit testing unreliable in this headless smoke test.
            category('connections')
            assert driver.find_element(By.ID,'cfx-ip-check').is_displayed()
            assert not driver.find_element(By.ID,'cfx-ip-auto').is_selected()
            driver.execute_script("document.getElementById('cfx-network-apply').click()")
            wait.until(lambda d: d.find_element(By.ID,'cfx-route-status').text.startswith('Saved'))
            category('identity')
            driver.execute_script("document.querySelector('.profile-maintenance').open=true")
            assert 'Forget container data' in driver.find_element(By.ID,'cfx-forget-data').text
            category('containers')
            assert 'encrypted' in driver.find_element(By.ID,'cfx-container-workflows').text.lower()
            wait.until(lambda d: d.find_element(By.ID,'cfx-inspect-run'))
            category('region')
            driver.execute_script("""
for(const [key,value] of Object.entries({locale:'de-DE',languages:'de-DE, de',timezone:'Europe/Berlin'})) document.getElementById('cfx-region-'+key).value=value;
[...document.querySelectorAll('#cfx-region-settings button')].find(b=>b.textContent==='Save region').click();
""")
            wait.until(lambda d: not d.find_element(By.ID,'cfx-tz-select').is_enabled())
            assert driver.find_element(By.ID,'cfx-tz-current').text == 'Europe/Berlin'
            driver.execute_script("""
[...document.querySelectorAll('#cfx-region-settings button')].find(b=>b.textContent==='Use generated defaults').click();
const tz=document.getElementById('cfx-tz-select');tz.value='Asia/Tokyo';tz.dispatchEvent(new Event('change'));
""")
            assert driver.find_element(By.ID,'cfx-tz-select').is_enabled()
            driver.set_context('chrome')
            assert driver.execute_script("return JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_0')).timezone;") == 'Asia/Tokyo'
            driver.set_context('content')
            driver.set_context('chrome')
            target=driver.execute_script("""
const cis=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService;
const id=cis.create('Deep link scope','fingerprint','blue').userContextId;
Services.prefs.setBoolPref('permissions.isolateBy.userContext',true);
for(const [ucid,host] of [[0,'default-scope.test'],[id,'selected-scope.test']]) {
 const principal=Services.scriptSecurityManager.createContentPrincipal(Services.io.newURI('https://'+host),{userContextId:ucid});
 Services.perms.addFromPrincipal(principal,'camera',Services.perms.ALLOW_ACTION);
 ChromeUtils.importESModule('resource:///modules/CloakfoxTrackingProtection.sys.mjs').setBounceException(ucid,host,Date.now()+60000);
}
return id;
""")
            driver.set_context('content');driver.get('about:cloakfox?ucid='+str(target))
            wait.until(lambda d: d.find_element(By.ID,'cfx-container-select').get_attribute('value')==str(target))
            category('privacy')
            grants=driver.find_element(By.ID,'cfx-permission-settings').text
            assert 'selected-scope.test' in grants and 'default-scope.test' not in grants, grants
            category('network')
            exceptions=driver.find_element(By.ID,'cfx-tracking-exceptions').text
            assert 'selected-scope.test' in exceptions and 'default-scope.test' not in exceptions, exceptions
            print('PASS: actual settings scripts load, network save works, opt-in off, workflow and release status visible')
        finally: driver.quit()
if __name__ == '__main__': main()
