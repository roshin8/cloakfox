"""Validate warning acknowledgement/cancellation with an isolated profile."""
from screen_management_fixture import ScreenManagementFixture
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select,WebDriverWait

def main():
    with ScreenManagementFixture() as f:
        d=f.driver
        def load():
            d.get('about:cloakfox')
            WebDriverWait(d,15).until(lambda d:d.find_elements(By.ID,'cfx-consistency'))
        def cfg():return f.chrome('return JSON.parse(Services.prefs.getStringPref("cloakfox.s.cloak_cfg_0"))')
        load()
        Select(d.find_element(By.ID,'cfx-persona-os')).select_by_value('windows')
        Select(d.find_element(By.ID,'cfx-persona-hardware')).select_by_value('nvidia')
        d.find_element(By.ID,'cfx-generation-clear-overrides').click()
        d.find_element(By.ID,'cfx-regenerate').click()
        WebDriverWait(d,10).until(lambda d:'New persona saved' in d.find_element(By.ID,'cfx-generation-status').text)
        before=cfg()
        assert 'No known configuration conflicts' in d.find_element(By.ID,'cfx-consistency').get_attribute('textContent')
        def edit_available_width():
            d.execute_script('document.getElementById("sec-display").open=true')
            row=d.find_element(By.CSS_SELECTOR,'.k[title="screen.availWidth"]').find_element(By.XPATH,'..')
            row.find_element(By.CSS_SELECTOR,'.v').click()
            field=row.find_element(By.CSS_SELECTOR,'.row-input');d.execute_script('arguments[0].select()',field);field.send_keys('99999\ue007')
            alert=WebDriverWait(d,5).until(lambda d:d.switch_to.alert)
            assert 'Available screen width' in alert.text
            return alert
        edit_available_width().dismiss()
        WebDriverWait(d,5).until(lambda d:not d.find_elements(By.CSS_SELECTOR,".row-input"))
        assert cfg()==before,'Cancel changed the saved persona'
        assert not f.chrome('return Services.prefs.prefHasUserValue("cloakfox.container.0.override.screen.availWidth")')
        edit_available_width().accept()
        WebDriverWait(d,5).until(lambda _:cfg()['screen.availWidth']==99999)
        assert 'Available screen width' in d.find_element(By.ID,'cfx-consistency').get_attribute('textContent')
        assert cfg()['screen.width']==before['screen.width'],'Checker silently rewrote another field'
        d=f.restart();load()
        assert 'Available screen width' in d.find_element(By.ID,'cfx-consistency').get_attribute('textContent')
        print('PERSONA CONSISTENCY SETTINGS PASS: coherent generation, cancellation, explicit acceptance, persistence, no silent rewrites')
if __name__=='__main__':main()
