#!/usr/bin/env python3
"""Real about:cloakfox checkbox persistence and strict-policy config binding.

Uses a disposable profile, existing container configs with manual sentinels,
then creates a fresh container to verify it inherits the currently selected
policy. Requires CLOAKFOX_BIN; writes a JSON report under REPORT_DIR.
"""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait

PREF='cloakfox.opt.webgl_typed_readback_disabled'
FIELD='webgl:typed_readback:disabled'

def main():
    root=Path(os.environ.get('REPORT_DIR') or tempfile.mkdtemp(prefix='cloakfox-strict-settings-report-'))
    root.mkdir(parents=True,exist_ok=True)
    checks=[]
    def check(ok,label,data=None):
        checks.append({'pass':bool(ok),'label':label,'data':data})
        print(('PASS ' if ok else 'FAIL ')+label,flush=True)
    with tempfile.TemporaryDirectory(prefix='cloakfox-strict-settings-profile-') as tmp:
        profile=Path(tmp,'profile');profile.mkdir()
        (profile/'user.js').write_text('user_pref("cloakfox.enabled",true);\n')
        def launch():
            options=Options();options.binary_location=os.environ['CLOAKFOX_BIN']
            options.add_argument('-headless');options.add_argument('-purgecaches')
            options.add_argument('-profile');options.add_argument(str(profile))
            return webdriver.Firefox(options=options,service=Service(
                service_args=['--allow-system-access'],log_output=str(root/'gecko.log')))
        driver=launch()
        def chrome(script,*args):
            driver.set_context('chrome')
            try:return driver.execute_script(script,*args)
            finally:driver.set_context('content')
        def configs():
            # Firefox157 deliberately refreshes only session timing keys at restart.
            # Compare every persistent identity field while excluding that salt.
            return chrome("""return [1,2].map(id=>{
              const cfg=JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+id));
              delete cfg['timing:session_key_hi'];delete cfg['timing:session_key_lo'];
              return cfg;
            })""")
        def load():
            driver.get('about:cloakfox#sec-hardening')
            WebDriverWait(driver,15).until(lambda d:d.find_elements(By.CSS_SELECTOR,f'input[data-pref="{PREF}"]'))
            return driver.find_element(By.CSS_SELECTOR,f'input[data-pref="{PREF}"]')
        def wait_pref(value):
            WebDriverWait(driver,10).until(lambda _:chrome('return Services.prefs.getBoolPref(arguments[0])',PREF)==value)
        try:
            chrome("""
              Services.prefs.setBoolPref(arguments[0],true);
              for(const id of [1,2]){
                const cfg=JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+id,'{}'));
                Object.assign(cfg,{'webgl:typed_readback:disabled':true,
                  'navigator.userAgent':'manually-pinned-'+id,'canvas:seed':id*17,
                  'webrtc:ipv4':'192.0.2.'+id,'webrtc:ipv6':'2001:db8::'+id,
                  sentinel:{id,unchanged:['manual','network']}});
                Services.prefs.setStringPref('cloakfox.s.cloak_cfg_'+id,JSON.stringify(cfg));
              }
            """,PREF)
            before=configs()
            seeds=chrome("return [1,2].map(id=>Services.prefs.getStringPref('cloakfox.container.'+id+'.math_seed'))")
            checkbox=load();check(checkbox.is_selected(),'strict option initially checked')
            checkbox.click();wait_pref(False)
            current=configs()
            check(current==[{**cfg,FIELD:False} for cfg in before],
                  'checkbox off updates every existing config without changing other fields',current)
            checkbox=load()
            check(not checkbox.is_selected(),'checkbox off survives settings reload')
            check(configs()==[{**cfg,FIELD:False} for cfg in before],'active configs retain off after reload')
            created=chrome("""
              const {ContextualIdentityService}=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
              const id=ContextualIdentityService.create('Strict graphics fixture','fingerprint','blue').userContextId;
              return {id,cfg:JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+id))};
            """)
            check(created['cfg'].get(FIELD) is False,'fresh container inherits off policy',created['id'])
            driver.quit();driver=launch();checkbox=load()
            check(not checkbox.is_selected(),'checkbox off survives browser restart')
            check(configs()==[{**cfg,FIELD:False} for cfg in before],'config sentinels survive browser restart')
            checkbox.click();wait_pref(True)
            check(configs()==before,'checkbox on restores only strict field')
            fresh=chrome("return JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+arguments[0]))",created['id'])
            check(fresh[FIELD] is True,'global checkbox also updates newly created container')
            after_seeds=chrome("return [1,2].map(id=>Services.prefs.getStringPref('cloakfox.container.'+id+'.math_seed'))")
            check(after_seeds==seeds,'toggle preserves independent container seeds')
        finally:
            driver.quit()
            (root/'result.json').write_text(json.dumps({'checks':checks},indent=2)+'\n')
            print('Report: '+str(root),flush=True)
    if not all(c['pass'] for c in checks):raise SystemExit(1)

if __name__=='__main__':main()
