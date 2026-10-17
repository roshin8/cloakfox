"""Fresh constrained persona generation, persistence, override policy and isolation."""
import json
from click_evidence import click_with_evidence
from selenium.common.exceptions import ElementNotInteractableException
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
            # Session timing salts rotate at launch; compare every persistent identity field.
            return f.chrome('const cfg=JSON.parse(Services.prefs.getStringPref("cloakfox.s.cloak_cfg_"+arguments[0]));delete cfg["timing:session_key_hi"];delete cfg["timing:session_key_lo"];return cfg',id)
        def reveal(id):
            d.execute_script('location.hash=arguments[0]',id)
            WebDriverWait(d,5).until(lambda d:d.find_element(By.ID,id).is_displayed())
        def choose(id,value):
            if id != 'cfx-container-select':
                reveal('cfx-persona-panel')
            el=d.find_element(By.ID,id)
            d.execute_script('arguments[0].scrollIntoView({block:"center"})',el)
            if el.get_attribute('id') == 'cfx-persona-filter' and value != 'all':
                Select(el).select_by_visible_text(value)
            else:
                Select(el).select_by_value(value)
        generation_attempt = 0
        def generate():
            nonlocal generation_attempt
            generation_attempt += 1
            reveal('cfx-persona-panel')
            el=d.find_element(By.ID,'cfx-generate-new')
            d.execute_script('arguments[0].scrollIntoView({block:"center"})',el)
            click_with_evidence(d,el,f.report_path,f"generate-{generation_attempt}")
            WebDriverWait(d,15).until(lambda d: not d.find_element(By.ID,'cfx-generate-new').get_attribute('aria-busy'))
            assert 'Generated and applied' in d.find_element(By.ID,'cfx-identity-status').text
        load();before=cfg()
        choose('cfx-persona-filter','Windows');choose('cfx-persona-hardware','nvidia')
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
        assert Select(d.find_element(By.ID,'cfx-persona-filter')).first_selected_option.get_attribute('value')=='Windows'
        assert Select(d.find_element(By.ID,'cfx-persona-hardware')).first_selected_option.get_attribute('value')=='nvidia'
        choose('cfx-persona-filter','macOS');choose('cfx-persona-hardware','apple')
        reveal('cfx-persona-panel')
        clear=d.find_element(By.ID,'cfx-clear-overrides')
        d.execute_script('arguments[0].scrollIntoView({block:"center"})',clear)
        try:
            clear.click()
        except ElementNotInteractableException:
            diagnostic=d.execute_script("""const el=arguments[0],r=el.getBoundingClientRect();
              const ancestors=[];for(let n=el;n;n=n.parentElement){const s=getComputedStyle(n);
                ancestors.push({tag:n.tagName,id:n.id,hidden:n.hidden,open:n.open,
                  display:s.display,visibility:s.visibility,overflow:s.overflow})}
              return {hash:location.hash,container:document.getElementById('cfx-container-select').value,
                overrideText:document.getElementById('cfx-override-count').textContent,
                rect:r.toJSON(),viewport:[innerWidth,innerHeight],scroll:[scrollX,scrollY],
                top:document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.id,ancestors};""",clear)
            diagnostic['overridePersisted']=f.chrome('return Services.prefs.prefHasUserValue("cloakfox.container.0.override.navigator.hardwareConcurrency")')
            (f.report_path/'clear-overrides-diagnostic.json').write_text(json.dumps(diagnostic,indent=2))
            d.save_screenshot(str(f.report_path/'clear-overrides-diagnostic.png'))
            print('Clear overrides diagnostic:',json.dumps(diagnostic),flush=True)
            raise
        # Clearing overrides refreshes the saved controls; stage the intended filters again.
        choose('cfx-persona-filter','macOS');choose('cfx-persona-hardware','apple')
        generate();mac=cfg()
        assert mac['navigator.platform']=='MacIntel' and 'Apple' in mac['webGl:renderer']
        assert not f.chrome('return Services.prefs.prefHasUserValue("cloakfox.container.0.override.navigator.hardwareConcurrency")')
        assert mac['navigator.hardwareConcurrency']!=41
        choose('cfx-container-select','2');choose('cfx-persona-filter','Linux')
        generate();assert 'Linux' in cfg(2)['navigator.userAgent']
        assert cfg()==mac, 'Generation changed another container'
        choose('cfx-container-select','0')
        assert Select(d.find_element(By.ID,'cfx-persona-filter')).first_selected_option.get_attribute('value')=='macOS'
        print('PERSONA GENERATION PASS: staged filters, OS/GPU matches, fresh seeds, override retention/clearing, restart stability, container isolation')
if __name__=='__main__':main()
