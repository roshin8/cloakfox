"""Preserving source-framework build and owned identity/runtime verification.

A single locked pipeline; no original SDK/app is replaced. Failures keep objects,
logs, candidate SDK and status for diagnosis. Local app installation and commits
happen only after inspecting successful runtime results.
"""
import argparse
import ast
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time


def digest(path):
    with Path(path).open('rb') as source: return hashlib.file_digest(source, 'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source-root','build-root','sdk-template','tools-root','test-python','wire-python'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--jobs',type=int,default=6)
    parser.add_argument('--patch-lock',default='identity-patch-lock.json')
    parser.add_argument('--artifact-prefix',default='identity')
    args=parser.parse_args()
    if not 1<=args.jobs<=16:parser.error('jobs must be 1–16')
    if not re.fullmatch('[a-z][a-z0-9-]{0,47}',args.artifact_prefix):parser.error('Invalid artifact prefix')
    if '/' in args.patch_lock or not args.patch_lock.endswith('-patch-lock.json'):parser.error('Invalid native patch lock')
    prefix=args.artifact_prefix
    repo=Path(__file__).resolve().parents[2];root=args.build_root.resolve(strict=True)
    source=args.source_root.resolve(strict=True);tools=args.tools_root.resolve(strict=True)
    out=root/'out/Release_GN_arm64';sdk=root/(prefix+'-built-sdk');build=root/(prefix+'-companion-build')
    status=root/(prefix+'-build-status.json');logs=root/'logs';logs.mkdir(exist_ok=True)
    with (root/'.identity-pipeline.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('Identity pipeline already running; inspect existing status')
        data={'state':'running','stage':'starting','pid':os.getpid(),'started':time.time(),
              'sourceRoot':str(source),'outputRoot':str(out),'sdk':str(sdk),
              'runtimeTestsPassed':False,'preservesExistingSdkAndApp':True}
        def update(**fields):
            data.update(fields);temporary=status.with_suffix('.pending');temporary.write_text(json.dumps(data,indent=2)+'\n');temporary.replace(status)
        def stage(name,command,env=None):
            log=logs/(prefix+'-'+name+'.log')
            update(stage=name,log=str(log),stageStarted=time.time())
            with log.open('a') as output:
                output.write('\nStage invocation '+time.strftime('%Y-%m-%dT%H:%M:%S%z')+'\n');output.flush()
                process=subprocess.Popen([str(item) for item in command],cwd=repo,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT)
                update(childPid=process.pid)
                code=process.wait()
            if code:raise RuntimeError(f'{name} failed with code {code}; inspect {log}')
            update(lastPassed=name)
        env={**os.environ,'PATH':str(tools/'depot_tools')+os.pathsep+os.environ['PATH'],
             'DEPOT_TOOLS_UPDATE':'0','CIPD_CACHE_DIR':str(tools/'cache/cipd'),
             'VPYTHON_VIRTUALENV_ROOT':str(tools/'cache/vpython')}
        try:
            update()
            lock_hash=digest(repo/'engines/chromium'/args.patch_lock)
            stage('source-hashes',[sys.executable,repo/'engines/chromium/apply_identity_patch.py','--source-root',source,'--check','--lock',args.patch_lock])
            stage('framework',[source/'third_party/ninja/ninja','-C',out,'cef_framework','-j'+str(args.jobs)],env)
            if digest(repo/'engines/chromium'/args.patch_lock)!=lock_hash:
                raise RuntimeError('Identity patch changed during compilation; resume against one reviewed snapshot')
            stage('final-source-hashes',[sys.executable,repo/'engines/chromium/apply_identity_patch.py','--source-root',source,'--check','--lock',args.patch_lock])
            update(frameworkBuildPassed=True)
            framework='Chromium Embedded Framework.framework'
            native=out/framework/'Versions/A'
            source_hash=digest(native/'Chromium Embedded Framework')
            provenance=root/(prefix+'-sdk-provenance.json')
            if sdk.exists():
                if not provenance.is_file() or digest(sdk/'Release'/framework/'Chromium Embedded Framework')!=source_hash:
                    raise RuntimeError('Existing identity SDK is partial or differs; preserve it and inspect before resuming')
            else:
                update(stage='packaging-sdk')
                shutil.copytree(args.sdk_template,sdk,ignore=shutil.ignore_patterns('Release','Debug','tests','cefclient.app','cefsimple.app'))
                shutil.copytree(native,sdk/'Release'/framework,symlinks=True)
                for area in ('include','libcef_dll'):
                    for dest in sorted((sdk/area).rglob('*')):
                        if not dest.is_file() or dest.name in ('CMakeLists.txt','README-TRANSFER.txt'):continue
                        relative=dest.relative_to(sdk);generated=out/'gen/cef'/relative
                        original=generated if generated.is_file() else source/'cef'/relative
                        if not original.is_file():raise RuntimeError('Missing SDK source '+str(relative))
                        shutil.copyfile(original,dest)
                for transfer in ast.literal_eval((source/'cef/tools/distrib/transfer.cfg').read_text()):
                    original=(source/'cef'/transfer['source']).resolve();dest=sdk/transfer['target']
                    if not original.is_relative_to(source) or not dest.resolve().is_relative_to(sdk):
                        raise RuntimeError('SDK transfer escapes source/destination')
                    shutil.copyfile(original,dest)
                record={'sourceFrameworkSha256':source_hash,'sdkFrameworkSha256':digest(sdk/'Release'/framework/'Chromium Embedded Framework'),
                        'identityPatchLockSha256':lock_hash,'sourceRoot':str(source),'outputRoot':str(out),'template':str(args.sdk_template),
                        'purpose':'development identity privacy runtime verification; not an official CEF SDK'}
                if record['sourceFrameworkSha256']!=record['sdkFrameworkSha256']:raise RuntimeError('Packaged framework mismatch')
                provenance.write_text(json.dumps(record,indent=2)+'\n')
            def build_client(name,where,which_sdk):
                stage(name+'-configure',['cmake','-S',repo/'engines/chromium','-B',where,'-G','Ninja','-DCMAKE_BUILD_TYPE=Release','-DCEF_ROOT='+str(which_sdk)])
                stage(name+'-compile',['cmake','--build',where,'--parallel','6'])
                return where/'Release/CloakfoxChromium.app/Contents/MacOS/CloakfoxChromium'
            binary=build_client('client',build,sdk)
            embedded=binary.parent.parent/'Frameworks'/framework/'Versions/A/Chromium Embedded Framework'
            if digest(embedded)!=source_hash:raise RuntimeError('Companion embedded framework mismatch')
            update(binary=str(binary),frameworkSha256=source_hash)
            legacy=build_client('legacy-client',root/(prefix+'-legacy-check'),args.sdk_template)
            test_env={**os.environ,'CLOAKFOX_CHROMIUM_BIN':str(binary),'CLOAKFOX_UNPATCHED_CHROMIUM_BIN':str(legacy),'CLOAKFOX_NATIVE_SURFACE_PROBE':str(build/'Release/host_surface_probe')}
            stage('engine-tests',[sys.executable,'-m','unittest','discover','-s','tests/engines','-p','test_*.py','-v'],test_env)
            stage('cpp-tests',['ctest','--test-dir',build,'--output-on-failure'])
            stage('isolation',[sys.executable,repo/'tests/engines/probe_cef_isolation.py','--binary',binary,'--report',root/(prefix+'-isolation.json')])
            stage('transport',[args.wire_python,repo/'tests/engines/probe_cef_transport.py','--binary',binary,'--report',root/(prefix+'-transport.json')])
            stage('gecko158-coexistence',[args.test_python,repo/'tests/engines/probe_dual_engine_coexistence.py',
                '--gecko-binary','/Applications/Cloakfox.app/Contents/MacOS/cloakfox','--chromium-binary',binary,
                '--require-persona-config','--require-pixel-privacy','--report',root/(prefix+'-gecko158-coexistence.json')])
            update(state='passed',stage='runtime-tests-passed',runtimeTestsPassed=True,finished=time.time())
        except BaseException as error:
            update(state='failed',error=str(error),finished=time.time())
            raise

if __name__=='__main__':main()
