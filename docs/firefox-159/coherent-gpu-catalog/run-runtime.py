"""Disposable runner for the explicit159 build; never uses installed apps."""
import os,sys,json,subprocess,time,datetime
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'tests/fingerprint'))
import run_all
plan=json.loads((root/'docs/firefox-159/headless-test-plan.json').read_text())
output=root/'tests/fingerprint/reports/firefox159-coherent-gpu';output.mkdir(parents=True,exist_ok=True)
status=root/'docs/firefox-159/headless-test-status.json'
obj=root/'firefox-src/obj-aarch64-apple-darwin'
binary=root/'firefox-src/.tools159/acceptance-coherent-gpu/Cloakfox.app/Contents/MacOS/cloakfox'
assert binary.is_file(),'Self-contained Firefox159 acceptance binary missing'
assert json.loads((root/'docs/firefox-159/build-status.json').read_text())['state']=='built','Native build has not passed'
env=dict(os.environ,MOZ_HEADLESS='1',MOZ_REMOTE_ALLOW_SYSTEM_ACCESS='1',LIBRARY_HEADLESS='1',CLOAKFOX_BIN=str(binary),GECKODRIVER='/opt/homebrew/bin/geckodriver',SE_GECKODRIVER='/opt/homebrew/bin/geckodriver',PROBE_REPORT_ROOT=str(output))
env.pop('CLOAKFOX_HEADFUL',None)
for name in ('ALPS_CHROME_REFERENCE','SIGNATURE_CHROME_REFERENCE','FIREFOX158_STOCK_ONLY','CLOAK_CONFIG','CLOAK_CONFIG_1'):
 env.pop(name,None)
env['ALPS_SERVER']=str(root/'firefox-src/.tools159/alps-fixture/alps-server')
env['MONACO_PROBE_ASSETS']=str(root/'firefox-src/.tools159/monaco-probe-assets')
env['POINTER_PROBE_INPUT']='widget'
env['FIREFOX_BIN']=str(root/'firefox-src/.tools159/stock159/Firefox.app/Contents/MacOS/firefox')
env.update(CLOAKFOX_XPCSHELL=str(obj/'dist/bin/xpcshell'),CANONICAL_CODEC_SOURCE_DIR=str(root/'firefox-src'),CANONICAL_CODEC_LIB_DIR=str(obj/'dist/bin'),CLOAKFOX_CANONICAL_GPU_DIR=str(binary.parents[1]/'Resources/canonical-gpu'))

os.environ.clear();os.environ.update(env)
result=[]
for name in ['probe_container_gpu_profiles.py','probe_canvas_canonical_gpu.py','probe_container_rendering_feasibility.py','probe_webgl_backend_profile.py','probe_webgpu_canvas_owner.py','probe_canvas_owner_transfer.py','probe_strict_graphics_settings.py','probe_graphics_optins_settings.py','probe_graphics_privacy.py','probe_webgl_readback.py']:
 print('RUN',name,flush=True)
 code,text=run_all.run_probe(root/'tests/fingerprint'/name,900)
 (output/(name+'.log')).write_text(text)
 result.append({'probe':name,'code':code});(root/'docs/firefox-159/coherent-gpu-catalog/runtime.json').write_text(json.dumps(result,indent=2)+'\n')
 print(name,code,flush=True)
for canonical in ('0','1'):
 name='libraries-canonical-'+canonical
 mode=output/name;mode.mkdir(exist_ok=True)
 os.environ.clear();os.environ.update(env)
 os.environ.update(LIBRARY_WEBGPU_ENABLED='1',LIBRARY_CONTAINER_GPU_PROFILES=canonical,CLOAKFOX_TEST_CANVAS_PIPELINE=canonical,REPORT_DIR=str(mode),PROBE_REPORT_ROOT=str(mode))
 print('RUN',name,flush=True)
 code,text=run_all.run_probe(root/'tests/fingerprint/probe_fingerprint_libraries.py',2100)
 (mode/'output.log').write_text(text)
 result.append({'probe':name,'code':code});(root/'docs/firefox-159/coherent-gpu-catalog/runtime.json').write_text(json.dumps(result,indent=2)+'\n')
 print(name,code,flush=True)
sys.exit(0 if all(x['code']==0 for x in result) else 1)
