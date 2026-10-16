#!/usr/bin/env python3
"""Optional isolated compiler-cache benchmark; never invoked by the browser build.

Uses synthetic sources and a caller-supplied Clang, not a full Chromium compile.
No preexisting cache directory or daemon is reused or cleared.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--clang',type=Path,required=True)
parser.add_argument('--ccache',type=Path,required=True)
parser.add_argument('--sccache',type=Path,required=True)
parser.add_argument('--rounds',type=int,default=7)
parser.add_argument('--ccache-first',action='store_true')
parser.add_argument('--cxx-standard', choices=('c++20', 'c++23'), default='c++23')
parser.add_argument('--output', type=Path, required=True)
args=parser.parse_args()
if args.rounds<3:parser.error('at least three warm rounds required')
if (os.environ.get('GITHUB_ACTIONS') != 'true'
    or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'
    or platform.system() != 'Darwin' or platform.machine() != 'arm64'):
 parser.error('Run this comparison only on a standard GitHub-hosted macOS arm64 runner')
CLANG=args.clang.resolve()
CCACHE=args.ccache.resolve()
SCCACHE=args.sccache.resolve()
ROOT=Path(tempfile.mkdtemp(prefix='cloakfox-cache-comparison-',dir='/tmp'))
SDK=subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip()
BASE={k:v for k,v in os.environ.items() if not k.startswith(('CCACHE_','SCCACHE_','RUSTC_WRAPPER','AWS_','ACTIONS_CACHE_'))}
ENVS={
 'plain':BASE,
 'ccache':{**BASE,'CCACHE_DIR':str(ROOT/'ccache'),'CCACHE_CONFIGPATH':str(ROOT/'ccache.conf')},
 'sccache':{**BASE,'SCCACHE_DIR':str(ROOT/'sccache'),'SCCACHE_SERVER_UDS':str(ROOT/'sccache.sock'),
             'SCCACHE_CONF':str(ROOT/'sccache.toml'),'SCCACHE_CACHE_SIZE':'512M','SCCACHE_IDLE_TIMEOUT':'0','SCCACHE_DIRECT':'true'},
}
(ROOT/'sccache.toml').write_text('')
(ROOT/'ccache.conf').write_text('max_size = 512M\n')
header=ROOT/'fixture.h'
header.write_text('''#pragma once
#include <algorithm>
#include <array>
#include <atomic>
#include <bitset>
#include <chrono>
#include <functional>
#include <map>
#include <memory>
#include <numeric>
#include <optional>
#include <string>
#include <tuple>
#include <unordered_map>
#include <variant>
#include <vector>
constexpr int salt = 41;
template<int N> struct Fold { static constexpr unsigned value = Fold<N-1>::value * 33u + N; };
template<> struct Fold<0> { static constexpr unsigned value = 7; };
''')
SOURCES=[]
for n in range(6):
 p=ROOT/f'fixture{n}.cc'
 p.write_text('#include "fixture.h"\n'+f'''extern "C" unsigned fixture_{n}(const char* input) {{
std::vector<std::string> v; v.emplace_back(input); std::sort(v.begin(),v.end());
std::unordered_map<std::string,unsigned> m; m[v[0]]=Fold<{140+n}>::value;
return m[v[0]]+salt; }}\n''')
 SOURCES.append((p,'c++'))
p=ROOT/'fixture.mm';p.write_text('#import <Foundation/Foundation.h>\n#include "fixture.h"\nextern "C" unsigned fixture_objc() { return (unsigned)[@"test" length] + salt; }\n');SOURCES.append((p,'objective-c++'))
p=ROOT/'fixture.c';p.write_text('#include <stdint.h>\nuint32_t fixture_c(uint32_t n) { return (n ^ 0xdeadbeefu) + 17; }\n');SOURCES.append((p,'c'))
FLAGS=['--target=arm64-apple-macos','-isysroot',SDK,'-mmacosx-version-min=13.0','-O2','-fno-exceptions',
 '-fno-rtti','-fvisibility=hidden','-fPIC','-fstack-protector-strong','-fcolor-diagnostics','-MMD']
COMMANDS=[]
for p,lang in SOURCES:
 flags=[f for f in FLAGS if f!='-fno-rtti' or lang!='c']
 COMMANDS.append([str(CLANG),'-x',lang,*flags,*(['-std='+args.cxx_standard] if lang!='c' else ['-std=c11']),
   '-MF',str(p.with_name(p.name+'.d')),'-c',str(p),'-o',str(p.with_name(p.name+'.o'))])

def compile_one(kind, command):
 prefix=[] if kind=='plain' else [str(CCACHE if kind=='ccache' else SCCACHE)]
 start=time.perf_counter()
 r=subprocess.run(prefix+command,cwd=ROOT,env=ENVS[kind],capture_output=True,text=True,timeout=60)
 if r.returncode:raise RuntimeError(r.stderr)
 obj=Path(command[-1]);dep=Path(command[command.index('-MF')+1])
 return {'seconds':time.perf_counter()-start,'objectSha256':hashlib.sha256(obj.read_bytes()).hexdigest(),
         'depSha256':hashlib.sha256(dep.read_bytes()).hexdigest()}

def batch(kind):
 start=time.perf_counter()
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  rows=list(pool.map(lambda cmd:compile_one(kind,cmd),COMMANDS))
 return {'wallSeconds':time.perf_counter()-start,'objects':rows}

def stats(kind):
 cmd=[str(CCACHE),'--print-stats','--format','json'] if kind=='ccache' else [str(SCCACHE),'--show-stats','--stats-format','json']
 return json.loads(subprocess.check_output(cmd,env=ENVS[kind],text=True))

report={'fixtureRoot':str(ROOT),'scope':'Synthetic Chromium-style C/C++/Objective-C++ fixture with pinned compiler and real macOS SDK; local cache backends only, not full Chromium or remote GHA cache performance',
 'githubRun':os.environ.get('GITHUB_RUN_ID'),'gitSha':os.environ.get('GITHUB_SHA'),
 'platform':platform.platform(),'compiler':subprocess.check_output([str(CLANG),'--version'],text=True),
 'versions':{k:subprocess.check_output([str(v),'--version'],text=True).splitlines()[0] for k,v in [('ccache',CCACHE),('sccache',SCCACHE)]},
 'commands':COMMANDS,'cold':{},'warm':{},'changedHeader':{}}
try:
 subprocess.run([str(SCCACHE),'--start-server'],env=ENVS['sccache'],check=True,capture_output=True,text=True,timeout=15)
 time.sleep(1.1) # Both caches conservatively reject newly created header timestamps.
 # Alternate order; warm filesystem is shared by the baseline and both tools.
 for kind in (('plain','ccache','sccache') if args.ccache_first else ('plain','sccache','ccache')):
  report['cold'][kind]=batch(kind)
 reference=[x['objectSha256'] for x in report['cold']['plain']['objects']]
 for kind in ('ccache','sccache'):
  assert [x['objectSha256'] for x in report['cold'][kind]['objects']]==reference,('cold correctness',kind)
  assert [x['depSha256'] for x in report['cold'][kind]['objects']]==[x['depSha256'] for x in report['cold']['plain']['objects']],('cold dependency correctness',kind)
 for round in range(args.rounds):
  for kind in (('ccache','sccache') if round%2==0 else ('sccache','ccache')):
   result=batch(kind)
   assert [x['objectSha256'] for x in result['objects']]==reference,('warm correctness',kind)
   assert [x['depSha256'] for x in result['objects']]==[x['depSha256'] for x in report['cold']['plain']['objects']],('warm dependency correctness',kind)
   report['warm'].setdefault(kind,[]).append(result['wallSeconds'])
 report['statsBeforeMutation']={k:stats(k) for k in ('ccache','sccache')}
 cstats=report['statsBeforeMutation']['ccache']
 sstats=report['statsBeforeMutation']['sccache']['stats']
 hits={'ccache':cstats['direct_cache_hit']+cstats['preprocessed_cache_hit'],
       'sccache':sum(sstats['cache_hits']['counts'].values())}
 assert all(value>=len(COMMANDS)*args.rounds for value in hits.values()),('missing warm hits',hits)
 assert cstats['compile_failed']==0 and sstats['compile_fails']==0
 report['verifiedWarmCacheHits']=hits
 header.write_text(header.read_text().replace('salt = 41','salt = 97'))
 time.sleep(1.1)
 for kind in ('plain','ccache','sccache'):report['changedHeader'][kind]=batch(kind)
 changed=[x['objectSha256'] for x in report['changedHeader']['plain']['objects']]
 assert changed!=reference
 for kind in ('ccache','sccache'):
  assert [x['objectSha256'] for x in report['changedHeader'][kind]['objects']]==changed,('header invalidation',kind)
  assert [x['depSha256'] for x in report['changedHeader'][kind]['objects']]==[x['depSha256'] for x in report['changedHeader']['plain']['objects']],('changed dependency correctness',kind)
 report['finalStats']={k:stats(k) for k in ('ccache','sccache')}
 report['warmMedians']={k:statistics.median(v) for k,v in report['warm'].items()}
 report['correctness']='all objects match uncached compiler; changed header invalidated both caches'
finally:
 try:
  subprocess.run([str(SCCACHE),'--stop-server'],env=ENVS['sccache'],capture_output=True,text=True,timeout=15)
 finally:
  args.output.parent.mkdir(parents=True,exist_ok=True)
  args.output.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k in ('fixtureRoot','warmMedians','correctness')},indent=2))
 print('REPORT',args.output)
