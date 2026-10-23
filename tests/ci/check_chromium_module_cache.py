"""Hosted-only pinned-Clang correctness fixture; no performance benchmark."""
import argparse,hashlib,json,os,subprocess,time,importlib.util
from pathlib import Path


def run_fixture(root,clang,ccache,receipt):
    root.mkdir(parents=True,exist_ok=False);include=root/'include';include.mkdir()
    header=include/'value.h';module=include/'module.modulemap';source=root/'unit.cc';output=root/'unit.o';context=root/'context.json'
    header.write_text('inline constexpr int kValue=7;\n');module.write_text('module Value { header "value.h" export * }\n');source.write_text('#include "value.h"\nint value() { return kValue; }\n');context.write_text('{"source":"one","host":"pinned"}\n')
    sdk=subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-path'],text=True).strip()
    assert subprocess.check_output([str(ccache),'--version'],text=True).splitlines()[0]=='ccache version 4.14', 'Expected exact verified ccache 4.14'
    policy_path=Path(__file__).resolve().parents[2]/'scripts/ci/chromium_cache_policy.py'
    spec=importlib.util.spec_from_file_location('cache_policy',policy_path);policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
    values=policy.settings(receipt,context,'cc270ce4c2790dc4d2fb295e7721c23321cb3acc4aefa3f934b846eda5d08999','4f155411db66d1934e6926c4bf4c93cfb6561838')
    env={**os.environ,'CCACHE_DIR':str(root/'cache'),'CCACHE_LOGFILE':str(root/'ccache-debug.log'),**values}
    command=[str(ccache),str(clang),'-target','arm64-apple-macos13','-isysroot',sdk,'-std=c++20','-fmodules','-fimplicit-module-maps','-fmodules-cache-path='+str(root/'modules'),'-I'+str(include),'-MD','-MF',str(root/'unit.d'),'-c',str(source),'-o',str(output)]
    results=[]
    def stats():
        return {k:int(v) for k,v in (line.split() for line in subprocess.check_output([str(ccache),'--print-stats'],env=env,text=True).splitlines())}
    def compile(label,hit):
        time.sleep(1.1) # Keep ctime/mtime safety checks enabled for fresh fixture files.
        before=stats();subprocess.run(command,env=env,check=True,timeout=120);after=stats()
        hits=after['direct_cache_hit']+after['preprocessed_cache_hit']-before['direct_cache_hit']-before['preprocessed_cache_hit']
        assert hits==int(hit),(label,hits,after)
        if not hit:assert after['cache_miss']==before['cache_miss']+1,(label,after)
        digest=hashlib.sha256(output.read_bytes()).hexdigest();results.append({'label':label,'hit':hit,'objectSha256':digest});return digest
    first=compile('cold',False);assert compile('warm',True)==first
    header.write_text('inline constexpr int kValue=11;\n');assert compile('header-change',False)!=first;compile('header-warm',True)
    module.write_text('module Value { header "value.h" export *\n }\n');compile('modulemap-change',False)
    context.write_text('{"source":"two","host":"pinned"}\n');compile('source-identity-change',False)
    context.write_text('{"source":"two","host":"different-sdk"}\n');compile('host-identity-change',False)
    (root/'result.json').write_text(json.dumps({'verified':True,'compilerSha256':hashlib.sha256(clang.read_bytes()).hexdigest(),'results':results,'stats':stats()},indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--clang',type=Path,required=True);parser.add_argument('--ccache',type=Path,required=True);parser.add_argument('--receipt',type=Path,required=True);a=parser.parse_args();run_fixture(a.root,a.clang,a.ccache,a.receipt)
