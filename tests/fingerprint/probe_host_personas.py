"""Exercise native settings handlers and restart stability for persona OS modes."""
import json
import tempfile
from pathlib import Path
from selenium.webdriver.support.ui import WebDriverWait
from probe_daily_defaults import launch

def snapshot(driver,ucid):
    driver.set_context('content')
    WebDriverWait(driver,15).until(lambda d:d.execute_script("return !document.querySelector('[aria-busy=true]')"))
    driver.set_context('chrome')
    result = driver.execute_script("""
const prefix='cloakfox.container.'+arguments[0]+'.';
return {mode:Services.prefs.getStringPref(prefix+'persona_os_mode','legacy'),seed:Services.prefs.getStringPref(prefix+'math_seed'),cfg:Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+arguments[0])};
""",ucid)
    #157 session timing keys rotate on launch; persisted identity fields stay exact.
    cfg = json.loads(result['cfg'])
    result['sessionTiming'] = [cfg.pop('timing:session_key_hi'), cfg.pop('timing:session_key_lo')]
    result['cfg'] = cfg
    return result


def identity(state):
    return {key:value for key,value in state.items() if key != 'sessionTiming'}


def main():
    with tempfile.TemporaryDirectory(prefix='cloakfox-host-personas-') as temp:
        profile=Path(temp)/'profile';profile.mkdir()
        driver=launch(profile,Path(temp)/'first.log')
        try:
            ucid=driver.execute_script("return ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService.create('Host mode','fingerprint','blue').userContextId;")
            fresh=snapshot(driver,ucid);assert fresh['mode']=='legacy',fresh
            host=driver.execute_script('return Services.appinfo.OS')
            expected={'Darwin':'MacIntel','WINNT':'Win32','Linux':'Linux x86_64'}[host]
            driver.set_context('content');driver.get('about:cloakfox')
            WebDriverWait(driver,15).until(lambda d:d.execute_script("return document.querySelectorAll('#grp-navigator .signal-row').length || document.getElementById('cfx-headline-text').textContent !== '—'"))
            driver.execute_script("const s=document.getElementById('cfx-container-select');s.value=String(arguments[0]);s.dispatchEvent(new Event('change'));",ucid)
            labels=driver.execute_script("return [...document.querySelectorAll('#cfx-persona-choice optgroup')].map(o=>o.label)")
            assert len(labels)==3 and all(any(os in label for label in labels) for os in ['Windows','macOS','Linux']),labels
            driver.execute_script("const f=document.getElementById('cfx-persona-filter');f.value='Windows';f.dispatchEvent(new Event('change'))")
            assert driver.execute_script("return [...document.querySelectorAll('#cfx-persona-choice optgroup')].map(g=>g.label)")==['Windows']
            assert snapshot(driver,ucid)==fresh
            driver.set_context('content')
            driver.execute_script("const f=document.getElementById('cfx-persona-filter');f.value='all';f.dispatchEvent(new Event('change'));document.getElementById('cfx-persona-choice').value='2';document.getElementById('cfx-persona-choice').dispatchEvent(new Event('change'))")
            assert driver.execute_script("return [...document.querySelectorAll('.card p:empty')].every(p=>getComputedStyle(p).display==='none')")
            driver.execute_script("document.querySelector('[data-category=display]').click()")
            assert driver.execute_script("const d=document.querySelector('#grp-screen details');d.open=true;return [...d.querySelectorAll('.spoof-row')].every(r=>getComputedStyle(r).display==='grid' && r.getBoundingClientRect().width>d.getBoundingClientRect().width*.9)")
            driver.execute_script("document.querySelector('[data-category=identity]').click()")
            # Choosing a future mode alone must not alter current appearance.
            assert driver.execute_script("return !document.getElementById('cfx-persona-os-mode')")
            assert snapshot(driver,ucid)==fresh
            driver.set_context('content');driver.execute_script("document.getElementById('cfx-regenerate').click()")
            legacy=snapshot(driver,ucid);assert legacy['mode']=='legacy';assert legacy['seed']!=fresh['seed']
            assert driver.execute_script("return Services.prefs.getIntPref('cloakfox.container.'+arguments[0]+'.persona_index')",ucid)==2
            driver.set_context('content')
            driver.execute_script("const s=document.querySelector('select[data-key=\"navigator.hardwareConcurrency\"]');s.value='16';s.dispatchEvent(new Event('change'))")
            before_generated=snapshot(driver,ucid)
            assert before_generated['cfg']['navigator.hardwareConcurrency']==16
            other=snapshot(driver,0)
            driver.set_context('content')
            driver.execute_script("document.getElementById('cfx-persona-choice').value='3';document.getElementById('cfx-generate-new').click()")
            generated=snapshot(driver,ucid)
            assert generated['seed']!=before_generated['seed']
            assert generated['cfg']['navigator.hardwareConcurrency']==16
            assert driver.execute_script("return Services.prefs.getIntPref('cloakfox.container.'+arguments[0]+'.persona_index',-1)",ucid)==-1
            assert snapshot(driver,0)==other
            driver.set_context('content')
            driver.execute_script("const s=document.querySelector('select[data-key=\"navigator.hardwareConcurrency\"]');s.value='auto';s.dispatchEvent(new Event('change'))")
            driver.set_context('chrome')
            # Emulate a pre-mode identity, then restart: no silent migration.
            driver.execute_script("Services.prefs.clearUserPref('cloakfox.container.'+arguments[0]+'.persona_os_mode');Services.prefs.savePrefFile(null);",ucid)
            old=snapshot(driver,ucid)
        finally:driver.quit()
        driver=launch(profile,Path(temp)/'second.log')
        try:
            restarted=snapshot(driver,ucid)
            assert identity(restarted)==identity(old),(old,restarted)
            assert restarted['sessionTiming'] != old['sessionTiming'], 'restart reused timing session key'
            driver.set_context('content');driver.get('about:cloakfox')
            WebDriverWait(driver,15).until(lambda d:d.execute_script("return document.getElementById('cfx-headline-text').textContent !== '—'"))
            driver.execute_script("const s=document.getElementById('cfx-container-select');s.value=String(arguments[0]);s.dispatchEvent(new Event('change'));const f=document.getElementById('cfx-persona-filter');f.value=arguments[1];f.dispatchEvent(new Event('change'));document.getElementById('cfx-generate-new').click();",ucid,{"Darwin":"macOS","WINNT":"Windows","Linux":"Linux"}[host])
            changed=snapshot(driver,ucid)
            assert changed['mode']=={'Darwin':'macos','WINNT':'windows','Linux':'linux'}[host];assert changed['seed']!=old['seed']
            assert changed['cfg']['navigator.platform']==expected
            for os, mode, platform in [('Windows','windows','Win32'),('macOS','macos','MacIntel'),('Linux','linux','Linux x86_64')]:
                before=snapshot(driver,ucid)
                driver.set_context('content')
                driver.execute_script("const f=document.getElementById('cfx-persona-filter');f.value=arguments[0];f.dispatchEvent(new Event('change'))",os)
                assert snapshot(driver,ucid)==before
                driver.set_context('content')
                assert driver.execute_script("return document.getElementById('cfx-persona-choice').value")=='-1'
                assert driver.execute_script("return document.getElementById('cfx-regenerate').disabled")
                for attempt in range(3):
                    driver.execute_script("document.getElementById('cfx-generate-new').click()")
                    result=snapshot(driver,ucid)
                    assert result['mode']==mode
                    assert result['cfg']['navigator.platform']==platform
                    assert result['seed']!=before['seed']
                    before=result
                    driver.set_context('content')
                    assert 'Generated and applied' in driver.execute_script("return document.getElementById('cfx-identity-status').textContent")
                    assert driver.execute_script("return document.getElementById('cfx-persona-filter').value")==os
                    assert driver.execute_script("return document.getElementById('cfx-regenerate').disabled")
                driver.get('about:cloakfox?ucid='+str(ucid))
                WebDriverWait(driver,10).until(lambda d:d.execute_script("return document.getElementById('cfx-persona-filter').value")==os)
                assert snapshot(driver,ucid)==result
            print(json.dumps({'ok':True,'host':host,'newMode':fresh['mode'],'legacyRestartStable':identity(restarted)==identity(old),'timingKeyRotated':restarted['sessionTiming']!=old['sessionTiming'],'explicitHostMode':changed['mode']}))
        finally:driver.quit()

if __name__=='__main__':main()
