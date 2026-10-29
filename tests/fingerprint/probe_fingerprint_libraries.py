"""Run pinned, unmodified upstream CreepJS and FingerprintJS in real Cloakfox.

Requires scripts/setup-fingerprint-libraries.py. Temporary profiles, local HTTP
pages, no media grants. Upstream CreepJS may attempt its usual STUN probe; native
browser protection remains in force. All upstream detection flags are retained.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait

from library_audit_common import ROOT, LIB, CREEP, MANIFEST, FP_BUNDLE, Handler, stable_hash, verify_fixtures, observed_gpu_recognized


def main():
    binary = os.environ.get('CLOAKFOX_BIN', '/Applications/Cloakfox.app/Contents/MacOS/cloakfox')
    container_profiles = os.environ.get('LIBRARY_CONTAINER_GPU_PROFILES','0') == '1'
    reference_layout = os.environ.get('LIBRARY_REFERENCE_LAYOUT', '0') == '1'
    observed_gpu = os.environ.get('LIBRARY_OBSERVED_GPU', '0') == '1'
    if observed_gpu and not reference_layout:
        raise ValueError('LIBRARY_OBSERVED_GPU requires LIBRARY_REFERENCE_LAYOUT=1')
    webgpu_enabled = os.environ.get('LIBRARY_WEBGPU_ENABLED', '0') == '1' or reference_layout
    graphics_modes = {
        'canvas_render_privacy': os.environ.get('LIBRARY_CANVAS_RENDER_PRIVACY', '0') == '1',
        'gpu_backend_profiles': os.environ.get('LIBRARY_GPU_BACKEND_PROFILES', '0') == '1',
        'canonical_2d': os.environ.get('CLOAKFOX_TEST_CANVAS_PIPELINE', '0') == '1',
    }
    if reference_layout and not (container_profiles and graphics_modes['canonical_2d']):
        raise ValueError('LIBRARY_REFERENCE_LAYOUT requires LIBRARY_CONTAINER_GPU_PROFILES=1 and CLOAKFOX_TEST_CANVAS_PIPELINE=1')
    out = Path(os.environ.get('REPORT_DIR', ROOT / 'tests/fingerprint/reports/fingerprint-libraries'))
    out.mkdir(parents=True, exist_ok=True)
    repeats = int(os.environ.get('LIBRARY_REPEATS', '3'))
    assert repeats >= 3, 'At least three reload samples required'
    assert Path(binary).is_file(), 'Required Gecko binary is missing'
    provenance = {**verify_fixtures(), 'binary': binary, 'graphicsModes': graphics_modes,
                  'webgpuEnabled': webgpu_enabled, 'containerGPUProfiles': container_profiles,
                  'referenceLayout': reference_layout, 'observedGPU': observed_gpu}
    (out / 'upstreams.json').write_text(json.dumps(provenance, indent=2))
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(CREEP / 'docs')))
    server.requests = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    cases, checks = [], []

    def check(ok, label, detail=None):
        checks.append({'pass': bool(ok), 'label': label, 'detail': detail})
        print(('PASS ' if ok else 'FAIL ') + label, flush=True)

    def save():
        (out / 'results.json').write_text(json.dumps({'provenance': provenance, 'cases': cases,
                                                     'checks': checks, 'requests': server.requests}, indent=2))

    try:
        for enabled in [True, False]:
            with tempfile.TemporaryDirectory(prefix='cfx-library-audit-') as temp:
                options = Options()
                options.binary_location = binary
                options.add_argument('-profile')
                options.add_argument(temp)
                options.add_argument('-no-remote')
                if os.environ.get('LIBRARY_HEADLESS') == '1':
                    options.add_argument('--headless')
                options.set_preference('remote.prefs.recommended', False)
                options.set_preference('cloakfox.enabled', enabled)
                options.set_preference('privacy.resistFingerprinting', False)
                if webgpu_enabled:
                    options.set_preference('dom.webgpu.enabled', True)
                    if os.environ.get('MOZ_HEADLESS') == '1':
                        options.set_preference('layers.gpu-process.allow-headless', True)
                for name, value in graphics_modes.items():
                    options.set_preference('cloakfox.experimental.canvas_pipeline' if name == 'canonical_2d' else 'cloakfox.opt.' + name, value)
                driver = webdriver.Firefox(options=options, service=Service(
                    os.environ.get('GECKODRIVER') or shutil.which('geckodriver'), service_args=['--allow-system-access'],
                    log_output=str(out / ('protected-gecko.log' if enabled else 'native-gecko.log'))))
                driver.set_page_load_timeout(40)
                driver.set_script_timeout(60)

                def chrome(script, *args):
                    driver.set_context('chrome')
                    try:
                        return driver.execute_script(script, *args)
                    finally:
                        driver.set_context('content')

                try:
                    provenance['runtime'] = chrome('return {version:Services.appinfo.version,buildID:Services.appinfo.appBuildID,os:Services.appinfo.OS}')
                    definitions = [('native', 0, '127.0.0.1')]
                    if enabled:
                        ids = chrome('''const m=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');return ['A','B','Chrome'].map(n=>m.ContextualIdentityService.create('Library '+n,'fingerprint','blue').userContextId)''')
                        chrome('''const ids=arguments[0];const p=ChromeUtils.importESModule('resource:///modules/CloakfoxPersonas.sys.mjs');
                          const base=JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_0'));
                          const seed=Services.prefs.getStringPref('cloakfox.container.0.math_seed');
                          Object.assign(base,p.fillPersonaKeys(seed,0,{os:'windows',hardware:'nvidia'}));
                          for(const id of [0,...ids]){
                            const original=JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+id));
                            const cfg={...base};for(const [key,value] of Object.entries(original))if(/seed|secret/i.test(key))cfg[key]=value;
                            if(id===ids[2]){const ua='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36';Object.assign(cfg,{'navigator.userAgent':ua,'headers.User-Agent':ua,'navigator.appVersion':ua.slice(8)})}
                            Services.prefs.setStringPref('cloakfox.s.cloak_cfg_'+id,JSON.stringify(cfg));
                          }''', ids)
                        definitions = [('default', 0, '127.0.0.1'), ('A', ids[0], '127.0.0.1'),
                                       ('B', ids[1], '127.0.0.1'), ('A-other-site', ids[0], 'localhost'),
                                       ('Chrome', ids[2], '127.0.0.1'), ('Chrome-other-site', ids[2], 'localhost'), ('A-return', ids[0], '127.0.0.1')]
                    if enabled and container_profiles:
                        chrome('''const m=ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs');
                          const p=ChromeUtils.importESModule('resource:///modules/CloakfoxPersonas.sys.mjs');
                          for(const key of Services.prefs.getChildList('cloakfox.s.cloak_cfg_')){
                            const id=Number(key.slice('cloakfox.s.cloak_cfg_'.length)),c=JSON.parse(Services.prefs.getStringPref(key));
                            if(![0,...arguments[0]].includes(id)){
                              const n=p.fillPersonaKeys('B'.repeat(43)+'=',id,{os:'windows',hardware:'nvidia'});
                              for(const [k,v]of Object.entries(c))if(/seed|secret/i.test(k))n[k]=v;
                              Services.prefs.setStringPref(key,JSON.stringify(n));
                            }
                          }
                          m.setContainerGPUProfilesEnabled(true);
                          for(const key of Services.prefs.getChildList('cloakfox.s.cloak_cfg_')){
                            const id=Number(key.slice('cloakfox.s.cloak_cfg_'.length));
                            Services.prefs.setStringPref(key,JSON.stringify(m.applyGraphicsPolicy(JSON.parse(Services.prefs.getStringPref(key)),id)));
                          }''',ids)
                    if enabled and reference_layout:
                        chrome('''const {REFERENCE_GPU_PROFILES}=ChromeUtils.importESModule('resource:///modules/CloakfoxGPUReferenceProfiles.sys.mjs');
                          const m=ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs');
                          for(const id of [0,...arguments[0]]){
                            const family=arguments[1]&&id===arguments[0][0]?'intel':arguments[1]&&id===arguments[0][1]?'amd':'nvidia';
                            const ref=REFERENCE_GPU_PROFILES.find(p=>p.family===family&&p.os==='win');
                            if(!ref)throw Error('Recorded Windows '+family+' reference fixture is missing');
                            const key='cloakfox.s.cloak_cfg_'+id,c=JSON.parse(Services.prefs.getStringPref(key));
                            Object.assign(c,{'webGl:renderer':ref.renderer,'webGl:vendor':ref.vendor,
                              'navigator.platform':'Win32','navigator.oscpu':'Windows NT 10.0; Win64; x64',
                              'rendering:gpu_reference':true,'rendering:gpu_observed':arguments[1],'geometry:canonical':true,'navigator:webgpu:disabled':false});
                            Services.prefs.setStringPref(key,JSON.stringify(m.applyGraphicsPolicy(c,id)));
                          }''', ids, observed_gpu)
                    for label, container, host in definitions:
                        before = set(driver.window_handles)
                        chrome('''const w=Services.wm.getMostRecentWindow('navigator:browser');w.gBrowser.selectedTab=w.gBrowser.addTab('about:blank',{userContextId:arguments[0],triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()})''', container)
                        handle = WebDriverWait(driver, 15).until(lambda d: next(iter(set(d.window_handles)-before), False))
                        driver.switch_to.window(handle)
                        case = {'case': label, 'container': container, 'host': host, 'protected': enabled, 'libraries': {}}
                        cases.append(case)
                        if enabled and webgpu_enabled:
                            chrome('''const key='cloakfox.s.cloak_cfg_'+arguments[0];
                              const cfg=JSON.parse(Services.prefs.getStringPref(key));
                              cfg['navigator:webgpu:disabled']=false;
                              Services.prefs.setStringPref(key,JSON.stringify(cfg));''', container)
                        if enabled:
                            if reference_layout:
                                case['referenceLayout'] = chrome('''const c=JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+arguments[0]));
                                  return {referenceRequested:c['rendering:gpu_reference']===true,geometryRequested:c['geometry:canonical']===true,
                                    gpu:c['rendering:gpu_profile'],geometry:c['rendering:geometry_profile']};''', container)
                                mode = case['referenceLayout']
                                check(mode['referenceRequested'] and mode['geometryRequested']
                                      and mode.get('gpu', {}).get('mode') == ('observed-reference' if observed_gpu else 'reference')
                                      and mode['gpu'].get('owner') == container
                                      and mode.get('geometry') == {'version':1,'id':'canonical-v1','owner':container},
                                      label + ': reference GPU and canonical geometry requests have exact owned descriptors')
                            case['graphicsModes'] = chrome('''const cfg=JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_'+arguments[0]));
                              return {canvas_render_privacy:cfg['canvas:render_privacy']===true,
                                      gpu_backend_profiles:cfg['webGl:backend_profile']===true,
                                      canonical_2d:cfg['canvas:canonical_2d']===true}''', container)
                            check(case['graphicsModes'] == {**graphics_modes,'gpu_backend_profiles':graphics_modes['gpu_backend_profiles'] or graphics_modes['canonical_2d']},
                                  label + ': requested graphics policy reaches owning container')
                        for library, path, ready, result in [
                            ('fingerprintjs', '/fp.html', 'return !!window.libraryResult', 'return window.libraryResult'),
                            ('creepjs', '/index.html', 'return !!window.Fingerprint&&!!window.Creep', 'return {fingerprint:window.Fingerprint,creep:window.Creep}')]:
                            samples = []
                            case['libraries'][library] = samples
                            for repeat in range(repeats):
                                print(f'RUN {label}/{library}/{repeat}', flush=True)
                                url = f'http://{host}:{server.server_port}{path}'
                                driver.get(url)
                                WebDriverWait(driver, 60).until(lambda d: d.current_url == url and d.execute_script(ready))
                                value = driver.execute_script(result)
                                check(isinstance(value, dict) and 'error' not in value, f'{label}/{library}/{repeat} completes')
                                samples.append(value)
                                (out / f'{label}-{library}-{repeat}.json').write_text(json.dumps(value, indent=2))
                                save()
                            if library == 'fingerprintjs':
                                check(all(isinstance(x.get('components', {}).get('audio', {}).get('value'), (int, float)) and x['components']['audio']['value'] > 0 for x in samples), f'{label}: FingerprintJS audio is a real sample')
                                check(all(x['rawCanvas']['geometry'].startswith('data:image/') and x['rawCanvas']['text'].startswith('data:image/') for x in samples), f'{label}: FingerprintJS raw canvas images collected')
                                check(len({stable_hash(x['rawCanvas']) for x in samples}) == 1, f'{label}: FingerprintJS raw canvas reload stability')
                                check(all(isinstance(x.get('visitorId'), str) and re.fullmatch(r'[0-9a-f]{32}', x['visitorId']) for x in samples), f'{label}: FingerprintJS visitor IDs are populated')
                                check(len({x.get('visitorId') for x in samples}) == 1, f'{label}: FingerprintJS visitor ID reload stability')
                                for component in ['canvas', 'audio', 'timezone', 'platform', 'screenResolution']:
                                    entries = [x.get('components', {}).get(component, {}) for x in samples]
                                    check(all('value' in x and x['value'] is not None and 'error' not in x for x in entries), f'{label}: FingerprintJS {component} successful value')
                                    if component == 'canvas':
                                        case['fingerprintjsCanvasStatus'] = [x.get('value', {}) for x in entries]
                                    values = [stable_hash(x.get('value')) for x in entries]
                                    check(len(set(values)) == 1, f'{label}: FingerprintJS {component} reload stability')
                            else:
                                if webgpu_enabled:
                                    gpu_values = [x['fingerprint'].get('navigator', {}).get('webgpu') for x in samples]
                                    check(all(isinstance(g, dict) and len(g.get('adapterInfo', [])) == 4 and g.get('limits') for g in gpu_values),
                                          f'{label}: CreepJS collects enabled WebGPU adapter and limits')
                                    check(len({stable_hash(g) for g in gpu_values}) == 1,
                                          f'{label}: WebGPU adapter and limits reload stability')
                                for component in ['canvas2d', 'offlineAudioContext', 'cssMedia', 'screen', 'navigator', 'workerScope']:
                                    values = [x['fingerprint'].get(component, {}).get('$hash') for x in samples]
                                    check(all(values), f'{label}: CreepJS {component} collected')
                                    case.setdefault('creepReloadHashes', {})[component] = values
                                    if component != 'canvas2d':
                                        check(len(set(values)) == 1, f'{label}: CreepJS {component} reload stability')
                                for field in ['dataURI', 'paintURI', 'paintCpuURI', 'textURI', 'emojiURI']:
                                    values = [x['fingerprint']['canvas2d'].get(field) for x in samples]
                                    check(all(isinstance(x, str) and x.startswith('data:image/') for x in values), f'{label}: CreepJS {field} image collected')
                                    check(len(set(values)) == 1, f'{label}: CreepJS {field} reload stability')
                                for value in samples:
                                    f=value['fingerprint'];css=f['cssMedia'];a=css['mediaCSS'];b=css['matchMediaCSS']
                                    check(bool(a) and a.keys()==b.keys() and {'color-gamut','device-screen','prefers-reduced-motion','forced-colors'} <= a.keys() and all(a[key]==b[key] for key in a), f'{label}: CreepJS stylesheet and matchMedia agree')
                                    n=f['navigator'];w=f['workerScope']
                                    check(n.get('platform')==w.get('platform') and n.get('hardwareConcurrency')==w.get('hardwareConcurrency'), f'{label}: CreepJS window and worker identity agree')
                                    if enabled:
                                        check(n.get('system')=='Windows' and w.get('system')=='Windows' and w.get('timezoneLocation')=='UTC', f'{label}: CreepJS reports selected OS and timezone')
                                        check(all('Microsoft' in voice for voice in f['voices']['local']) and bool(f['voices']['local']), f'{label}: CreepJS voice family matches Windows')
                        driver.close()
                        driver.switch_to.window(next(iter(before)))
                        save()
                finally:
                    driver.quit()
        by_name = {x['case']: x for x in cases}
        for left, right in [('default', 'A'), ('A', 'B'), ('A', 'A-other-site'), ('Chrome', 'Chrome-other-site')]:
            for component in ['canvas', 'audio']:
                a = by_name[left]['libraries']['fingerprintjs'][0]
                b = by_name[right]['libraries']['fingerprintjs'][0]
                av = a['rawCanvas'] if component == 'canvas' else a['components'][component]['value']
                bv = b['rawCanvas'] if component == 'canvas' else b['components'][component]['value']
                standardized=graphics_modes['canonical_2d'] and component=='canvas'
                if standardized:
                    provenance.setdefault('canonicalCrossScopePixels', []).append({'pair':[left,right], 'library':'fingerprintjs', 'equal':av==bv})
                else:
                    check(av!=bv, f'{left}/{right}: FingerprintJS {component} isolation')
            for component, field in [('canvas2d', 'dataURI'), ('offlineAudioContext', '$hash')]:
                a=by_name[left]['libraries']['creepjs'][0]['fingerprint'][component][field]
                b=by_name[right]['libraries']['creepjs'][0]['fingerprint'][component][field]
                standardized=graphics_modes['canonical_2d'] and component=='canvas2d'
                if standardized:
                    provenance.setdefault('canonicalCrossScopePixels', []).append({'pair':[left,right], 'library':'creepjs', 'equal':a==b})
                else:
                    check(a!=b, f'{left}/{right}: CreepJS {component} isolation')
        for library in ['fingerprintjs', 'creepjs']:
            a=by_name['A']['libraries'][library][0];b=by_name['A-return']['libraries'][library][0]
            if library=='fingerprintjs':
                check(a['visitorId']==b['visitorId'] and a['rawCanvas']==b['rawCanvas'], 'Return to original site restores FingerprintJS identity')
            else:
                check(a['fingerprint']['canvas2d']['dataURI']==b['fingerprint']['canvas2d']['dataURI'] and a['fingerprint']['offlineAudioContext']['$hash']==b['fingerprint']['offlineAudioContext']['$hash'], 'Return to original site restores CreepJS canvas/audio')
        native=by_name['native']['libraries']['creepjs'][0]['fingerprint']
        expected_system={'Darwin':'Mac','Linux':'Linux','WINNT':'Windows'}.get(provenance['runtime']['os'])
        check(expected_system is not None and native['navigator']['system']==native['workerScope']['system']==expected_system, 'Master-off native control exposes its real platform')
        for name in ['default','A','B','Chrome']:
            f=by_name[name]['libraries']['creepjs'][0]['fingerprint']
            check(f['canvas2d']['dataURI']!=native['canvas2d']['dataURI'] and f['offlineAudioContext']['$hash']!=native['offlineAudioContext']['$hash'], name+': protected output differs from native control')
        if observed_gpu:
            for case in cases:
                if not case['protected']:
                    continue
                for index, sample in enumerate(case['libraries']['creepjs']):
                    warnings = sample['fingerprint'].get('trash', {}).get('trashBin', [])
                    flagged = [w for w in warnings if w.get('value') in ['suspicious gpu', 'suspicious capabilities']]
                    check(observed_gpu_recognized(sample['fingerprint']), f"{case['case']}/{index}: complete unmodified CreepJS collection recognizes observed GPU and capabilities", flagged)
        save()
        failures = [x for x in checks if not x['pass']]
        (out / 'summary.json').write_text(json.dumps({'cases': len(cases), 'repeats': repeats, 'checks': len(checks),
            'failures': failures, 'libraryExecutions': sum(len(s) for c in cases for s in c['libraries'].values())}, indent=2))
        assert not failures, failures
    except BaseException as error:
        check(False, 'library audit completed', str(error))
        save()
        (out / 'summary.json').write_text(json.dumps({'success': False, 'error': str(error),
            'cases': len(cases), 'checks': checks}, indent=2))
        raise
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
