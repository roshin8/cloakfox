"""Exercise the real adjacent feature/count/origin settings, using a test profile."""
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from screen_management_fixture import ScreenManagementFixture

def main():
    with ScreenManagementFixture() as f:
        d=f.driver;d.get('about:cloakfox')
        toggle=WebDriverWait(d,15).until(lambda x:x.find_element(By.ID,'cfx-screen-management'))
        count=d.find_element(By.ID,'cfx-screen-count'); origins=d.find_element(By.ID,'cfx-screen-origins')
        assert d.execute_script('return arguments[0].closest("section")===arguments[1].closest("section")',toggle,origins)
        toggle.click(); assert f.chrome('return Services.prefs.getBoolPref("cloakfox.compat.screen_management")') is False
        toggle.click()
        from selenium.webdriver.support.ui import Select
        Select(count).select_by_value('2')
        assert f.chrome('return Services.prefs.getIntPref("cloakfox.compat.screen_management.screen_count")')==2
        origins.clear();origins.send_keys('https://app.testdome.com\nhttps://OTHER.testdome.invalid:443\nhttps://app.testdome.com')
        d.find_element(By.ID,'cfx-screen-origins-save').click()
        stored=f.chrome('return Services.prefs.getStringPref("cloakfox.compat.screen_management.origins")')
        assert json.loads(stored)==['https://app.testdome.com','https://other.testdome.invalid'],stored
        for bad in ['http://app.testdome.com','https://*.testdome.com','https://app.testdome.com/path','https://user:pass@app.testdome.com']:
            origins.clear();origins.send_keys(bad);d.find_element(By.ID,'cfx-screen-origins-save').click()
            assert f.chrome('return Services.prefs.getStringPref("cloakfox.compat.screen_management.origins")')==stored
            assert 'Line 1' in d.find_element(By.ID,'cfx-screen-origins-status').text
        origins.clear();d.find_element(By.ID,'cfx-screen-origins-save').click()
        assert f.chrome('return Services.prefs.getStringPref("cloakfox.compat.screen_management.origins")')=='[]'
        d.find_element(By.ID,'cfx-screen-origins-reset').click();d.refresh()
        assert d.find_element(By.ID,'cfx-screen-count').get_attribute('value')=='2'
        assert d.find_element(By.ID,'cfx-screen-origins').get_attribute('value')=='https://app.testdome.com'
        for value in [1,2,3,8,0,-1,9,'wrong']:
            f.set_screen_count(value); d.refresh()
            expected=str(value) if isinstance(value,int) and 1<=value<=8 else '1'
            assert d.find_element(By.ID,'cfx-screen-count').get_attribute('value')==expected
        for malformed in ['{bad', '{}', '[7]']:
            f.pref('cloakfox.compat.screen_management.origins',malformed);d.refresh()
            assert 'Could not read' in d.find_element(By.ID,'cfx-screen-origins-status').text
        f.set_screen_count(3);f.set_origins([f.origin]);d=f.restart();d.get('about:cloakfox')
        assert d.find_element(By.ID,'cfx-screen-count').get_attribute('value')=='3'
        assert d.find_element(By.ID,'cfx-screen-origins').get_attribute('value')==f.origin
        defaults=f.chrome("return [Services.prefs.getDefaultBranch('').getBoolPref('cloakfox.compat.screen_management'),Services.prefs.getDefaultBranch('').getIntPref('cloakfox.compat.screen_management.screen_count'),Services.prefs.getDefaultBranch('').getStringPref('cloakfox.compat.screen_management.origins')]")
        assert defaults == [False,1,'["https://app.testdome.com"]'],defaults
        print('SCREEN MANAGEMENT SETTINGS PASS')

if __name__=='__main__': main()
