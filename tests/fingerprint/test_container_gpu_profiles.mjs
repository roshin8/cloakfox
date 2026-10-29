import test from 'node:test';
import assert from 'node:assert/strict';
import {createGPUProfile} from '../../additions/browser/components/cloakfox/CloakfoxGPUProfiles.sys.mjs';
const config=renderer=>({'webGl:renderer':renderer,'webGl:vendor':'Synthetic persona vendor','fingerprint:secret':'A'.repeat(43)+'=','canvas:seed':42,'canvas:canonical_gpu':true});
test('all four BrowserForge hardware families receive independently owned descriptors',()=>{
 for(const [renderer,family]of [['Apple M1, or similar','apple'],['Intel UHD Graphics','intel'],['AMD Radeon RX 6600','amd'],['ANGLE (NVIDIA GeForce GTX 980)','nvidia']]){
  const cfg=config(renderer),before=JSON.stringify(cfg),a=createGPUProfile(cfg,6),b=createGPUProfile(cfg,7);
  assert.equal(a.family,family);assert.equal(a.owner,6);assert.equal(b.owner,7);assert.notEqual(a,b);assert.notDeepEqual(a,b);assert.equal(a.renderer,renderer);assert.equal(a.vendor,cfg['webGl:vendor']);assert.equal(JSON.stringify(cfg),before);assert.deepEqual(a,createGPUProfile(cfg,6));
 }
});
test('missing identity, wrong owner and unsupported claims never select a generic fallback',()=>{
 for(const c of [{},config('llvmpipe'),config('SwiftShader'),{...config('Apple M1'),'fingerprint:secret':''},{...config('Intel UHD'),'canvas:seed':-1}])assert.throws(()=>createGPUProfile(c,6));
 for(const owner of [-1,1.5,NaN,'6',0x100000000])assert.throws(()=>createGPUProfile(config('NVIDIA GTX 980'),owner));
});
test('incompatible manual capacity overrides are rejected without mutating input',()=>{
 const c={...config('Intel UHD'),'webGl:parameters':{'3379':13}};const before=JSON.stringify(c);assert.throws(()=>createGPUProfile(c,6));assert.equal(JSON.stringify(c),before);
});

import fs from 'node:fs';
import vm from 'node:vm';
function policyFixture(entries){
 const values=new Map(entries),writes=[];
 const source=fs.readFileSync(new URL('../../additions/browser/components/cloakfox/CloakfoxOverrides.sys.mjs',import.meta.url),'utf8').replace(/^import .*\n/gm,'').replace(/export /g,'');
 const context=vm.createContext({createGPUProfile,applyRegion:(_id,c)=>c,applyPrivacyPolicy:(_id,c)=>c,Services:{prefs:{getBoolPref:(k,f)=>values.has(k)?values.get(k):f,getStringPref:(k,f)=>values.has(k)?values.get(k):f,getBranch:p=>({getChildList:()=>[...values.keys()].filter(k=>k.startsWith(p)).map(k=>k.slice(p.length))}),getChildList:p=>[...values.keys()].filter(k=>k.startsWith(p)),clearUserPref:k=>{writes.push(k);values.delete(k);},setStringPref:(k,v)=>{writes.push(k);values.set(k,v);},setBoolPref:(k,v)=>{writes.push(k);values.set(k,v);}}}});
 vm.runInContext(source,context);return {context,values,writes};
}
test('global activation validates every owner before any write and requires protected software backing',()=>{
 const prefix='cloakfox.s.cloak_cfg_',mode='cloakfox.opt.container_rendering_profiles',full='cloakfox.experimental.canvas_pipeline';
 const {context,values,writes}=policyFixture([[full,true],[prefix+'6',JSON.stringify(config('NVIDIA GTX 980'))],[prefix+'7',JSON.stringify(config('Unknown card'))]]);
 assert.throws(()=>context.setContainerGPUProfilesEnabled(true));assert.equal(writes.length,0);assert.equal(values.has(mode),false);
 values.set(prefix+'7',JSON.stringify(config('Apple M1')));context.setContainerGPUProfilesEnabled(true);assert.deepEqual(writes,[mode]);assert.equal(values.get(mode),true);
 for(const owner of [6,7]){const original=JSON.parse(values.get(prefix+owner)),before=JSON.stringify(original),active=context.applyGraphicsPolicy(original,owner);assert.equal(active['rendering:gpu_profile'].owner,owner);assert.equal(JSON.stringify(original),before);context.setContainerGPUProfilesEnabled(false);assert.deepEqual(context.applyGraphicsPolicy(active,owner)['rendering:gpu_profile'],active['rendering:gpu_profile']);values.set(mode,true);}
 values.set(full,false);writes.length=0;assert.throws(()=>context.setContainerGPUProfilesEnabled(true));assert.equal(writes.length,0);
});
test('preset changes validate the complete update before deleting any saved fields',()=>{
 const mode='cloakfox.opt.container_rendering_profiles',full='cloakfox.experimental.canvas_pipeline',prefix='cloakfox.s.cloak_cfg_',branch='cloakfox.container.6.override.';
 const {context,values,writes}=policyFixture([[mode,true],[full,true],[prefix+'6',JSON.stringify(config('Intel UHD'))],['cloakfox.container.6.math_seed','seed'],[branch+'webGl:vendor','Intel'],[branch+'webGl:renderer','Intel UHD']]);
 context.ChromeUtils={importESModule:()=>({fillPersonaKeys:()=>config('llvmpipe')})};
 assert.throws(()=>context.setOverrides(6,{'webGl:vendor':null,'webGl:renderer':null}));
 assert.equal(values.get(branch+'webGl:vendor'),'Intel');assert.equal(values.get(branch+'webGl:renderer'),'Intel UHD');assert.equal(writes.length,0);
 context.setOverrides(6,{'webGl:vendor':'AMD','webGl:renderer':'AMD Radeon'});
 assert.equal(values.get(branch+'webGl:renderer'),'AMD Radeon');
});

test('whole catalog eligibility filters ceilings without independently randomizing limits',()=>{
 const all=createGPUProfile(config('Apple M1'),6);
 assert.equal(all.version,2);assert.deepEqual(all.catalog,[1,2]);
 const smaller=createGPUProfile({...config('Apple M1'),'webGl:parameters':{'3379':4096}},6);
 assert.deepEqual(smaller.catalog,[1]);
 assert.throws(()=>createGPUProfile({...config('AMD Radeon'),'webGl2:parameters':{'3379':4095}},6));
 assert.throws(()=>createGPUProfile({...config('NVIDIA GTX 980'),'webGl:parameters':{'3386':[4096,100]}},6));
 assert.deepEqual(createGPUProfile({...config('Intel UHD'),'webGl:parameters':{'3386':[4096,4096]}},6).catalog,[1]);
});
