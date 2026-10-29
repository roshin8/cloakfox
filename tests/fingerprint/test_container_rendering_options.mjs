import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {createGPUProfile} from '../../additions/browser/components/cloakfox/CloakfoxGPUProfiles.sys.mjs';

const prefix='cloakfox.s.cloak_cfg_',branch=id=>`cloakfox.container.${id}.override.`;
const cfg=()=>({'fingerprint:secret':'A'.repeat(43)+'=','canvas:seed':42,'webGl:vendor':'Intel','webGl:renderer':'Intel UHD'});
function fixture(){
 const values=new Map([['cloakfox.experimental.canvas_pipeline',true],[prefix+'6',JSON.stringify(cfg())],[prefix+'7',JSON.stringify(cfg())]]),writes=[];
 const context=vm.createContext({createGPUProfile,applyRegion:(_id,c)=>c,applyPrivacyPolicy:(_id,c)=>c,ChromeUtils:{importESModule:()=>({fillPersonaKeys:()=>cfg()})},Services:{prefs:{
 getBoolPref:(k,f)=>values.has(k)?values.get(k):f,getStringPref:(k,f)=>values.has(k)?values.get(k):f,
 getBranch:p=>({getChildList:()=>[...values.keys()].filter(k=>k.startsWith(p)).map(k=>k.slice(p.length))}),
 getChildList:p=>[...values.keys()].filter(k=>k.startsWith(p)),clearUserPref:k=>{writes.push(k);values.delete(k);},
 setStringPref:(k,v)=>{writes.push(k);values.set(k,v);},setBoolPref:(k,v)=>{writes.push(k);values.set(k,v);}
 }}});
 const source=fs.readFileSync(new URL('../../additions/browser/components/cloakfox/CloakfoxOverrides.sys.mjs',import.meta.url),'utf8').replace(/^import .*\n/gm,'').replace(/export /g,'');
 vm.runInContext(source,context);return {context,values,writes};
}
test('canonical geometry saves only the selected owner and emits exact owned metadata',()=>{
 const {context,values,writes}=fixture();const other=values.get(prefix+'7');
 context.setOverrides(6,{'geometry:canonical':true});
 assert.deepEqual(writes,[branch(6)+'geometry:canonical']);assert.equal(values.get(branch(6)+'geometry:canonical'),true);assert.equal(values.get(prefix+'7'),other);
 const applied=context.applyOverrides(6,cfg());assert.equal(applied['geometry:canonical'],true);
 assert.deepEqual(JSON.parse(JSON.stringify(applied['rendering:geometry_profile'])),{version:1,id:'canonical-v1',owner:6});
 assert.equal(context.applyOverrides(7,cfg())['geometry:canonical'],undefined);
});
test('new rendering modes require real booleans and canonical backing before any write',()=>{
 for(const key of ['geometry:canonical','rendering:gpu_reference']){
  for(const bad of ['true',1,{},[]]){const {context,writes}=fixture();assert.throws(()=>context.setOverrides(6,{[key]:bad}),/boolean/i);assert.equal(writes.length,0);}
  const {context,values,writes}=fixture();values.set('cloakfox.experimental.canvas_pipeline',false);
  assert.throws(()=>context.setOverrides(6,{[key]:true}),/canonical/i);assert.equal(writes.length,0);
 }
});
test('geometry rejects missing identity atomically and disabling mode removes descriptor',()=>{
 const {context,values,writes}=fixture();const c=cfg();delete c['fingerprint:secret'];
 assert.throws(()=>context.applyGraphicsPolicy({...c,'geometry:canonical':true},6),/identity/i);
 assert.equal(writes.length,0);
 const active=context.applyGraphicsPolicy({...cfg(),'geometry:canonical':true},6);
 const off=context.applyGraphicsPolicy({...active,'geometry:canonical':false},6);
 assert.equal(off['rendering:geometry_profile'],undefined);
 values.set(prefix+'6',JSON.stringify(active));values.set(branch(6)+'geometry:canonical',true);
 context.clearOverride(6,'geometry:canonical');assert.equal(values.has(branch(6)+'geometry:canonical'),false);
});
test('reference selection requires the GPU owner policy and never enables another owner',()=>{
 const {context,values,writes}=fixture();
 assert.throws(()=>context.setOverrides(6,{'rendering:gpu_reference':true}),/GPU.*profile/i);
 assert.equal(writes.length,0);assert.equal(values.has(branch(7)+'rendering:gpu_reference'),false);
});

test('canonical backing cannot be disabled while an owner still requests a rendering mode',()=>{
 const {context,values,writes}=fixture();
 values.set(branch(7)+'geometry:canonical',true);
 assert.throws(()=>context.requireContainerRenderingModesDisabled(),/container/i);
 assert.equal(writes.length,0);
 values.set(branch(7)+'geometry:canonical',false);
 context.requireContainerRenderingModesDisabled();
});

test('either saved request can be disabled after an external backing failure',()=>{
 const {context,values,writes}=fixture();
 values.set(branch(6)+'geometry:canonical',true);values.set(branch(6)+'rendering:gpu_reference',true);
 values.set('cloakfox.experimental.canvas_pipeline',false);
 context.setOverrides(6,{'geometry:canonical':false});
 assert.equal(values.get(branch(6)+'geometry:canonical'),false);
 assert.equal(values.get(branch(6)+'rendering:gpu_reference'),true);
 const pending=context.applyOverrides(6,cfg(),undefined,true);
 assert.equal(pending['rendering:geometry_profile'],null);
 context.setOverrides(6,{'rendering:gpu_reference':false});
 assert.equal(values.get(branch(6)+'rendering:gpu_reference'),false);
 assert.deepEqual(writes,[branch(6)+'geometry:canonical',branch(6)+'rendering:gpu_reference']);
});

test('clear-overrides handler rebuilds the same owner without an undefined recovery argument',()=>{
 const {context,values}=fixture();let click;
 const oldSeed='A'.repeat(43)+'=';values.set('cloakfox.container.6.math_seed',oldSeed);
 values.set(branch(6)+'geometry:canonical',true);
 values.set(prefix+'6',JSON.stringify({...cfg(),'geometry:canonical':true}));
 context.document={getElementById:()=>({addEventListener:(_event,fn)=>{click=fn;}})};
 context.selectEl={value:'6'};
 context.masterSeedPref=id=>`cloakfox.container.${id}.math_seed`;
 context.persistCloakCfg=(id,seed)=>{assert.equal(seed,oldSeed);values.set(prefix+id,JSON.stringify(context.applyOverrides(id,cfg())));};
 context.refreshContainer=()=>{};
 const source=fs.readFileSync(new URL('../../additions/browser/components/cloakfox/content/settings.js',import.meta.url),'utf8');
 const start=source.indexOf('  const clearOverridesBtn ='),end=source.indexOf('  const screenCountPref =',start);
 vm.runInContext(source.slice(start,end),context);
 click();
 assert.equal(values.has(branch(6)+'geometry:canonical'),false);
 assert.equal(JSON.parse(values.get(prefix+'6'))['geometry:canonical'],undefined);
 assert.equal(values.get('cloakfox.container.6.math_seed'),oldSeed);
});
