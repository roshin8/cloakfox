"""Run scoped privacy/persistence regressions on the owned headless159 app."""
import hashlib,json,os,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'tests/fingerprint'))
import run_all
out=root/'tests/fingerprint/reports/firefox159-fpgen-personas'
out.mkdir(parents=True,exist_ok=True)
binary=root/'firefox-src/.tools159/acceptance-fpgen-personas/Cloakfox.app/Contents/MacOS/cloakfox'
os.environ.update(CLOAKFOX_BIN=str(binary),MOZ_HEADLESS='1',MOZ_REMOTE_ALLOW_SYSTEM_ACCESS='1',GECKODRIVER='/opt/homebrew/bin/geckodriver',PROBE_REPORT_ROOT=str(out))
for name in ['CLOAKFOX_HEADFUL','CLOAK_CONFIG','CLOAK_CONFIG_1']:os.environ.pop(name,None)
result={'headless':True,'binary':str(binary),'probes':[]}
for name in ['probe_host_personas.py','probe_persona_generation.py','probe_templates.py',
             'probe_container_rendering_settings.py','probe_identity_network_gaps.py',
             'probe_container_fonts.py','probe_webgl_readback.py']:
    print('RUN',name,flush=True)
    os.environ['REPORT_DIR']=str(out/name.removesuffix('.py'))
    started=time.monotonic()
    code,output=run_all.run_probe(root/'tests/fingerprint'/name,600)
    (out/(name+'.log')).write_text(output)
    result['probes'].append({'probe':name,'exitCode':code,'seconds':round(time.monotonic()-started,2)})
    (root/'docs/firefox-159/fpgen-personas/regressions.json').write_text(json.dumps(result,indent=2)+'\n')
    print(name,code,flush=True)
    if code:print(output[-2500:],flush=True)
sys.exit(0 if all(p['exitCode']==0 for p in result['probes']) else 1)
