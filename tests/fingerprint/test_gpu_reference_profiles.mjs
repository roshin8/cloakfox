import test from 'node:test';
import assert from 'node:assert/strict';
import {createReferenceGPUProfile, REFERENCE_GPU_PROFILES} from '../../additions/browser/components/cloakfox/CloakfoxGPUReferenceProfiles.sys.mjs';
const config = p => ({'webGl:renderer':p.renderer,'webGl:vendor':p.vendor,'canvas:seed':42,'fingerprint:secret':'A'.repeat(43)+'=','rendering:gpu_reference':true,'navigator.platform':p.os==='mac'?'MacIntel':'Win32','navigator.oscpu':p.os==='mac'?'Intel Mac OS X 10.15':'Windows NT 10.0; Win64; x64'});
test('reference registry owns immutable paired identities from all four families',()=>{
  assert.equal(new Set(REFERENCE_GPU_PROFILES.map(p=>p.family)).size,4);
  for(const p of REFERENCE_GPU_PROFILES){
    assert(Object.isFrozen(p));
    const d=createReferenceGPUProfile(config(p),7);
    assert.equal(d.owner,7);assert.equal(d.version,3);assert(d.catalog.includes(p.code));
    assert.equal(d.renderer,p.renderer);assert.match(d.source,/6530b832/);
  }
});
test('unknown, borrowed and malformed identities cannot acquire a reference',()=>{
 const p=REFERENCE_GPU_PROFILES[0];
 for(const c of [{...config(p),'webGl:vendor':'borrowed'}, {...config(p),'webGl:renderer':'Apple invented'}, {...config(p),'canvas:seed':-1}])assert.throws(()=>createReferenceGPUProfile(c,7));
 for(const owner of [-1,1.5,2**32])assert.throws(()=>createReferenceGPUProfile(config(p),owner));
});
test('explicit conflicting capability ceilings reject the whole profile',()=>{
 const p=REFERENCE_GPU_PROFILES[0];
 assert.throws(()=>createReferenceGPUProfile({...config(p),'rendering:gpu_reference:ceilings':{webgl:{'3379':1}}},7));
});

test('generated BF ceilings are superseded as a complete bundle',()=>{
 const p=REFERENCE_GPU_PROFILES[0];
 const d=createReferenceGPUProfile({...config(p),'webGl:parameters':{'3379':1},'webGl2:parameters':{'35375':24}},7);
 assert(d.catalog.includes(p.code));
});

test('same GPU label cannot borrow a different BrowserForge OS pair',()=>{
 for(const p of REFERENCE_GPU_PROFILES)assert.throws(()=>createReferenceGPUProfile({...config(p),'navigator.platform':p.os==='mac'?'Win32':'MacIntel'},7));
});
