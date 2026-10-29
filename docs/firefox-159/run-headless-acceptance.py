"""Disposable runner for the explicit159 build; never uses installed apps."""
import os,sys,json,subprocess,time,datetime
from pathlib import Path
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'tests/fingerprint'))
import run_all
plan=json.loads((root/'docs/firefox-159/headless-test-plan.json').read_text())
output=root/'tests/fingerprint/reports/firefox159-headless';output.mkdir(parents=True,exist_ok=True)
status=root/'docs/firefox-159/headless-test-status.json'
obj=root/'firefox-src/obj-aarch64-apple-darwin'
binary=root/'firefox-src/.tools159/acceptance-viewport/Cloakfox.app/Contents/MacOS/cloakfox'
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

identity=subprocess.run([str(binary),'-headless','--version'],cwd=root,env=env,capture_output=True,text=True,timeout=30)
assert identity.returncode==0 and '159.0' in identity.stdout,(identity.returncode,identity.stdout,identity.stderr)
(output/'binary-version.txt').write_text(identity.stdout+identity.stderr)
os.environ.clear();os.environ.update(env)
priority=['probe_privileged_viewport.py','probe_network_identity.py','probe_realm_privacy.py','probe_language_scopes.py','probe_worker_debugger_startup.py','probe_navigator_coherence.py','probe_webgpu_null_safety.py','probe_site_data_scope.py','probe_site_data_cache_scope.py']
paths=[root/'tests/fingerprint'/n for n in plan['selected']]
paths.sort(key=lambda p:(priority.index(p.name) if p.name in priority else len(priority),p.name))
result={'state':'testing','binary':str(binary),'headless':True,'version':identity.stdout.strip(),'started':datetime.datetime.now(datetime.timezone.utc).isoformat(),'deferred':plan['deferred'],'results':[]}
def save():status.write_text(json.dumps(result,indent=2)+'\n')
save()
for path in paths:
 start=time.monotonic();print('RUN',path.name,flush=True)
 code,text=run_all.run_probe(path,900)
 entry={'probe':path.name,'code':code,'outcome':'passed' if code==0 else 'inconclusive' if code==2 else 'failed','seconds':round(time.monotonic()-start,2)}
 result['results'].append(entry);save();print(entry,flush=True)
# Audit libraries separately, retaining failures/inconclusives as such.
for canonical in ('0','1'):
 mode_output=output/('library-audit-canonical-'+canonical);mode_output.mkdir(exist_ok=True)
 library_env=dict(env,CLOAKFOX_TEST_CANVAS_PIPELINE=canonical,REPORT_DIR=str(mode_output),PROBE_REPORT_ROOT=str(mode_output))
 os.environ.clear();os.environ.update(library_env)
 code,text=run_all.run_probe(root/'tests/fingerprint/probe_fingerprint_libraries.py',2100)
 (mode_output/'probe-output.txt').write_text(text)
 result['results'].append({'probe':'fingerprint-libraries-canonical-'+canonical,'code':code,'outcome':'passed' if code==0 else 'inconclusive' if code==2 else 'failed'});save()
# Browser-backed pytest tests use the same explicit new binary and owned profiles.
wrapper=output/'firefox159_pytest_runtime.py'
wrapper.write_text("import pytest,sys\nfrom pathlib import Path\nroot=Path("+repr(str(root))+")\nsys.exit(pytest.main(['--noconftest','-q',*[str(p) for p in sorted((root/'tests/fingerprint').glob('test_*.py'))]]))\n")
os.environ.clear();os.environ.update(env)
code,text=run_all.run_probe(wrapper,2100)
(output/'pytest-runtime-output.txt').write_text(text)
result['results'].append({'probe':'fingerprint-pytest-runtime','code':code,'outcome':'passed' if code==0 else 'failed'});save()
result['state']='passed' if all(x['code']==0 for x in result['results']) else 'needs-attention'
result['finished']=datetime.datetime.now(datetime.timezone.utc).isoformat();save();print(result['state'],flush=True)

sys.exit(0 if result['state']=='passed' else 1)
