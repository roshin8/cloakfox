"""Fresh constrained persona generation, persistence, override policy and isolation."""
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from screen_management_fixture import ScreenManagementFixture

def main():
    with ScreenManagementFixture() as f:
        d=f.driver
        def load():
            d.get('about:cloakfox')
            WebDriverWait(d,15).until(lambda d:len(Select(d.find_element(By.ID,'cfx-persona-hardware')).options)>1)
            d.execute_script('document.documentElement.style.scrollBehavior="auto"')
        def cfg(id=0):
            return f.chrome('return JSON.parse(Services.prefs.getStringPref("cloakfox.s.cloak_cfg_"+arguments[0]))',id)
        def choose(id,value):
            el=d.find_element(By.ID,id)
            d.execute_script('arguments[0].scrollIntoView({block:"center"})',el)
            Select(el).select_by_value(value)
        def generate():
            el=d.find_element(By.ID,'cfx-regenerate')
            d.execute_script('arguments[0].scrollIntoView({block:"center"})',el);el.click()
            assert 'New persona saved' in d.find_element(By.ID,'cfx-generation-status').text
        load();before=cfg()
        choose('cfx-persona-os','windows');choose('cfx-persona-hardware','nvidia')
        assert cfg()==before, 'Choosing filters applied them before generation'
        f.chrome('ChromeUtils.importESModule("resource:///modules/CloakfoxOverrides.sys.mjs").setOverride(0,"navigator.hardwareConcurrency",41)')
        generate();first=cfg()
        assert 'Windows' in first['navigator.userAgent']
        assert 'NVIDIA' in first['webGl:renderer'] or 'GeForce' in first['webGl:renderer']
        assert first['navigator.hardwareConcurrency']==41
        seed=f.chrome('return Services.prefs.getStringPref("cloakfox.container.0.math_seed")')
        generate();second=cfg()
        assert f.chrome('return Services.prefs.getStringPref("cloakfox.container.0.math_seed")')!=seed
        assert second!=first
        assert 'Windows' in second['navigator.userAgent'] and second['navigator.hardwareConcurrency']==41
        d=f.restart();load()
        assert cfg()==second, 'Restart changed generated persona'
        assert Select(d.find_element(By.ID,'cfx-persona-os')).first_selected_option.get_attribute('value')=='windows'
        assert Select(d.find_element(By.ID,'cfx-persona-hardware')).first_selected_option.get_attribute('value')=='nvidia'
        choose('cfx-persona-os','macos');choose('cfx-persona-hardware','apple')
        clear=d.find_element(By.ID,'cfx-generation-clear-overrides')
        d.execute_script('arguments[0].scrollIntoView({block:"center"})',clear);clear.click()
        generate();mac=cfg()
        assert mac['navigator.platform']=='MacIntel' and 'Apple' in mac['webGl:renderer']
        assert not f.chrome('return Services.prefs.prefHasUserValue("cloakfox.container.0.override.navigator.hardwareConcurrency")')
        assert mac['navigator.hardwareConcurrency']!=41
        choose('cfx-container-select','2');choose('cfx-persona-os','linux')
        generate();assert 'Linux' in cfg(2)['navigator.userAgent']
        assert cfg()==mac, 'Generation changed another container'
        choose('cfx-container-select','0')
        assert Select(d.find_element(By.ID,'cfx-persona-os')).first_selected_option.get_attribute('value')=='macos'
        print('PERSONA GENERATION PASS: staged filters, OS/GPU matches, fresh seeds, override retention/clearing, restart stability, container isolation')
if __name__=='__main__':main()
