#!/usr/bin/env python3
"""Generate immutable executable candidates; admission remains a native runtime check.
The source observations are never rewritten or silently clamped. Privacy exclusions
and Firefox146 ->159 adaptation are separate explicit policy, not source claims.
"""
import json
import copy
import hashlib
import gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE='6530b8322cdaa4ec042921c8d9a0369a0e6e0269ba636c01a7203e4a2f109936'
IDS=['165cf47b5f7d3a73e3c6d237c7110db7c674356b20a41846db90263817a36363','9bc697f54e04df4da5771d3f913de083019fe449929b97a94dd0432020ccb531','3f9b16196a1d6ff1f80adf429c8b2cfbda1539dac05aa1b2b511a5d29cd56075','27053b853db1c3399a7426ba0d80ed347f36517a6e8741a0ab5f52f86550046b']
DENIED={'WEBGL_debug_shaders','EXT_disjoint_timer_query','EXT_disjoint_timer_query_webgl2','WEBGL_provoking_vertex'}
FULL_SHA256='54c9726596fab90c9c5e35ee59b236c8406dd16de7a8c3ab6623b273f2471ce5'
def load_full():
 path=ROOT/'additions/cloakcfg/gpu-full-reference-records.json.gz'
 raw=path.read_bytes()
 if len(raw)>4*1024*1024 or hashlib.sha256(raw).hexdigest()!=FULL_SHA256:raise ValueError('Immutable full GPU source changed')
 with gzip.open(path,'rb') as stream:decoded=stream.read(64*1024*1024+1)
 if len(decoded)>64*1024*1024:raise ValueError('Full GPU source exceeds bound')
 return json.loads(decoded)

def execution_projection(corpus, record):
 """Exact capability evidence; identity labels never confer execution support."""
 result={}
 for gl in ['webgl','webgl2']:
  entry=corpus['contexts'].get(record.get(gl),{})
  if not entry.get('staticCapabilities'):return None
  c=copy.deepcopy(entry['staticCapabilities']); observed=entry['observed']
  c['supportedExtensions']=[e for e in c['supportedExtensions'] if e not in DENIED]
  for enum in ['34047','34852','36063','38449']:
   value=observed['extensions'].get(enum,{}).get('parameter',{}).get('value')
   if type(value) in (int,float) and enum not in c['parameters']:c['parameters'][enum]={'value':value}
  c['parameters']={k:v['value'] for k,v in c['parameters'].items()}
  c['defaults']={k:observed['params'].get(k,{}).get('value') for k in ['2963','2968','36004','36005']}
  c['contextAttributes']=observed['contextAttributes'];result[gl]=c
 return result

def admit_full(full, legacy):
 if full['source']['archive']['sha256']!=SOURCE:raise ValueError('Unexpected full GPU source')
 records={r['id']:r for r in legacy['records']}
 seeds=[records['sha256:'+rid] for rid in IDS[1:]]
 signatures=[execution_projection(legacy,r) for r in seeds]
 grouped={};audit=[]
 for r in sorted(full['records'],key=lambda r:r['id']):
  projection=execution_projection(full,r)
  reason=('incomplete-or-inconsistent-source' if r.get('blockers') or projection is None else
          'unsupported-os-binding' if r['os']!='win' else
          'unsupported-family' if r['family'] not in ['intel','amd','nvidia'] else
          'capability-pair-not-execution-equivalent' if projection not in signatures else None)
  audit.append({'record':r['id'],'browser':r['browser'],'sourceTokens':r['sourceTokens'],'blockers':r.get('blockers',[]),'reason':reason or 'admitted-exact-execution-equivalence'})
  if reason:continue
  identity=(r['os'],r['family'],r['gpu']['vendor'],r['gpu']['renderer'])
  group=grouped.setdefault(identity,[]);group.append(r)
 admitted=[]
 for identity,lineage in sorted(grouped.items()):
  # Stable legacy IDs/codes win; all equivalent paths retain explicit lineage.
  chosen=next((r for seed in seeds for r in lineage if r['id']==seed['id']),lineage[0])
  admitted.append({**chosen,'sourceRecords':[r['id'] for r in lineage]})
 admitted.sort(key=lambda r:(0,IDS.index(r['id'][7:])) if r['id'][7:] in IDS else (1,r['id']))
 from collections import Counter
 report={'schemaVersion':1,'sourceArchiveSha256':SOURCE,'fullCorpusSha256':FULL_SHA256,'fullRecordCount':len(full['records']),'fullContextCount':len(full['contexts']),'observedIdentityCount':len(admitted),'reasonCounts':dict(sorted(Counter(r['reason'] for r in audit).items())),'policy':'Exact complete capability equivalence to validated legacy observed pairs after existing privacy exclusions; no capability adaptation or host fallback','identities':[{'record':r['id'],'sourceRecords':r['sourceRecords'],'os':r['os'],'family':r['family'],'gpu':r['gpu']} for r in admitted],'records':audit}
 return admitted,report

