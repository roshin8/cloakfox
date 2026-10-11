"""Container-scoped network intent, multiple Settings views and restart persistence."""
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from screen_management_fixture import ScreenManagementFixture, CHROME as SCREEN_CHROME, FIREFOX

import re

CHROME = re.sub(r'Chrome/\d+', 'Chrome/155', SCREEN_CHROME)

def main():
    with ScreenManagementFixture() as f:
        d=f.driver
        f.set_master(True)
        f.set_config(0,{'navigator.userAgent':CHROME})
        f.set_config(2,{'navigator.userAgent':CHROME})
        def load():
            d.get('about:cloakfox')
            WebDriverWait(d,15).until(lambda d:d.find_elements(By.ID,'cfx-network-follow-identity'))
            WebDriverWait(d,15).until(lambda d:d.find_elements(By.ID,'cfx-layout'))
            d.execute_script("const layout=document.getElementById('cfx-layout'); layout.value='grouped'; layout.dispatchEvent(new Event('change'))")
            d.execute_script("document.documentElement.style.scrollBehavior='auto'; document.querySelector('[data-category=identity]').click()")
            WebDriverWait(d,10).until(lambda d:d.find_element(By.ID,'cfx-network-follow-identity').is_displayed())
        def profile(ucid):
            return f.chrome("return Services.prefs.getIntPref('cloakfox.container.'+arguments[0]+'.network_profile',0)",ucid)
        def toggle():
            box=d.find_element(By.ID,'cfx-network-follow-identity')
            d.execute_script('arguments[0].scrollIntoView({block:"center"})',box)
            d.execute_script('arguments[0].click()',box)
        load()
        assert not d.find_element(By.ID,'cfx-network-follow-identity').is_selected()
        toggle();assert profile(0)==1
        assert 'Experimental' in d.find_element(By.ID,'cfx-network-profile-status').text
        status=d.find_element(By.ID,'cfx-network-profile-status').text
        assert 'trust-anchor IDs' in status and 'ALPS' not in status,status
        first=d.current_window_handle
        d.switch_to.new_window('tab');load()
        assert d.find_element(By.ID,'cfx-network-follow-identity').is_selected()
        toggle();assert profile(0)==0
        d.switch_to.window(first)
        assert not d.find_element(By.ID,'cfx-network-follow-identity').is_selected()
        d.execute_script("const select=document.getElementById('cfx-container-select');select.value='2';select.dispatchEvent(new Event('change'))")
        toggle();assert profile(2)==1 and profile(0)==0
        f.set_config(2,{'navigator.userAgent':FIREFOX})
        WebDriverWait(d,5).until(lambda _:profile(2)==0)
        f.set_config(2,{'navigator.userAgent':CHROME});WebDriverWait(d,5).until(lambda _:profile(2)==1)
        f.set_config(2,{'navigator.userAgent':CHROME.replace('Chrome/155','Chrome/154')})
        WebDriverWait(d,5).until(lambda _:profile(2)==0)
        assert 'no supported' in d.find_element(By.ID,'cfx-network-profile-status').text
        f.set_config(2,{'navigator.userAgent':CHROME});WebDriverWait(d,5).until(lambda _:profile(2)==1)
        f.set_master(False);WebDriverWait(d,5).until(lambda _:profile(2)==0)
        assert 'disabled' in d.find_element(By.ID,'cfx-network-profile-status').text
        f.set_master(True);WebDriverWait(d,5).until(lambda _:profile(2)==1)
        d=f.restart();load()
        d.execute_script("const select=document.getElementById('cfx-container-select');select.value='2';select.dispatchEvent(new Event('change'))")
        assert d.find_element(By.ID,'cfx-network-follow-identity').is_selected()
        assert profile(2)==1 and profile(0)==0
        print('PASS: production toggle, identity/master reconciliation, two Settings views, container isolation and restart persistence')

if __name__=='__main__':main()
