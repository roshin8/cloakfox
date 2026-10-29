import test from 'node:test';
import assert from 'node:assert/strict';
import * as registry from '../../additions/browser/components/cloakfox/CloakfoxGPUReferenceProfiles.sys.mjs';
import {createGPUProfile} from '../../additions/browser/components/cloakfox/CloakfoxGPUProfiles.sys.mjs';
const config=p=>({'webGl:renderer':p.renderer,'webGl:vendor':p.vendor,'navigator.platform':'Win32','navigator.oscpu':'Windows NT 10.0; Win64; x64','fingerprint:secret':'A'.repeat(43)+'=','canvas:seed':42,'rendering:gpu_reference':true,'rendering:gpu_observed':true});
test('observed mode selects independently versioned immutable complete Windows records',()=>{
 assert.equal(registry.OBSERVED_GPU_PROFILES?.length,9);
 for(const [i,p] of registry.OBSERVED_GPU_PROFILES.entries()){
  assert.equal(p.code,36866+i);assert(Object.isFrozen(p));
  const c=config(p), before=structuredClone(c),d=createGPUProfile(c,0);
  assert.equal(d.owner,0);assert.equal(d.version,4);assert.equal(d.mode,'observed-reference');assert.deepEqual(d.catalog,[p.code]);assert.deepEqual(c,before);
  assert.equal(p.contexts.webgl2.parameters['34045'].value,2);assert.equal(p.contexts.webgl2.parameters['36203'].value,4294967294);
  for(const context of Object.values(p.contexts))assert.equal(context.defaults.stencilMask,2147483647);
 }
});
test('observed dependencies, unsupported Apple, foreign identities and ceilings fail closed',()=>{
 const p=registry.REFERENCE_GPU_PROFILES.find(p=>p.family==='intel');const c=config(p);
 for(const v of [false,undefined,'true',1])assert.throws(()=>createGPUProfile({...c,'rendering:gpu_reference':v},0));
 for(const v of ['true',1,null])assert.throws(()=>createGPUProfile({...c,'rendering:gpu_observed':v},0));
 assert.throws(()=>createGPUProfile({...c,'rendering:gpu_reference:ceilings':{webgl2:{'34045':1}}},0));
 assert.throws(()=>createGPUProfile({...c,'webGl:vendor':'borrowed'},0));
 const apple=registry.REFERENCE_GPU_PROFILES[0];assert.throws(()=>createGPUProfile({...config(apple),'navigator.platform':'MacIntel','navigator.oscpu':'Intel Mac OS X 10.15'},0),/supported/);
 assert.equal(createGPUProfile({...c,'rendering:gpu_observed':false},0).version,3);
});

test('expanded identities retain lineage and independent container descriptors',()=>{
 const identities=new Set();
 for(const p of registry.OBSERVED_GPU_PROFILES){
  assert(p.sourceRecords.includes(p.record));
  const identity=JSON.stringify([p.os,p.vendor,p.renderer]);assert(!identities.has(identity));identities.add(identity);
  const a=createGPUProfile(config(p),1),b=createGPUProfile(config(p),2);
  assert.equal(a.owner,1);assert.equal(b.owner,2);a.catalog.push(123);
  assert.deepEqual(createGPUProfile(config(p),2),b);
  for(const key of ['navigator.platform','navigator.oscpu'])assert.throws(()=>createGPUProfile({...config(p),[key]:'borrowed'},1));
  for(const secret of ['',null,'A'.repeat(44)])assert.throws(()=>createGPUProfile({...config(p),'fingerprint:secret':secret},1));
 }
});
