"""Exercise restored native preset controls using a disposable browser profile."""
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from screen_management_fixture import ScreenManagementFixture

def main():
    with ScreenManagementFixture() as f:
        d=f.driver
        def load():
            d.get('about:cloakfox')
            WebDriverWait(d,15).until(lambda d:d.find_elements(By.ID,'cfx-browser-preset'))
            d.execute_script('document.documentElement.style.scrollBehavior="auto"')
        def choose(control, value, section=None):
            if section:
                d.execute_script('document.getElementById(arguments[0]).open=true',section)
            el=d.find_element(By.ID,control)
            d.execute_script('arguments[0].scrollIntoView({block:"center"})',el)
            Select(el).select_by_value(value)
        def cfg():
            return f.chrome('return JSON.parse(Services.prefs.getStringPref("cloakfox.s.cloak_cfg_0"))')
        load()
        assert len(Select(d.find_element(By.ID,'cfx-browser-preset')).options)==117
        assert len(Select(d.find_element(By.ID,'cfx-persona-os')).options)==4
        choose('cfx-browser-preset','win10-firefox-123')
        assert not d.find_element(By.ID,'sec-screen-management').is_displayed(), 'Firefox must hide Chromium compatibility'
        choose('cfx-browser-preset','win10-chrome-122')
        assert d.find_element(By.ID,'sec-screen-management').is_displayed()
        assert d.execute_script('return document.getElementById("sec-screen-management").closest("details").id')=='sec-identity'
        count=d.find_element(By.ID,'cfx-screen-count')
        Select(count).select_by_value('2')
        choose('cfx-browser-preset','win10-firefox-123')
        assert not d.find_element(By.ID,'sec-screen-management').is_displayed()
        choose('cfx-browser-preset','win10-chrome-122')
        assert Select(d.find_element(By.ID,'cfx-screen-count')).first_selected_option.get_attribute('value')=='2'
        assert 'Enabled' in d.find_element(By.ID,'cfx-chromium-status').text
        toggle=d.find_element(By.ID,'cfx-screen-management')
        d.execute_script('arguments[0].scrollIntoView({block:"center"})',toggle);toggle.click()
        assert 'toggle' in d.find_element(By.ID,'cfx-chromium-status').text
        toggle.click()
        choose('cfx-browser-preset','win10-chrome-122')
        state=cfg()
        assert 'Chrome/122.' in state['navigator.userAgent'],state['navigator.userAgent']
        assert state['headers.User-Agent']==state['navigator.userAgent']
        assert state['navigator.platform']=='Win32'
        assert state['navigator.appVersion']==state['navigator.userAgent'].removeprefix('Mozilla/')
        choose('cfx-screen-preset','desktop-1920x1080','sec-display')
        state=cfg()
        assert state['screen.width']==1920 and state['screen.height']==1080
        assert state['window.innerWidth']<=state['window.outerWidth']<=state['screen.availWidth']
        choose('cfx-gpu-preset','apple-m2','sec-graphics')
        state=cfg();assert state['webGl:vendor']=='Apple Inc.' and state['webGl:renderer']=='Apple M2'
        choose('cfx-language-preset','ja-JP','sec-locale')
        state=cfg();assert state['navigator.language']=='ja-JP' and state['locale:region']=='JP'
        assert state['locale:script']=='Jpan' and state['headers.Accept-Language'].startswith('ja-JP')
        cpu=d.find_element(By.CSS_SELECTOR,'select[aria-label="navigator.hardwareConcurrency preset"]')
        d.execute_script('arguments[0].scrollIntoView({block:"center"})',cpu)
        Select(cpu).select_by_value('16'); assert cfg()['navigator.hardwareConcurrency']==16
        load()
        assert Select(d.find_element(By.ID,'cfx-browser-preset')).first_selected_option.get_attribute('value')=='win10-chrome-122', {k:v for k,v in cfg().items() if k.startswith('navigator.') or k=='headers.User-Agent'}
        # Raw edits remain available; a mixed bundle is honestly shown as custom.
        value=d.find_element(By.CSS_SELECTOR,'.k[title="navigator.platform"]').find_element(By.XPATH,'..').find_element(By.CSS_SELECTOR,'.v')
        d.execute_script('arguments[0].scrollIntoView({block:"center"})',value);value.click()
        field=d.find_element(By.CSS_SELECTOR,'#grp-navigator .row-input')
        d.execute_script('arguments[0].select()',field);field.send_keys('CustomPlatform\ue004')
        assert cfg()['navigator.platform']=='CustomPlatform'
        assert Select(d.find_element(By.ID,'cfx-browser-preset')).first_selected_option.get_attribute('value')=='custom'
        choose('cfx-browser-preset','auto')
        assert not f.chrome('return Services.prefs.getChildList("cloakfox.container.0.override.").some(k=>k.endsWith("navigator.userAgent"))')
        choose('cfx-screen-preset','auto','sec-display')
        choose('cfx-gpu-preset','auto','sec-graphics')
        choose('cfx-persona-os','windows')
        d.execute_script('document.getElementById("cfx-regenerate").scrollIntoView({block:"center"})')
        d.find_element(By.ID,'cfx-regenerate').click()
        assert 'Windows' in cfg()['navigator.userAgent']
        assert cfg()['navigator.hardwareConcurrency']==16
        d=f.restart();load()
        assert Select(d.find_element(By.ID,'cfx-persona-os')).first_selected_option.get_attribute('value')=='windows'
        default=cfg()
        Select(d.find_element(By.ID,'cfx-container-select')).select_by_value('2')
        choose('cfx-browser-preset','win10-chrome-122')
        assert 'Chrome/122.' in f.chrome('return JSON.parse(Services.prefs.getStringPref("cloakfox.s.cloak_cfg_2"))["navigator.userAgent"]')
        Select(d.find_element(By.ID,'cfx-container-select')).select_by_value('0')
        assert cfg()==default, 'Container preset changed a different container'
        d.set_window_size(1100,1200)
        d.execute_script('document.documentElement.style.scrollBehavior="auto";document.getElementById("sec-identity").open=true;window.scrollTo(0,document.getElementById("sec-identity").offsetTop-80)')
        d.find_element(By.ID,'sec-identity').screenshot('/tmp/cloakfox-settings-presets.png')
        print('SETTINGS PRESETS PASS: browser/header coherence, display bounds, GPU/language bundles, custom edits, reset, persona, persistence')
if __name__=='__main__':main()
