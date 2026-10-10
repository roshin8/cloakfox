#!/usr/bin/env python3
"""Website Light/Dark/Automatic: page-world CSS/JS, live updates and restart.

Uses disposable profiles and local same-/cross-origin frames. Simulated theme
preferences affect only the test profile, never the desktop's real appearance.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

from probe_focus_masking import chrome

PREF = "layout.css.prefers-color-scheme.content-override"
PAGE = """<!doctype html><meta charset=utf-8>
<style>html{color-scheme:light dark;--dark:0}
@media(prefers-color-scheme:dark){html{--dark:1}}
</style><pre id=report></pre><script>
const dark=matchMedia('(prefers-color-scheme:dark)');
const light=matchMedia('(prefers-color-scheme:light)');
let changes=0;dark.addEventListener('change',()=>changes++);
const label=new URLSearchParams(location.search).get('label')||'top';
const reports={};window.addEventListener('message',e=>{
  if(e.data?.appearanceProbe)reports[e.data.label]=e.data.value;
});
function collect(){return {dark:dark.matches,light:light.matches,changes,
  cssDark:getComputedStyle(document.documentElement).getPropertyValue('--dark').trim()==='1',
  mixed:matchMedia('(pointer:fine) and (prefers-color-scheme:dark)').matches,
  background:getComputedStyle(document.documentElement).backgroundColor,
  token:document.documentElement.dataset.token};}