def main(check=False):
 def output(relative,text):
  path=ROOT/relative
  if check:
   if not path.exists() or path.read_text()!=text:raise ValueError('Generated reference catalog is stale: '+str(relative))
  else:path.write_text(text)
 raw=(ROOT/'additions/cloakcfg/gpu-reference-records.json').read_bytes()
 if hashlib.sha256(raw).hexdigest()!='8a5b474b1c7c296ce344cdbe6a4beb93c9a8c5428dfc6482287baaf6ecf65931':raise ValueError('Immutable paired GPU reference records changed')
 x=json.loads(raw)
 if x['source']['archive']['sha256']!=SOURCE or len(x['records'])!=106 or len(x['contexts'])!=118:raise ValueError('Unexpected pinned GPU source or pairing corpus')
 full=load_full()
 admitted,report=admit_full(full,x)
 legacy=x
 records={r['id']:r for r in x['records']}
 profiles=[]; cpp=['/* Generated by scripts/generate-gpu-reference-profiles.py. MPL-2.0. */','#pragma once','#include <cstdint>','#include <cstddef>','#include <string_view>','#include <optional>','namespace CloakfoxGPUReference {','struct Parameter { uint32_t pname; double lo, hi; uint8_t components; };','struct Precision { uint32_t shader, type, rangeMin, rangeMax, precision; };','struct Context { const Parameter* parameters; size_t parameterCount; const Precision* precision; size_t precisionCount; const char* const* extensions; size_t extensionCount; };','struct Profile { uint32_t code, family; const char* os; const char* record; const char* renderer; const char* vendor; const Context* contexts[2]; bool observed; uint32_t stencilMasks[2]; };']
 for index,r in enumerate([records['sha256:'+rid] for rid in IDS]+admitted):
  observed=index>=4; sourceIndex=index-3 if observed else index
  x=full if observed else legacy
  p={'code':36865+sourceIndex if observed else 32769+index,'family':r['family'],'record':r['id'],'renderer':r['gpu']['renderer'],'vendor':r['gpu']['vendor'],'os':r['os'],'contexts':{}}
  if observed:p['sourceRecords']=r['sourceRecords']
  for gi,key in enumerate(['webgl','webgl2']):
   original=x['contexts'][r[key]]['staticCapabilities']; c=copy.deepcopy(original)
   changes={}
   def adapt(k,value,reason):
    k=str(k);entry=c['parameters'].get(k)
    if entry and entry['value']!=value:
     changes[k]={'source':entry['value'],'derived':value,'reason':reason};entry['value']=value
   if gi and not observed:
    v=lambda k:c['parameters'][str(k)]['value']
    varying=min(v(36348),v(35659)//4,v(37154)//4,v(37157)//4)
    for k,n in [(36348,varying),(35659,4*varying),(37154,4*varying),(37157,4*varying)]:adapt(k,n,'Firefox159 coherent shader translator varying resources')
    adapt(37137,0,'Protected canonical WebGL server wait has no finite timeout')
    adapt(36203,4294967295,'Firefox159 canonical unsigned element-index validation')
   if not observed:adapt(34045,16,'Canonical CPU sampler executes LOD bias clamped to sixteen')
   if observed:
    masks=[x['contexts'][r[key]]['observed']['params'][str(k)]['value'] for k in [2963,2968,36004,36005]]
    if masks!=[2147483647]*4:raise ValueError('Unsupported observed stencil defaults')
    c['defaults']={'stencilMask':masks[0]}
    p['observed']=True
   removed=[ext for ext in c['supportedExtensions'] if ext in DENIED]
   if removed:changes['supportedExtensions']={'excluded':removed,'reason':'Protected policy blocks timers/debug-shaders; Firefox159 version-specific provoking-vertex is not admitted'}
   c['supportedExtensions']=[ext for ext in c['supportedExtensions'] if ext not in DENIED]
   # Extension-owned fixed limits are included only with their normal enablement guard.
   for enum in ['34047','34852','36063','38449']:
    value=x['contexts'][r[key]]['observed']['extensions'].get(enum,{}).get('parameter',{}).get('value')
    if isinstance(value,(int,float)) and enum not in c['parameters']:c['parameters'][enum]={'name':'extension-owned static limit','type':'Number','value':value}
   for precision in c['shaderPrecisionFormats']:
    target={'rangeMin':127,'rangeMax':127,'precision':23} if precision['precisionType'] in [36336,36337,36338] else {'rangeMin':31,'rangeMax':30,'precision':0}
    if observed and precision['shaderPrecisionFormat']!=target:raise ValueError('Unsupported observed precision')
    if not observed and precision['shaderPrecisionFormat']!=target:
     changes[str(precision['shaderType'])+','+str(precision['precisionType'])]={'source':precision['shaderPrecisionFormat'],'derived':target,'reason':'Canonical CPU shaders execute full32bit arithmetic for every precision qualifier'}
     precision['shaderPrecisionFormat']=target
   p.setdefault('adaptations',{})[key]=changes
   p.setdefault('sourceContexts',{})[key]=r[key]
   p['contexts'][key]=c
   params=[]
   for k,v in c['parameters'].items():
    val=v['value']
    if k=='34467':continue # Derived from admitted enabled compression extensions.
    if isinstance(val,list):
     assert len(val)==2; lo,hi=val; n=2
    else:lo=hi=val;n=1
    params.append('{'+f'{k},{lo},{hi},{n}'+'}')
   tag=f'k{index}_{gi}'
   cpp+=['inline constexpr Parameter '+tag+'Params[] = {'+','.join(params)+'};']
   precisions=[s for s in c['shaderPrecisionFormats']]
   cpp+=['inline constexpr Precision '+tag+'Precision[] = {'+','.join('{'+','.join(str(z) for z in [s['shaderType'],s['precisionType'],s['shaderPrecisionFormat']['rangeMin'],s['shaderPrecisionFormat']['rangeMax'],s['shaderPrecisionFormat']['precision']])+'}' for s in precisions)+'};']
   ext=[e for e in c['supportedExtensions'] if e not in DENIED]
   cpp+=['inline constexpr const char* '+tag+'Extensions[] = {'+','.join(json.dumps(e) for e in ext)+'};',f'inline constexpr Context {tag} = {{{tag}Params, {len(params)}, {tag}Precision, {len(precisions)}, {tag}Extensions, {len(ext)}}};']
  profiles.append(p)
 cpp+=['inline constexpr Profile kProfiles[] = {']
 for i,p in enumerate(profiles):cpp+=['{'+','.join([str(p['code']),str({'apple':1,'intel':2,'amd':3,'nvidia':4}[p['family']]),json.dumps(p['os']),json.dumps(p['record']),json.dumps(p['renderer']),json.dumps(p['vendor']),'{&k'+str(i)+'_0,&k'+str(i)+'_1}', 'true' if p.get('observed') else 'false', '{2147483647,2147483647}' if p.get('observed') else '{0,0}'])+'},']
 cpp+=['};','inline const Profile* Lookup(uint32_t code) { for (const auto& p:kProfiles) if(p.code==code)return &p; return nullptr; }','inline bool Observed(uint32_t code) {const auto* p=Lookup(code);return p&&p->observed;}', 'inline uint32_t ObservedStencilMask(uint32_t code,bool gl2) {const auto* p=Lookup(code);return p&&p->observed?p->stencilMasks[gl2?1:0]:0;}', 'inline float ObservedLodBias(uint32_t code) {return Observed(code)?2.0f:0.0f;}', 'inline const Context* ForContext(uint32_t code, bool gl2) { const auto* p=Lookup(code); return p?p->contexts[gl2?1:0]:nullptr; }','inline const Parameter* Find(uint32_t code,bool gl2,uint32_t pname) {const auto* c=ForContext(code,gl2);if(c)for(size_t i=0;i<c->parameterCount;i++)if(c->parameters[i].pname==pname)return &c->parameters[i];return nullptr;}','inline uint32_t Cap(uint32_t code,bool gl2,uint32_t pname) {const auto* p=Find(code,gl2,pname);return p?uint32_t(p->lo):0;}','inline bool HasExtension(const Context& c,std::string_view name) {for(size_t i=0;i<c.extensionCount;i++)if(name==c.extensions[i])return true;return false;}','inline constexpr const char* kSource = "'+SOURCE+'";','}']
 output('docs/firefox-159/full-fpgen-gpu/catalog-expansion.json',json.dumps(report,indent=2)+'\n')
 output('additions/cloakcfg/gpu-reference-executable.json',json.dumps({'schemaVersion':1,'sourceArchiveSha256':SOURCE,'profiles':[p for p in profiles if not p.get('observed')],'observedProfiles':[p for p in profiles if p.get('observed')],'policyExclusions':sorted(DENIED),'claim':'Reference-derived protected canonical profiles; no physical-driver or Firefox146 emulation claim'},indent=2)+'\n')
 output('additions/cloakcfg/CloakfoxGPUReferenceCatalog.hpp','\n'.join(cpp)+'\n')
 js='/* Generated immutable source candidates; native code independently admits all capabilities. MPL-2.0. */\nconst profiles = '+json.dumps(profiles,separators=(',',':'))+';\n'
 js+='''function freeze(value) { if (value && typeof value === 'object') {for (const child of Object.values(value)) freeze(child);Object.freeze(value);}return value;}
export const REFERENCE_GPU_PROFILES = freeze(profiles.filter(p=>!p.observed));
export const OBSERVED_GPU_PROFILES = freeze(profiles.filter(p=>p.observed));
export const OBSERVED_GPU_POLICY = 'observed-reference-v1';
export const OBSERVED_GPU_ADAPTATION = 'observed:full32;native-stencil;typed-lod-bias;fixed-restart-index;deny-debug-shaders-and-timers;omit-version-specific-provoking-vertex;WebGPU-canonical-device';
export function createObservedGPUProfile(config, owner) {
 if(config['rendering:gpu_reference']!==true||config['rendering:gpu_observed']!==true)throw new Error('Observed GPU requires reference rendering');
 return createReferenceGPUProfile(config,owner);
}
export const REFERENCE_GPU_SOURCE = '@SOURCE@';
export const REFERENCE_GPU_POLICY = 'reference-protected-v1';
export function createReferenceGPUProfile(config, owner) {
 if(config['rendering:gpu_observed']!==undefined&&typeof config['rendering:gpu_observed']!=='boolean')throw new Error('Invalid observed GPU request');
 const observed=config['rendering:gpu_observed']===true;
 if(observed&&config['rendering:gpu_reference']!==true)throw new Error('Observed GPU requires reference rendering');
 if (!Number.isInteger(owner)||owner<0||owner>0xffffffff) throw new Error('Reference GPU requires an exact container owner');
 if (typeof config['fingerprint:secret'] !== 'string'||!/^[A-Za-z0-9+/]{43}=$/.test(config['fingerprint:secret'])||!Number.isInteger(config['canvas:seed'])||config['canvas:seed']<0||config['canvas:seed']>0xffffffff) throw new Error('Reference GPU identity is missing or invalid');
 const ceilings=config['rendering:gpu_reference:ceilings'];
 if(ceilings!==undefined&&(!ceilings||typeof ceilings!=='object'||Array.isArray(ceilings)))throw new Error('Invalid explicit reference GPU ceilings');
 const candidates=profiles.filter(p=>!!p.observed===observed&&p.renderer===config['webGl:renderer']&&p.vendor===config['webGl:vendor']&&config['navigator.platform']===(p.os==='mac'?'MacIntel':'Win32')&&config['navigator.oscpu']===(p.os==='mac'?'Intel Mac OS X 10.15':'Windows NT 10.0; Win64; x64'));
 if(!candidates.length)throw new Error('Choose a supported BrowserForge OS/hardware identity for reference-based protected GPU rendering');
 const eligible=candidates.filter(p=>['webgl','webgl2'].every((context,i)=>{
  const table=config['rendering:gpu_reference:ceilings']?.[context];if(table===undefined)return true;
  if(!table||typeof table!=='object'||Array.isArray(table))throw new Error('Invalid reference GPU capability table');
  return Object.entries(p.contexts[context].parameters).every(([key,entry])=>{
   if(!Object.hasOwn(table,key)||key==='34467')return true;
   const value=table[key],required=entry.value;
   if(Array.isArray(required))return Array.isArray(value)&&value.length===2&&value.every((v,j)=>Number.isFinite(v)&&(j||key==='3386'?v>=required[j]:v<=required[j]));
   return Number.isFinite(value)&&(key==='35076'?value<=required:value>=required);
  });
 }));
 if(!eligible.length)throw new Error('GPU capability overrides conflict with the complete paired reference profile');
 return {version:observed?4:3,mode:observed?'observed-reference':'reference',owner,family:eligible[0].family,renderer:eligible[0].renderer,vendor:eligible[0].vendor,catalog:eligible.map(p=>p.code),source:REFERENCE_GPU_SOURCE,privacyPolicy:observed?OBSERVED_GPU_POLICY:REFERENCE_GPU_POLICY,adaptation:observed?OBSERVED_GPU_ADAPTATION:'Firefox146-to159:canonical-renderer;deny-debug-shaders-and-timers;omit-version-specific-provoking-vertex;WebGPU-canonical-device'};
}
'''.replace('@SOURCE@',SOURCE)
 output('additions/browser/components/cloakfox/CloakfoxGPUReferenceProfiles.sys.mjs',js)
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args();main(check=args.check)
