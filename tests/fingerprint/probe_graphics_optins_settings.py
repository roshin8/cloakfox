#!/usr/bin/env python3
"""Exercise both graphics opt-ins through about:cloakfox in a disposable profile.

Requires CLOAKFOX_BIN and Selenium. Verifies UI/config policy persistence and
identity preservation; native drawing/context behavior has separate probes.
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

POLICIES = {
    'cloakfox.opt.canvas_render_privacy': 'canvas:render_privacy',
    'cloakfox.opt.gpu_backend_profiles': 'webGl:backend_profile',
}


def main():
    report = Path(os.environ.get('REPORT_DIR') or tempfile.mkdtemp(prefix='cloakfox-graphics-optins-report-'))
    report.mkdir(parents=True, exist_ok=True)
    checks = []

    def check(ok, label):
        checks.append({'pass': bool(ok), 'label': label})
        print(('PASS ' if ok else 'FAIL ') + label, flush=True)
        if not ok:
            raise AssertionError(label)

    with tempfile.TemporaryDirectory(prefix='cloakfox-graphics-optins-profile-') as tmp:
        profile = Path(tmp, 'profile')
        profile.mkdir()
        (profile / 'user.js').write_text('user_pref("cloakfox.enabled",true);\n')

        def launch():
            options = Options()
            options.binary_location = os.environ['CLOAKFOX_BIN']
            for arg in ['-headless', '-purgecaches', '-profile', str(profile)]:
                options.add_argument(arg)
            return webdriver.Firefox(options=options, service=Service(
                service_args=['--allow-system-access'], log_output=str(report / 'gecko.log')))

        driver = launch()

        def chrome(script, *args):
            driver.set_context('chrome')
            try:
                return driver.execute_script(script, *args)
            finally:
                driver.set_context('content')

        def load():
            driver.get('about:cloakfox#sec-hardening')
            WebDriverWait(driver, 15).until(lambda d: all(
                d.find_elements(By.CSS_SELECTOR, f'input[data-pref="{pref}"]') for pref in POLICIES))

        def checkbox(pref):
            return driver.find_element(By.CSS_SELECTOR, f'input[data-pref="{pref}"]')

        def configs():
            return chrome("""return [0,1,2].map(id => {
              const cfg=JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+id));
              delete cfg['timing:session_key_hi']; delete cfg['timing:session_key_lo'];
              return cfg;
            });""")

        def seeds():
            return chrome("return [0,1,2].map(id=>Services.prefs.getStringPref('cloakfox.container.'+id+'.math_seed'))")

        selected = {field: False for field in POLICIES.values()}
        try:
            load()
            for pref in POLICIES:
                check(not checkbox(pref).is_selected(), pref + ' defaults off')
            chrome("""for(const id of [0,1,2]) {
              const pref='cloakfox.s.cloak_cfg_'+id;
              const cfg=JSON.parse(Services.prefs.getStringPref(pref));
              Object.assign(cfg, {'navigator.userAgent':'graphics-manual-'+id,
                'canvas:seed':19+id, 'webrtc:ipv4':'192.0.2.'+(id+1),
                sentinel:{owner:id, unchanged:['manual','network']}});
              Services.prefs.setStringPref(pref,JSON.stringify(cfg));
            }""")
            before, original_seeds = configs(), seeds()
            for pref, field in POLICIES.items():
                checkbox(pref).click()
                WebDriverWait(driver, 10).until(lambda _: chrome(
                    'return Services.prefs.getBoolPref(arguments[0])', pref) is True)
                selected[field] = True
                check(configs() == [{**cfg, **selected} for cfg in before],
                      pref + ' changes only policy fields')
                load()
                check(checkbox(pref).is_selected(), pref + ' survives settings reload')
            created = chrome("""
              const {ContextualIdentityService}=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
              const id=ContextualIdentityService.create('Graphics opt-ins fixture','fingerprint','blue').userContextId;
              return {id,cfg:JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+id))};
            """)
            check(all(created['cfg'].get(field) is True for field in POLICIES.values()),
                  'new container inherits both selections')
            # Leave stale opposite values in an existing overlay. Startup must
            # backfill policy without regenerating its manually pinned identity.
            chrome("""const pref='cloakfox.s.cloak_cfg_1';
              const cfg=JSON.parse(Services.prefs.getStringPref(pref));
              cfg['canvas:render_privacy']=false;cfg['webGl:backend_profile']='true';
              Services.prefs.setStringPref(pref,JSON.stringify(cfg));
              Services.prefs.savePrefFile(null);""")
            driver.quit()
            driver = launch()
            load()
            check(all(checkbox(pref).is_selected() for pref in POLICIES),
                  'both selections survive browser restart')
            check(configs() == [{**cfg, **selected} for cfg in before],
                  'startup repairs only policy fields and preserves sentinels')
            for pref, field in POLICIES.items():
                checkbox(pref).click()
                WebDriverWait(driver, 10).until(lambda _: chrome(
                    'return Services.prefs.getBoolPref(arguments[0])', pref) is False)
                selected[field] = False
                check(configs() == [{**cfg, **selected} for cfg in before],
                      pref + ' off preserves other selection and existing privacy')
            check(seeds() == original_seeds, 'all container identity seeds remain unchanged')
            fresh = chrome("return JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+arguments[0]))", created['id'])
            check(all(fresh[field] is False for field in POLICIES.values()),
                  'global changes also update newly created container')
        finally:
            driver.quit()
            (report / 'result.json').write_text(json.dumps({'checks': checks}, indent=2) + '\n')
            print('Report: ' + str(report), flush=True)


if __name__ == '__main__':
    main()
