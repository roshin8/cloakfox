"""Collect a local GPU realism diagnostic; never certify hardware emulation.

Headless, disposable profile, authored pixels and loopback traffic only. Native
control is confined to that profile. No public reference is silently imported.
"""
import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from probe_canvas_consistency import Page
from probe_canvas_canonical_gpu import SCRIPT
from probe_webgl_backend_profile import INSPECT
from probe_container_workflows import chrome, open_site

CAPTURE_CAPS = INSPECT + "return ['webgl','webgl2'].map(kind=>{const g=document.createElement('canvas').getContext(kind);const r=inspect(g);if(g)g.getExtension('WEBGL_lose_context')?.loseContext();return r});"


def main():
    binary = os.environ['CLOAKFOX_BIN']
    out = Path(os.environ['REPORT_DIR']); out.mkdir(parents=True, exist_ok=True)
    report = {'qualification': 'Local diagnostics only; not vendor-driver emulation validation',
              'validatedEmulationProfiles': [], 'corpusSHA256': hashlib.sha256((SCRIPT+CAPTURE_CAPS).encode()).hexdigest(), 'samples': {}}
    server = ThreadingHTTPServer(('127.0.0.1', 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='cfx159-gpu-reference-') as profile:
            options = Options(); options.binary_location = binary
            for arg in ['-headless', '-profile', profile]: options.add_argument(arg)
            for key, value in {'cloakfox.enabled':False, 'dom.webgpu.enabled':True,
                'layers.gpu-process.allow-headless':True}.items(): options.set_preference(key,value)
            d = webdriver.Firefox(options=options,service=Service(os.environ.get('GECKODRIVER','/opt/homebrew/bin/geckodriver'),service_args=['--allow-system-access'],log_output=str(out/'gecko.log')))
            try:
                d.set_script_timeout(120)
                report['runtime'] = chrome(d,'return {version:Services.appinfo.version,buildID:Services.appinfo.appBuildID}')
                assert report['runtime']['version'].startswith('159.')
                d.set_context('content')
                d.get(f'http://127.0.0.1:{server.server_port}/')
                report['samples']['native'] = {'caps':d.execute_script(CAPTURE_CAPS),'render':d.execute_async_script(SCRIPT)}
                families = [('apple','macos'),('intel','windows'),('amd','windows'),('nvidia','windows')]
                ids = chrome(d,"return Array.from({length:4},(_,i)=>cis.create('GPU reference '+i,'fingerprint','blue').userContextId)")
                # Preflight all existing owners using eligible personas, preserving
                # their actual secrets. No identity or seed leaves the browser.
                chrome(d,"""const p=ChromeUtils.importESModule('resource:///modules/CloakfoxPersonas.sys.mjs');for(const key of Services.prefs.getChildList('cloakfox.s.cloak_cfg_')){const id=Number(key.slice('cloakfox.s.cloak_cfg_'.length)),old=JSON.parse(Services.prefs.getStringPref(key)),next=p.fillPersonaKeys('B'.repeat(43)+'=',id,{os:'windows',hardware:'nvidia'});for(const[k,v]of Object.entries(old))if(/seed|secret/i.test(k))next[k]=v;next['navigator:webgpu:disabled']=false;Services.prefs.setStringPref(key,JSON.stringify(next));}Services.prefs.setBoolPref('cloakfox.enabled',true);Services.prefs.setBoolPref('cloakfox.experimental.canvas_pipeline',true);ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs').setContainerGPUProfilesEnabled(true);""")
                for owner,(family,platform) in zip(ids,families):
                    # The shared tab helper locates ownership by exact URL.
                    # Keep each diagnostic tab distinct from the native control.
                    _, actual = open_site(d,f'http://127.0.0.1:{server.server_port}/?owner={owner}',owner); assert actual==owner
                    chrome(d,"""const id=arguments[0],p=ChromeUtils.importESModule('resource:///modules/CloakfoxPersonas.sys.mjs'),o=ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs'),key='cloakfox.s.cloak_cfg_'+id,old=JSON.parse(Services.prefs.getStringPref(key)),next=p.fillPersonaKeys('B'.repeat(43)+'=',id,{os:arguments[1],hardware:arguments[2]});for(const[k,v]of Object.entries(old))if(/seed|secret/i.test(k))next[k]=v;next['navigator:webgpu:disabled']=false;Services.prefs.setStringPref(key,JSON.stringify(o.applyGraphicsPolicy(next,id)));""",owner,platform,family)
                    d.set_context('content');d.refresh()
                    sample = {'owner':owner,'caps':d.execute_script(CAPTURE_CAPS),'render':d.execute_async_script(SCRIPT)}
                    assert all(not c.get('missing') for c in sample['caps'])
                    assert all(sample['render'].get(api,{}).get('available') for api in ['webgl','webgl2','webgpu']),sample['render']
                    report['samples'][family] = sample
                report['comparisonsToLocalControl'] = {}
                for family,_ in families:
                    sample = report['samples'][family]; native = report['samples']['native']
                    comparison = {}
                    for index,api in enumerate(['webgl','webgl2']):
                        a,b = native['render'][api]['pixels'],sample['render'][api]['pixels']
                        assert len(a)==len(b)==256
                        comparison[api] = {'differentChannels':sum(x!=y for x,y in zip(a,b)),
                            'maxChannelDifference':max(abs(x-y) for x,y in zip(a,b)),
                            'differentCapabilityFields':[k for k,v in native['caps'][index]['caps'].items() if sample['caps'][index]['caps'].get(k)!=v]}
                    report['comparisonsToLocalControl'][family] = comparison
                print(json.dumps(report['comparisonsToLocalControl'],indent=2))
                print('DIAGNOSTIC COMPLETE: four owned profiles measured; vendor emulation remains unvalidated')
            finally: d.quit()
    finally:
        server.shutdown();server.server_close()
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__': main()
