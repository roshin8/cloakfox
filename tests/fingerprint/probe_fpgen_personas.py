#!/usr/bin/env python3
"""Local-only Firefox159 source selection, isolation and native API acceptance.

Uses a disposable profile and headless browser. Never reports identity secrets,
opens a production site, changes installed applications or requests capture.
"""
import base64
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import Select, WebDriverWait


def main():
    out = Path(os.environ['REPORT_DIR'])
    out.mkdir(parents=True, exist_ok=True)
    binary = Path(os.environ['CLOAKFOX_BIN']).resolve()
    report = {'checks': [], 'binary': str(binary), 'headless': True}
    driver = None
    headers = {}
    page = b'<!doctype html><title>Local fpgen acceptance</title><body>Local-only fixture</body>'
    worker = b'onmessage=()=>postMessage({ua:navigator.userAgent,platform:navigator.platform,cores:navigator.hardwareConcurrency,languages:[...navigator.languages]})'

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            headers[self.path] = self.headers.get('User-Agent')
            self.send_response(200)
            self.send_header('Content-Type', 'text/javascript' if self.path.startswith('/worker') else 'text/html')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(worker if self.path.startswith('/worker') else page)

        def log_message(self, *_):
            pass

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def check(value, label):
        report['checks'].append({'pass': bool(value), 'label': label})
        print(('PASS ' if value else 'FAIL ') + label, flush=True)
        if not value:
            raise AssertionError(label)

    with tempfile.TemporaryDirectory(prefix='cloakfox-fpgen-acceptance-') as temp:
        profile = Path(temp) / 'profile'
        profile.mkdir()
        # Simulate a real pre-provider profile: existing master seed, no source.
        legacy_seed = base64.b64encode(bytes(range(32))).decode()
        (profile / 'user.js').write_text(
            'user_pref("cloakfox.enabled",true);\n'
            f'user_pref("cloakfox.container.0.math_seed",{json.dumps(legacy_seed)});\n')
        launches = 0

        def launch():
            nonlocal launches
            launches += 1
            opts = Options()
            opts.binary_location = str(binary)
            opts.page_load_strategy = 'none'
            for arg in ['-headless', '-purgecaches', '-profile', str(profile)]:
                opts.add_argument(arg)
            opts.set_preference('remote.prefs.recommended', False)
            d = webdriver.Firefox(options=opts, service=Service(
                executable_path=os.environ.get('GECKODRIVER') or shutil.which('geckodriver'),
                service_args=['--allow-system-access'], log_output=str(out / f'gecko-{launches}.log')))
            d.set_script_timeout(30)
            return d

        def chrome(script, *args):
            driver.set_context('chrome')
            try:
                return driver.execute_script(script, *args)
            finally:
                driver.set_context('content')

        def snapshot(owner):
            return chrome('''
              const p='cloakfox.container.'+arguments[0]+'.';
              const cfg=JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+arguments[0]));
              delete cfg['timing:session_key_hi'];delete cfg['timing:session_key_lo'];
              const state={};for(const name of Services.prefs.getChildList(p)){
                if(!Services.prefs.prefHasUserValue(name))continue;
                // Publication generation advances at startup, but preserve the
                // native profile bit and exhaustion sentinel in comparisons.
                if(name===p+'network_state'){
                  const stateValue=Services.prefs.getIntPref(name);
                  state[name]=stateValue<0?-1:stateValue&1;continue;
                }
                const t=Services.prefs.getPrefType(name);
                state[name]=t===128?Services.prefs.getBoolPref(name):t===64?Services.prefs.getIntPref(name):Services.prefs.getStringPref(name);
              }
              return {cfg,state,source:Services.prefs.getStringPref(p+'persona_source','browserforge')};
            ''', owner)

        def load_settings(owner):
            driver.get('about:blank')
            WebDriverWait(driver, 20).until(lambda d: d.execute_script("return location.href==='about:blank'"))
            driver.get(f'about:cloakfox?ucid={owner}#cfx-persona-panel')
            WebDriverWait(driver, 30).until(lambda d: d.find_elements(By.ID, 'cfx-persona-source'))
            WebDriverWait(driver, 20).until(lambda d: d.find_element(By.ID, 'cfx-container-select').get_attribute('value') == str(owner))

        def reveal(control):
            driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})", control)
            WebDriverWait(driver, 10).until(lambda d: d.execute_script('''
              const c=arguments[0],r=c.getBoundingClientRect();
              const hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
              return hit===c || c.contains(hit);
            ''', control))
            return control

        def choose(id, value):
            control = Select(reveal(driver.find_element(By.ID, id)))
            if id == 'cfx-persona-filter':
                control.select_by_visible_text(value)
            else:
                control.select_by_value(value)

        def generate():
            button = reveal(driver.find_element(By.ID, 'cfx-generate-new'))
            button.click()
            WebDriverWait(driver, 30).until(lambda d: not d.find_element(By.ID, 'cfx-generate-new').get_attribute('aria-busy'))
            status = driver.find_element(By.ID, 'cfx-identity-status')
            if 'identity-error' in status.get_attribute('class'):
                report['generationError'] = status.text
                print('GENERATION ERROR:', status.text, flush=True)
            check('identity-error' not in status.get_attribute('class'), 'real settings generation completes without an error')

        def open_site(owner, host='127.0.0.1'):
            url = f'http://{host}:{server.server_port}/owner-{owner}'
            old = set(driver.window_handles)
            chrome('''
              const w=Services.wm.getMostRecentWindow('navigator:browser');
              w.gBrowser.selectedTab=w.gBrowser.addTab(arguments[0],{
                userContextId:arguments[1],triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
            ''', url, owner)
            handle = WebDriverWait(driver, 20).until(lambda d: next(iter(set(d.window_handles)-old), None))
            driver.switch_to.window(handle)
            WebDriverWait(driver, 20).until(lambda d: d.execute_script("return location.href===arguments[0] && document.readyState==='complete'", url))

        def signals():
            return driver.execute_async_script('''
              const done=arguments[arguments.length-1];
              const canvas=document.createElement('canvas');canvas.width=80;canvas.height=40;
              const c=canvas.getContext('2d');c.fillStyle='#427ac1';c.fillRect(0,0,80,40);c.fillStyle='white';c.fillText('Persona',3,20);
              const gpu=document.createElement('canvas').getContext('webgl');
              const ext=gpu?.getExtension('WEBGL_debug_renderer_info');
              const result={ua:navigator.userAgent,platform:navigator.platform,cores:navigator.hardwareConcurrency,
                languages:[...navigator.languages],width:screen.width,height:screen.height,dpr:devicePixelRatio,
                innerWidth,innerHeight,availWidth:screen.availWidth,availHeight:screen.availHeight,
                canvas:canvas.toDataURL(),renderer:ext?gpu.getParameter(ext.UNMASKED_RENDERER_WEBGL):null,
                cookie:document.cookie,storage:localStorage.getItem('owner')};
              const w=new Worker('/worker.js');
              w.onmessage=e=>{w.terminate();done({...result,worker:e.data})};
              w.onerror=e=>{w.terminate();done({...result,error:e.message})};w.postMessage('read');
            ''')

        try:
            driver = launch()
            report['version'] = chrome('return Services.appinfo.version')
            check(report['version'].startswith('159.'), 'acceptance runs on Firefox 159')
            WebDriverWait(driver, 30).until(lambda _: chrome("return !!Services.prefs.getStringPref('cloakfox.s.cloak_cfg_0','')"))
            legacy = snapshot(0)
            check(legacy['source'] == 'browserforge', 'existing seed without a provider retains BrowserForge')
            load_settings(0)
            check(set(o.get_attribute('value') for o in Select(driver.find_element(By.ID, 'cfx-persona-source')).options) == {'fpgen', 'browserforge'}, 'packaged settings offer both persona sources')
            check(snapshot(0) == legacy, 'opening source controls does not change existing identity')
            owners = chrome('''
              const {ContextualIdentityService:cis}=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
              return [cis.create('fpgen acceptance A','fingerprint','blue').userContextId,
                      cis.create('fpgen acceptance B','fingerprint','green').userContextId];
            ''')
            for owner in owners:
                WebDriverWait(driver, 30).until(lambda _: chrome("return !!Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+arguments[0],'')", owner))
                check(snapshot(owner)['source'] == 'fpgen', f'new container {owner} defaults to fpgen')
            a, b = owners
            b_initial = snapshot(b)
            policy_before = chrome('''
              const state={};for(const prefix of ['cloakfox.opt.','cloakfox.webrtc.','cloakfox.privacy.','permissions.']){
                for(const name of Services.prefs.getChildList(prefix)){
                  const t=Services.prefs.getPrefType(name);
                  state[name]=t===128?Services.prefs.getBoolPref(name):t===64?Services.prefs.getIntPref(name):Services.prefs.getStringPref(name);
                }
              }return state;
            ''')
            for provider, os_value, hardware in [('fpgen', 'macOS', 'apple'), ('browserforge', 'Windows', 'nvidia'), ('fpgen', 'Linux', 'intel')]:
                load_settings(a)
                before = snapshot(a)
                choose('cfx-persona-source', provider)
                choose('cfx-persona-filter', os_value)
                choose('cfx-persona-hardware', hardware)
                check(snapshot(a) == before, f'{provider} filters are staged until Generate')
                generate()
                result = snapshot(a)
                check(result['source'] == provider, f'{provider} source is saved on selected container')
                expected = {'macOS': 'MacIntel', 'Windows': 'Win32', 'Linux': 'Linux x86_64'}[os_value]
                check(result['cfg']['navigator.platform'] == expected, f'{provider} generation honors selected {os_value}')
                check(snapshot(b) == b_initial and snapshot(0) == legacy, f'{provider} generation leaves other identities unchanged')
                check(result['cfg']['fingerprint:secret'] != b_initial['cfg']['fingerprint:secret'], 'containers retain separate secrets')
                check(all(k in result['cfg'] for k in ['canvas:seed', 'audio:seed', 'font:seed', 'fonts:spacing_seed', 'math:trig_seed', 'fonts']), 'generated identity retains existing privacy fields')
                if provider == 'browserforge':
                    open_site(a)
                    observed_bf = signals()
                    check('error' not in observed_bf, 'BrowserForge website worker loads')
                    for name, key in [('ua','navigator.userAgent'), ('platform','navigator.platform'), ('cores','navigator.hardwareConcurrency')]:
                        check(observed_bf[name] == result['cfg'][key] == observed_bf['worker'][name], f'BrowserForge {name} matches native window and worker')
                    check(observed_bf['ua'] == headers[f'/owner-{a}'], 'BrowserForge HTTP User-Agent matches document')
                    driver.quit()
                    driver = None
                    (profile / 'user.js').unlink(missing_ok=True)
                    driver = launch()
                    load_settings(a)
                    restarted = snapshot(a)
                    if restarted != result:
                        report['restartDifferences'] = {group: {key: [result[group].get(key), restarted[group].get(key)]
                            if not any(word in key.lower() for word in ['secret','seed','key']) else 'redacted'
                            for key in result[group].keys() | restarted[group].keys()
                            if result[group].get(key) != restarted[group].get(key)} for group in ['cfg','state']}
                        print('RESTART DIFF:', json.dumps(report['restartDifferences']), flush=True)
                    check(restarted == result, 'BrowserForge identity remains unchanged after restart')
                    check(Select(driver.find_element(By.ID,'cfx-persona-source')).first_selected_option.get_attribute('value') == 'browserforge', 'explicit BrowserForge choice remains selected after restart')

            before_invalid = snapshot(a)
            driver.execute_script('''
              const s=document.getElementById('cfx-persona-source');
              s.add(new Option('Invalid provider fixture','invalid-provider'));
            ''')
            choose('cfx-persona-source', 'invalid-provider')
            reveal(driver.find_element(By.ID, 'cfx-generate-new')).click()
            WebDriverWait(driver, 30).until(lambda d: not d.find_element(By.ID, 'cfx-generate-new').get_attribute('aria-busy'))
            check('identity-error' in driver.find_element(By.ID,'cfx-identity-status').get_attribute('class'), 'invalid provider fails visibly')
            check(snapshot(a) == before_invalid, 'failed generation preserves provider, seed, overrides and published identity')
            policy_after = chrome('''
              const state={};for(const prefix of ['cloakfox.opt.','cloakfox.webrtc.','cloakfox.privacy.','permissions.']){
                for(const name of Services.prefs.getChildList(prefix)){
                  const t=Services.prefs.getPrefType(name);
                  state[name]=t===128?Services.prefs.getBoolPref(name):t===64?Services.prefs.getIntPref(name):Services.prefs.getStringPref(name);
                }
              }return state;
            ''')
            check(policy_before == policy_after, 'both providers preserve privacy, WebRTC and permission preferences')

            # Compare actual native document/worker APIs and network header.
            public = {}
            for owner in owners:
                cfg = snapshot(owner)['cfg']
                open_site(owner)
                observed = signals()
                report.setdefault('nativeScreen', []).append({'owner': owner,
                    'saved': [cfg['screen.width'], cfg['screen.height']],
                    'observed': [observed['width'], observed['height']], 'dpr': observed['dpr']})
                check('error' not in observed, f'owner {owner} worker loads')
                for name, key in [('ua','navigator.userAgent'), ('platform','navigator.platform'), ('cores','navigator.hardwareConcurrency')]:
                    check(observed[name] == cfg[key] == observed['worker'][name], f'owner {owner} {name} matches native window and worker')
                letterboxing = chrome("return Services.prefs.getBoolPref('privacy.resistFingerprinting.letterboxing',false)")
                if letterboxing:
                    check(observed['width'] == observed['innerWidth'] == observed['availWidth'] and
                          observed['height'] == observed['innerHeight'] == observed['availHeight'],
                          f'owner {owner} retains protected letterboxed screen geometry')
                else:
                    check(observed['width'] == cfg['screen.width'] and observed['height'] == cfg['screen.height'], f'owner {owner} native screen matches saved persona')
                check(observed['ua'] == headers[f'/owner-{owner}'], f'owner {owner} HTTP User-Agent matches document')
                check(observed['storage'] is None and 'owner=' not in observed['cookie'], f'owner {owner} has isolated storage')
                driver.execute_script("localStorage.setItem('owner',arguments[0]);document.cookie='owner='+arguments[0]+';path=/'", str(owner))
                driver.execute_script('window.__fpgenReloadMarker=true')
                driver.refresh()
                WebDriverWait(driver, 20).until(lambda d: d.execute_script("return !window.__fpgenReloadMarker && document.readyState==='complete'"))
                repeated = signals()
                check(repeated['canvas'] == observed['canvas'], f'owner {owner} canvas is stable on reload')
                public[owner] = observed
            check(public[a]['canvas'] != public[b]['canvas'], 'separate container canvas fingerprints remain distinct')
            open_site(a, 'localhost')
            second_site = signals()
            check(second_site['canvas'] != public[a]['canvas'], 'same-container canvas remains separated across sites')
            saved = {owner: snapshot(owner) for owner in [0, a, b]}
            driver.quit()
            driver = None
            (profile / 'user.js').unlink(missing_ok=True)
            driver = launch()
            for owner, state in saved.items():
                WebDriverWait(driver, 30).until(lambda _: chrome("return !!Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+arguments[0],'')", owner))
                check(snapshot(owner) == state, f'owner {owner} provider, seeds and config survive restart')
            load_settings(a)
            check(Select(driver.find_element(By.ID,'cfx-persona-source')).first_selected_option.get_attribute('value') == 'fpgen', 'source dropdown restores saved fpgen selection')
            report['passed'] = True
        except BaseException as error:
            report['passed'] = False
            report['error'] = f'{type(error).__name__}: {error}'
            raise
        finally:
            if driver:
                driver.quit()
            server.shutdown()
            server.server_close()
            xul = binary.parent / 'XUL'
            with xul.open('rb') as handle:
                report['xulSHA256'] = hashlib.file_digest(handle, 'sha256').hexdigest()
            (out / 'validation.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
