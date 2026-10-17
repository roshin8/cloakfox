"""Verify actual settings persistence without launching ordinary Chromium sites."""
import json
import os
from pathlib import Path
import tempfile
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait


def main():
    with tempfile.TemporaryDirectory(prefix='cloakfox-presentation-ui-') as folder:
        options=Options();options.binary_location=os.environ['CLOAKFOX_BIN']
        for argument in ('-no-remote','-purgecaches','-profile',folder):options.add_argument(argument)
        options.set_preference('cloakfox.enabled',True)
        driver=webdriver.Firefox(options=options,service=Service(service_args=['--allow-system-access']))
        try:
            driver.get('about:cloakfox')
            wait=WebDriverWait(driver,20)
            wait.until(lambda d:d.execute_script('return document.getElementById("cfx-chromium-presentation")?.value')=='same-window')
            driver.set_context('chrome')
            before=driver.execute_script('return {master:Services.prefs.getBoolPref("cloakfox.enabled"),config:Services.prefs.getStringPref("cloakfox.s.cloak_cfg_0","")}')
            driver.set_context('content')
            containers=driver.execute_script('return Array.from(document.getElementById("cfx-container-select").options,x=>x.value)')
            other=next(value for value in containers if value!='0')
            def select(container):
                driver.execute_script('const s=document.getElementById("cfx-container-select");s.value=arguments[0];s.dispatchEvent(new Event("change"))',container)
            def mode():return driver.execute_script('return document.getElementById("cfx-chromium-presentation").value')
            driver.execute_script('const s=document.getElementById("cfx-chromium-presentation");s.value="separate-window";s.dispatchEvent(new Event("change"))')
            assert 'saved for this container' in driver.execute_script('return document.getElementById("cfx-chromium-presentation-status").textContent')
            select(other);assert mode()=='same-window'
            select('0');assert mode()=='separate-window'
            driver.refresh();wait.until(lambda d:mode()=='separate-window')
            driver.set_context('chrome')
            after=driver.execute_script('return {master:Services.prefs.getBoolPref("cloakfox.enabled"),config:Services.prefs.getStringPref("cloakfox.s.cloak_cfg_0","")}')
            assert before==after,'Presentation changed privacy or persona policy'
            assert driver.execute_script('return Services.prefs.getStringPref("cloakfox.container.0.chromium_presentation")')=='separate-window'
            print(json.dumps({'status':'passed','defaultSaved':'separate-window','otherContainerDefault':'same-window','reloadPersisted':True,'privacyPolicyUnchanged':True,'scope':'Settings preference only; production engine switching remains gated'}))
        finally:driver.quit()

if __name__=='__main__':main()