document.documentElement.dataset.token=crypto.randomUUID();
setInterval(()=>{
 const value=collect();
 if(label==='top')document.querySelector('#report').textContent=JSON.stringify({top:value,...reports});
 else parent.postMessage({appearanceProbe:true,label,value},'*');
},50);
if(label==='top')for(const name of ['same','cross']){
 const f=document.createElement('iframe'),u=new URL(location.href);
 u.searchParams.set('label',name);if(name==='cross')u.hostname='localhost';
 f.src=u;document.body.appendChild(f);
}
</script>"""


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def read_report(driver):
    raw = driver.execute_script("return document.querySelector('#report')?.textContent")
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {}


def wait_report(driver, expected=None, before=None):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        value = read_report(driver)
        if all(k in value for k in ['top', 'same', 'cross']):
            if expected is None or all(r['dark'] == expected and r['cssDark'] == expected
                    and (before is None or before[k]['cssDark'] == expected
                         or r['changes'] > before[k]['changes'])
                    for k, r in value.items()):
                return value
        time.sleep(.05)
    return read_report(driver)


def set_appearance(driver, choice, theme, system):
    # The theme consumer owns browser.theme.content-theme and rewrites it
    # whenever the system appearance changes. Exercise real built-in themes
    # rather than racing it with direct writes to its derived preference.
    driver.set_context('chrome')
    try:
        result = driver.execute_async_script("""
          const [choice,theme,system,done]=arguments;
          const {AddonManager}=ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
          const {BuiltInThemes}=ChromeUtils.importESModule('resource:///modules/BuiltInThemes.sys.mjs');
          (async()=>{
            await BuiltInThemes.ensureBuiltInThemes();
            Services.prefs.setIntPref('ui.systemUsesDarkTheme',system);
            const id=['firefox-compact-dark@mozilla.org',
              'firefox-compact-light@mozilla.org','default-theme@mozilla.org'][theme];
            const addon=await AddonManager.getAddonByID(id);
            if(!addon)throw new Error('Missing built-in theme: '+id);
            await addon.enable();
            Services.prefs.setIntPref('layout.css.prefers-color-scheme.content-override',choice);
            done({id});
          })().catch(e=>done({error:e.message}));
        """, choice, theme, system)
    finally:
        driver.set_context('content')
    assert 'error' not in result, result


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    checks = []

    def check(ok, name, data=None):
        checks.append({"name": name, "pass": bool(ok), "data": data})
        print(('PASS' if ok else 'FAIL') + ' — ' + name, flush=True)
        if not ok:
            print(json.dumps(data), flush=True)

    try:
        with tempfile.TemporaryDirectory(prefix='cloakfox-website-appearance-') as temp:
            profile = Path(temp) / 'profile'
            profile.mkdir()

            def launch():
                opts = Options()
                opts.binary_location = os.environ['CLOAKFOX_BIN']
                opts.add_argument('-headless')
                opts.add_argument('-profile')
                opts.add_argument(str(profile))
                return webdriver.Firefox(options=opts, service=Service(
                    executable_path=os.environ.get('GECKODRIVER') or shutil.which('geckodriver'),
                    service_args=['--allow-system-access'], log_output=str(Path(temp)/'gecko.log')))

            driver = launch()
            try:
                check(chrome(driver, 'return Services.prefs.getIntPref(arguments[0])', PREF) == 2,
                      'fresh profile defaults to Automatic')
                for ucid in [0, 2]:
                    before_handles=set(driver.window_handles)
                    chrome(driver, """
                      const id=arguments[0],key='cloakfox.s.cloak_cfg_'+id;
                      const cfg=JSON.parse(Services.prefs.getStringPref(key,'{}'));
                      cfg['document:prefersColorScheme']=0; // legacy light pin must not win
                      Services.prefs.setStringPref(key,JSON.stringify(cfg));
                      const tab=gBrowser.addTab(arguments[1],{userContextId:id,
                        triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
                      gBrowser.selectedTab=tab;
                    """, ucid, f'http://127.0.0.1:{server.server_port}/')
                    deadline=time.monotonic()+10
                    while not (set(driver.window_handles)-before_handles):
                        if time.monotonic()>deadline:
                            raise AssertionError('Container tab did not open')
                        time.sleep(.05)
                    driver.switch_to.window((set(driver.window_handles)-before_handles).pop())
                    initial=wait_report(driver)
                    assert len(initial)==3, ('Probe frames did not report',initial)
                    for enabled in [True, False]:
                        chrome(driver, 'Services.prefs.setBoolPref("cloakfox.enabled",arguments[0])', enabled)
                        for name, choice, theme, system, expected in [
                            ('Dark', 0, 1, 0, True),
                            ('Light', 1, 0, 1, False),
                            ('Automatic/dark theme', 2, 0, 0, True),
                            ('Automatic/light theme', 2, 1, 1, False),
                            ('Automatic/system dark', 2, 2, 1, True),
                            ('Automatic/system light', 2, 2, 0, False),
                        ]:
                            before=wait_report(driver)
                            set_appearance(driver, choice, theme, system)
                            # CSS can update before the queued MediaQueryList
                            # change event. Wait for both rather than sampling
                            # the first frame in between those native steps.
                            result=wait_report(driver,expected,before)
                            check(len(result)==3 and all(r['dark']==expected and
                                  r['light']==(not expected) and r['cssDark']==expected and
                                  r['mixed']==expected for r in result.values()),
                                  f'{name}: CSS and page JS agree (container={ucid}, enabled={enabled})',result)
                            check(len(result)==3 and all(r['token']==before[k]['token'] and
                                  (before[k]['cssDark']==expected or r['changes']>before[k]['changes'])
                                  for k,r in result.items()),
                                  f'{name}: existing documents receive theme changes (container={ucid}, enabled={enabled})',result)
                chrome(driver, 'Services.prefs.setIntPref(arguments[0],1); Services.prefs.savePrefFile(null)', PREF)
            finally:
                driver.quit()
            for saved in [1, 2, 0]:
                driver=launch()
                try:
                    value=chrome(driver,'return Services.prefs.getIntPref(arguments[0])',PREF)
                    check(value==saved,f'website appearance survives restart: {saved}',value)
                    next_value={1:2,2:0,0:2}[saved]
                    chrome(driver,'Services.prefs.setIntPref(arguments[0],arguments[1]); Services.prefs.savePrefFile(null)',PREF,next_value)
                finally:
                    driver.quit()
    finally:
        server.shutdown()
        server.server_close()
    report=Path(os.environ.get('WEBSITE_APPEARANCE_REPORT','/tmp/cloakfox-website-appearance.json'))
    report.write_text(json.dumps(checks,indent=2)+'\n')
    passed=sum(c['pass'] for c in checks)
    print(f'{passed}/{len(checks)} checks passed; {report}')
    return 0 if passed==len(checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
