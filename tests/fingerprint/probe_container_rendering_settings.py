#!/usr/bin/env python3
"""Headless about:cloakfox per-owner rendering controls in a disposable profile.

This checks real privileged settings handlers and persistence, not native GPU
admission or canonical painting (those have separate probes). The fixture uses
paired BrowserForge reference labels validated by createReferenceGPUProfile.
Requires CLOAKFOX_BIN, geckodriver and Selenium; reports no identity secrets.
"""
from __future__ import annotations
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait

PIPELINE = 'cloakfox.experimental.canvas_pipeline'
GPU_PROFILES = 'cloakfox.opt.container_rendering_profiles'
GEOMETRY = 'geometry:canonical'
REFERENCE = 'rendering:gpu_reference'
OBSERVED = 'rendering:gpu_observed'


def main():
    out = Path(os.environ.get('REPORT_DIR') or tempfile.mkdtemp(prefix='cloakfox-container-rendering-report-'))
    out.mkdir(parents=True, exist_ok=True)
    report = {'checks': [], 'purpose': 'real selected-owner settings handlers and persistence'}

    def check(ok, label):
        report['checks'].append({'pass': bool(ok), 'label': label})
        print(('PASS ' if ok else 'FAIL ') + label, flush=True)
        if not ok:
            raise AssertionError(label)

    binary = Path(os.environ['CLOAKFOX_BIN']).resolve()
    report['binary'] = str(binary)
    xul = binary.parent / 'XUL'
    if not xul.exists():
        xul = binary.parents[1] / 'Resources/XUL'
    with xul.open('rb') as source:
        report['xulSHA256'] = hashlib.file_digest(source, 'sha256').hexdigest()
    with tempfile.TemporaryDirectory(prefix='cloakfox-container-rendering-profile-') as temp:
        profile = Path(temp) / 'profile'
        profile.mkdir()
        (profile / 'user.js').write_text('user_pref("cloakfox.enabled",true);\n')
        launches = 0

        def launch():
            nonlocal launches
            launches += 1
            options = Options()
            # Internal category navigation has no new load event. All readiness
            # and persistence expectations below are explicitly polled.
            options.page_load_strategy = 'none'
            options.binary_location = str(binary)
            for arg in ['-headless', '-purgecaches', '-profile', str(profile)]:
                options.add_argument(arg)
            options.set_preference('remote.prefs.recommended', False)
            return webdriver.Firefox(options=options, service=Service(
                executable_path=os.environ.get('GECKODRIVER') or shutil.which('geckodriver'),
                service_args=['--allow-system-access'], log_output=str(out / f'gecko-{launches}.log')))

        driver = launch()

        def chrome(script, *args):
            driver.set_context('chrome')
            try:
                return driver.execute_script(script, *args)
            finally:
                driver.set_context('content')

        def load(owner):
            # With page_load_strategy=none, an immediate refresh can cancel a
            # pending owner navigation and reload the previous owner's page.
            # Commit a blank document first, guaranteeing fresh handlers even
            # when reloading the same settings URL after external pref changes.
            driver.get('about:blank')
            WebDriverWait(driver, 20).until(lambda d: d.execute_script(
                "return location.href==='about:blank' && document.readyState==='complete'"))
            target = f'about:cloakfox?ucid={owner}#sec-hardening'
            driver.get(target)
            WebDriverWait(driver, 20).until(lambda d: d.execute_script(
                "return location.href===arguments[0] && document.readyState==='complete'", target))
            WebDriverWait(driver, 20).until(lambda d: all(d.find_elements(
                By.CSS_SELECTOR, f'input[data-container-rendering="{key}"]') for key in [GEOMETRY, REFERENCE, OBSERVED]))
            WebDriverWait(driver, 10).until(lambda d: d.find_element(By.ID, 'cfx-container-select').get_attribute('value') == str(owner))

        def reveal(control):
            # The fixed settings header can cover WebDriver's default nearest
            # scroll position. Center the real control before native clicks.
            driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'});", control)
            WebDriverWait(driver,10).until(lambda d:d.execute_script("""
              const c=arguments[0],r=c.getBoundingClientRect();
              const hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
              return hit===c || c.contains(hit);
            """,control))
            return control

        def mode(key):
            driver.execute_script("location.hash='sec-graphics'")
            control=driver.find_element(By.CSS_SELECTOR, f'input[data-container-rendering="{key}"]')
            WebDriverWait(driver,10).until(lambda _:control.is_displayed())
            return reveal(control)

        def backing(pref):
            driver.execute_script("location.hash='sec-hardening'")
            control=driver.find_element(By.CSS_SELECTOR, f'input[data-pref="{pref}"]')
            WebDriverWait(driver,10).until(lambda _:control.is_displayed())
            return reveal(control)

        def status():
            mode(GEOMETRY)
            return driver.find_element(By.ID, 'cfx-container-rendering-status').text

        def snapshot(owners):
            # Do not include these raw records in the report. Session-only
            # timing keys intentionally rotate at browser startup.
            return chrome("""return arguments[0].map(id=>{
              const p='cloakfox.container.'+id+'.', cfg=JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+id));
              delete cfg['timing:session_key_hi'];delete cfg['timing:session_key_lo'];
              const branch=Services.prefs.getBranch(p+'override.');
              const overrides={};for(const key of branch.getChildList('')){
                const name=p+'override.'+key,type=Services.prefs.getPrefType(name);
                overrides[key]=type===128?Services.prefs.getBoolPref(name):type===64?Services.prefs.getIntPref(name):Services.prefs.getStringPref(name);
              }
              return {id,cfg,overrides,mathSeed:Services.prefs.getStringPref(p+'math_seed'),
                keyboardSeed:Services.prefs.getStringPref(p+'keyboard_seed',''),timingSeed:Services.prefs.getStringPref(p+'timing_seed','')};
            });""", owners)

        def identity(record):
            return {key: value for key, value in record.items() if key not in ('cfg', 'overrides')} | {
                'identityConfig': {key: value for key, value in record['cfg'].items() if 'seed' in key.lower() or 'secret' in key.lower()}}

        def wait_request(owner, key, value):
            WebDriverWait(driver, 10).until(lambda _: chrome("""
              return Services.prefs.getBoolPref('cloakfox.container.'+arguments[0]+'.override.'+arguments[1],false)===arguments[2] &&
                JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+arguments[0]))[arguments[1]]===arguments[2];
            """, owner, key, value))

        def exercise_identity_decorations(owner):
            # Canonical fonts also paint privileged content such as this real
            # Identity panel. Hover its existing underlined tools, then force
            # a skip-ink decoration on an owned text fixture and capture paint.
            driver.execute_script("location.hash='sec-identity';")
            WebDriverWait(driver,10).until(lambda d:d.find_element(By.ID,'grp-navigator').is_displayed())
            tools = [link for link in driver.find_elements(By.CSS_SELECTOR,'#grp-navigator .identity-field-tools a') if link.is_displayed()]
            if tools:
                ActionChains(driver).move_to_element(tools[0]).perform()
            driver.execute_script("""
              const p=document.createElement('p');p.id='cfx-owned-decoration-fixture';
              p.textContent='Identity glyphs gypq baseline';
              p.style='position:fixed;left:16px;top:16px;z-index:2147483647;display:block;width:max-content;margin:0;padding:4px;white-space:nowrap;font:24px serif;line-height:40px;color:black;background:white;border:0;outline:0;box-shadow:none;text-decoration-line:underline;text-decoration-style:solid;text-decoration-thickness:2px;text-decoration-skip-ink:auto;text-underline-offset:0';
              document.body.append(p);
            """)
            try:
                driver.execute_async_script('const done=arguments[arguments.length-1];requestAnimationFrame(()=>requestAnimationFrame(()=>done(true)));')
                state = driver.execute_script("""
                  const p=document.getElementById('cfx-owned-decoration-fixture'),r=p.getBoundingClientRect(),s=getComputedStyle(p);
                  return {bounds:[r.x,r.y,r.width,r.height],line:s.textDecorationLine,skipInk:s.textDecorationSkipInk};
                """)
                scale = chrome("return Services.wm.getMostRecentWindow('navigator:browser').devicePixelRatio;")
                image = Image.open(io.BytesIO(driver.get_screenshot_as_png())).convert('RGB')
                x,y,w,h = state['bounds']
                crop = image.crop((math.floor(x*scale),math.floor(y*scale),math.ceil((x+w)*scale),math.ceil((y+h)*scale)))
                crop.save(out/'identity-owned-decoration.png')
                inset = math.ceil(4*scale)
                longest = 0
                for row in range(inset,max(inset,crop.height-inset)):
                    run = 0
                    for column in range(inset,max(inset,crop.width-inset)):
                        run = run+1 if max(crop.getpixel((column,row))) < 80 else 0
                        longest = max(longest,run)
                painted = longest >= (crop.width-2*inset)*0.9
                report['identityDecoration'] = {'owner':owner,'visibleExistingTools':len(tools),
                    'style':state,'scale':scale,'longestDarkRun':longest,'cropSize':crop.size,
                    'sha256':hashlib.sha256(crop.tobytes()).hexdigest()}
                check(state['line']=='underline' and state['skipInk']=='auto' and painted,
                    'actual Identity panel and canonical skip-ink text paint an underline without a parent-process hang')
            finally:
                driver.execute_script("document.getElementById('cfx-owned-decoration-fixture')?.remove();location.hash='sec-hardening';")

        def click_mode(owner, key, value):
            control = mode(key)
            if not control.is_enabled():
                print('Disabled control: '+json.dumps(chrome("return {pipeline:Services.prefs.getBoolPref(arguments[0]),gpu:Services.prefs.getBoolPref(arguments[1])}",PIPELINE,GPU_PROFILES)),flush=True)
            check(control.is_enabled(), key + ' control is available for the selected owner')
            check(control.is_selected() != value, key + ' fixture starts in the opposite state')
            control.click()
            wait_request(owner, key, value)
            check(mode(key).is_selected() == value, key + ' real settings handler saved its checked state')

        try:
            report['runtime'] = chrome('return {version:Services.appinfo.version,buildID:Services.appinfo.appBuildID};')
            check(report['runtime']['version'].startswith('159.'), 'uses the separately selected Firefox159 application')
            fixture = chrome(r"""
              Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',false);
              Services.prefs.setBoolPref('cloakfox.opt.container_rendering_profiles',false);
              const {ContextualIdentityService:cis}=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
              const ids=['Rendering selected owner','Rendering untouched owner'].map(name=>cis.create(name,'fingerprint','blue').userContextId);
              const {fillPersonaKeys}=ChromeUtils.importESModule('resource:///modules/CloakfoxPersonas.sys.mjs');
              const o=ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs');
              const r=ChromeUtils.importESModule('resource:///modules/CloakfoxGPUReferenceProfiles.sys.mjs');
              const pair=r.REFERENCE_GPU_PROFILES.find(p=>p.family==='apple');
              if(!pair)throw Error('Missing shipped paired Apple reference fixture');
              const pinned={'webGl:vendor':pair.vendor,'webGl:renderer':pair.renderer,
                'navigator.platform':'MacIntel','navigator.oscpu':'Intel Mac OS X 10.15'};
              // Prepare every existing private test-profile owner for the real
              // global preflight, keeping its already generated seeds/secret.
              for(const name of Services.prefs.getChildList('cloakfox.s.cloak_cfg_')){
                if(!/^cloakfox\.s\.cloak_cfg_(0|[1-9]\d*)$/.test(name))continue;
                const id=Number(name.slice('cloakfox.s.cloak_cfg_'.length)),p='cloakfox.container.'+id+'.';
                const seed=Services.prefs.getStringPref(p+'math_seed');
                Services.prefs.setStringPref(p+'persona_os','macos');
                Services.prefs.setStringPref(p+'persona_hardware','apple');
                if(ids.includes(id))o.setOverrides(id,pinned);
                const raw=Uint8Array.from(atob(seed),c=>c.charCodeAt(0)),view=new DataView(raw.buffer);
                const base={'fingerprint:secret':seed,'canvas:seed':view.getUint32(0),'audio:seed':view.getUint32(4),
                  'font:seed':view.getUint32(8),'fonts:spacing_seed':view.getUint32(12),'math:trig_seed':view.getUint32(16),
                  ...fillPersonaKeys(seed,id),...pinned};
                Services.prefs.setStringPref(name,JSON.stringify(o.applyOverrides(id,base)));
              }
              const cfg=JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+ids[0]));
              const d=r.createReferenceGPUProfile({...cfg,'rendering:gpu_reference':true},ids[0]);
              return {ids,reference:{owner:d.owner,family:d.family,catalog:d.catalog,source:d.source}};
            """)
            selected, other = fixture['ids']
            owners = [selected, other]
            report['fixture'] = fixture
            load(selected)
            check(not mode(GEOMETRY).is_enabled() and not mode(REFERENCE).is_enabled(), 'dependencies off disable both inactive activation controls')
            check(not mode(GEOMETRY).is_selected() and not mode(REFERENCE).is_selected(), 'both per-owner requests default off')
            original = snapshot(owners)
            # Bypass HTML disabled only to invoke the actual onchange handler:
            # production validation must still reject before writing anything.
            driver.execute_script("const c=arguments[0];c.checked=true;c.dispatchEvent(new Event('change',{bubbles:true}));", mode(GEOMETRY))
            check(snapshot(owners) == original, 'backing-off activation is atomically rejected by the real handler')
            report['rejectedActivation'] = {'checked':mode(GEOMETRY).is_selected(), 'status':status()}
            print('Rejected activation: '+json.dumps(report['rejectedActivation']),flush=True)
            check(not mode(GEOMETRY).is_selected() and 'canonical' in status().lower(), 'invalid activation restores unchecked state and explains the dependency')

            backing(PIPELINE).click()
            WebDriverWait(driver, 10).until(lambda _: chrome('return Services.prefs.getBoolPref(arguments[0])', PIPELINE))
            check(mode(GEOMETRY).is_enabled() and not mode(REFERENCE).is_enabled(), 'canonical backing enables geometry while GPU profile dependency remains off')
            backing(GPU_PROFILES).click()
            WebDriverWait(driver, 10).until(lambda _: chrome('return Services.prefs.getBoolPref(arguments[0])', GPU_PROFILES))
            check(mode(REFERENCE).is_enabled(), 'real global GPU-profile preflight enables reference activation')
            decoration_before = snapshot(owners)
            exercise_identity_decorations(selected)
            check(snapshot(owners) == decoration_before, 'decorated Identity rendering preserves both owner records')
            # Imported/externally malformed identity must fail in the real
            # handler before it writes a request or rewrites cloak_cfg.
            prior_vendor = chrome("return Services.prefs.getStringPref('cloakfox.container.'+arguments[0]+'.override.webGl:vendor');", selected)
            chrome("Services.prefs.setStringPref('cloakfox.container.'+arguments[0]+'.override.webGl:vendor','Unpaired test fixture vendor');", selected)
            invalid = snapshot(owners)
            mode(REFERENCE).click()
            check(snapshot(owners) == invalid and not mode(REFERENCE).is_selected(), 'unpaired reference activation rejects atomically without writing either owner')
            check('BrowserForge' in status() or 'supported' in status().lower(), 'unpaired reference activation explains its unsupported identity')
            chrome("Services.prefs.setStringPref('cloakfox.container.'+arguments[0]+'.override.webGl:vendor',arguments[1]);", selected, prior_vendor)
            load(selected)
            before = snapshot(owners)
            click_mode(selected, GEOMETRY, True)
            geometry = snapshot(owners)
            check(geometry[1] == before[1], 'geometry checkbox persists only the selected owner')
            check([identity(x) for x in geometry] == [identity(x) for x in before], 'geometry checkbox preserves both owners seeds and secrets')
            check(geometry[0]['cfg'].get('rendering:geometry_profile') == {'version':1,'id':'canonical-v1','owner':selected}, 'selected geometry descriptor has exact owned metadata')
            click_mode(selected, REFERENCE, True)
            enabled = snapshot(owners)
            check(enabled[1] == before[1], 'reference checkbox leaves the other owner record unchanged')
            check([identity(x) for x in enabled] == [identity(x) for x in before], 'reference checkbox preserves both owners seeds and secrets')
            descriptor = enabled[0]['cfg'].get('rendering:gpu_profile', {})
            check(descriptor.get('owner') == selected and descriptor.get('mode') == 'reference' and bool(descriptor.get('catalog')), 'selected reference profile is paired, complete and owner-bound')
            check('Saved' in status(), 'actual handler reports per-container save and reload instructions')
            check(mode(OBSERVED).is_enabled() and not mode(OBSERVED).is_selected(), 'saved reference exposes optional observed activation')
            apple_before = snapshot(owners)
            mode(OBSERVED).click()
            check(snapshot(owners) == apple_before and not mode(OBSERVED).is_selected(), 'unsupported Apple observed activation rejects before any owner write')
            check('supported' in status().lower(), 'unsupported observed persona explains its rejection')
            # Switch only the selected fixture to a complete original Windows
            # pair. Persona constraints keep clear-all generation compatible.
            chrome("""
              const id=arguments[0],o=ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs');
              const {REFERENCE_GPU_PROFILES}=ChromeUtils.importESModule('resource:///modules/CloakfoxGPUReferenceProfiles.sys.mjs');
              const pair=REFERENCE_GPU_PROFILES.find(p=>p.family==='intel');
              Services.prefs.setStringPref('cloakfox.container.'+id+'.persona_os','windows');
              Services.prefs.setStringPref('cloakfox.container.'+id+'.persona_hardware','intel');
              o.setOverrides(id,{'webGl:vendor':pair.vendor,'webGl:renderer':pair.renderer,
                'navigator.platform':'Win32','navigator.oscpu':'Windows NT 10.0; Win64; x64'});
              const name='cloakfox.s.cloak_cfg_'+id,current=JSON.parse(Services.prefs.getStringPref(name));
              Services.prefs.setStringPref(name,JSON.stringify(o.applyOverrides(id,current)));
            """, selected)
            load(selected)
            windows_before = snapshot(owners)
            click_mode(selected, OBSERVED, True)
            observed = snapshot(owners)
            check(observed[1] == windows_before[1] and [identity(x) for x in observed] == [identity(x) for x in windows_before], 'observed activation preserves both owners and all seeds')
            d = observed[0]['cfg'].get('rendering:gpu_profile', {})
            check(d.get('version') == 4 and d.get('mode') == 'observed-reference' and d.get('owner') == selected and d.get('privacyPolicy') == 'observed-reference-v1', 'observed handler saves complete exact-owner version4 policy')
            click_mode(selected, OBSERVED, False)
            check(mode(REFERENCE).is_selected() and snapshot(owners)[0]['cfg']['rendering:gpu_profile']['version'] == 3, 'disabling observed retains the existing reference mode')
            click_mode(selected, OBSERVED, True)
            enabled = snapshot(owners)

            load(other)
            check(not mode(GEOMETRY).is_selected() and not mode(REFERENCE).is_selected(), 'selecting another container shows its separate inactive requests')
            load(selected)
            check(all(mode(key).is_selected() for key in [GEOMETRY,REFERENCE,OBSERVED]), 'all selected-owner requests survive settings reload')
            chrome('Services.prefs.savePrefFile(null);')
            driver.quit()
            driver = launch()
            load(selected)
            restored = snapshot(owners)
            check(restored == enabled, 'settings requests, independent owners and identity fields survive browser restart')
            check(all(mode(key).is_selected() for key in [GEOMETRY,REFERENCE,OBSERVED]), 'restart restores all selected-owner checkbox states')

            backing(PIPELINE).click()
            check(chrome('return Services.prefs.getBoolPref(arguments[0])', PIPELINE) is True and backing(PIPELINE).is_selected(), 'UI refuses global backing off while any saved rendering request remains')
            check(snapshot(owners) == restored, 'blocked global backing change leaves both records unchanged')
            check('Disable' in driver.find_element(By.ID, 'cfx-container-gpu-status').text, 'global backing refusal explains the required owner request changes')

            # After an external dependency failure, saved requests remain
            # checked and removable; the remaining active request fails closed.
            chrome('Services.prefs.setBoolPref(arguments[0],false);', PIPELINE)
            load(selected)
            check(all(mode(key).is_selected() and mode(key).is_enabled() for key in [GEOMETRY, REFERENCE]), 'saved checked requests can always be disabled after external backing loss')
            backing_lost = snapshot(owners)
            click_mode(selected, GEOMETRY, False)
            pending = snapshot(owners)
            check(pending[0]['cfg'].get(REFERENCE) is True and pending[0]['cfg'].get('rendering:geometry_profile', 'absent') is None, 'remaining unavailable reference request emits null geometry metadata and fails closed')
            check(pending[1] == backing_lost[1], 'backing-loss recovery remains scoped to the selected owner')
            check(not mode(GEOMETRY).is_enabled() and mode(REFERENCE).is_enabled(), 'dependency loss disables only inactive activation while keeping the saved request removable')
            click_mode(selected, REFERENCE, False)
            off = snapshot(owners)
            check(off[0]['cfg'].get(OBSERVED) is False and not mode(OBSERVED).is_selected(), 'disabling parent reference atomically disables observed during dependency loss')
            check(all(off[0]['cfg'].get(key) is False for key in [GEOMETRY, REFERENCE]), 'either requested mode can be switched off without restoring its dependency')
            check(all(not mode(key).is_enabled() and not mode(key).is_selected() for key in [GEOMETRY,REFERENCE]), 'after both requests are removed unavailable activation controls are disabled again')
            check([identity(x) for x in off] == [identity(x) for x in before], 'external-backing recovery does not rotate identity inputs')
            chrome('Services.prefs.setBoolPref(arguments[0],true);', PIPELINE)
            load(selected)
            click_mode(selected, GEOMETRY, True)
            click_mode(selected, REFERENCE, True)
            chrome('Services.prefs.setBoolPref(arguments[0],false);', PIPELINE)
            load(selected)
            reverse_lost = snapshot(owners)
            click_mode(selected, REFERENCE, False)
            reverse = snapshot(owners)
            check(reverse[0]['cfg'].get(GEOMETRY) is True and reverse[0]['cfg'].get('rendering:geometry_profile', 'absent') is None, 'reference can also be disabled first while remaining unavailable geometry metadata is null')
            check(reverse[1] == reverse_lost[1], 'reverse-order dependency recovery leaves other owner unchanged')
            click_mode(selected, GEOMETRY, False)
            check([identity(x) for x in snapshot(owners)] == [identity(x) for x in before], 'both dependency-recovery orders preserve all identity inputs')

            # Exercise clear-all through its actual button, after restoring the
            # dependency and saving a real request again.
            chrome('Services.prefs.setBoolPref(arguments[0],true);', PIPELINE)
            load(selected)
            click_mode(selected, GEOMETRY, True)
            preclear = snapshot(owners)
            print('RUN clear-overrides category navigation',flush=True)
            load(selected)
            driver.execute_script("location.hash='sec-identity'")
            WebDriverWait(driver, 10).until(lambda d: d.find_element(By.ID, 'cfx-clear-overrides').is_displayed())
            driver.find_element(By.ID, 'cfx-clear-overrides').click()
            print('RUN clear-overrides completion checks',flush=True)
            WebDriverWait(driver, 10).until(lambda _: not snapshot([selected])[0]['overrides'])
            cleared = snapshot(owners)
            check(not cleared[0]['overrides'] and GEOMETRY not in cleared[0]['cfg'] and REFERENCE not in cleared[0]['cfg'] and OBSERVED not in cleared[0]['cfg'] and 'rendering:geometry_profile' not in cleared[0]['cfg'], 'clear-overrides button removes both requests and derived geometry admission')
            check(cleared[1] == preclear[1], 'clear-overrides handler leaves the other owner untouched')
            check([identity(x) for x in cleared] == [identity(x) for x in before], 'clear-overrides handler keeps every owner seed and secret')
            check(not mode(GEOMETRY).is_selected() and not mode(REFERENCE).is_selected(), 'clear-overrides handler refreshes visible checked states')
            report['recordSHA256'] = [hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest() for row in cleared]
            report['completed'] = True
        except Exception as error:
            report['error'] = f'{type(error).__name__}: {error}'
            raise
        finally:
            driver.quit()
            report['status'] = 'PASS' if report.get('completed') and report['checks'] and all(row['pass'] for row in report['checks']) and 'error' not in report else 'FAIL'
            (out / 'result.json').write_text(json.dumps(report, indent=2)+'\n')
            print('Report: ' + str(out), flush=True)

if __name__ == '__main__':
    main()
