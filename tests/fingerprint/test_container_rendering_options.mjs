import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {REFERENCE_GPU_PROFILES} from '../../additions/browser/components/cloakfox/CloakfoxGPUReferenceProfiles.sys.mjs';
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
 for(const key of ['geometry:canonical','rendering:gpu_reference','rendering:gpu_observed']){
  for(const bad of ['true',1,{},[]]){const {context,writes}=fixture();assert.throws(()=>context.setOverrides(6,{[key]:bad}),/boolean/i);assert.equal(writes.length,0);}
  const {context,values,writes}=fixture();values.set('cloakfox.experimental.canvas_pipeline',false);
  assert.throws(()=>context.setOverrides(6,{[key]:true,...(key==='rendering:gpu_observed'?{'rendering:gpu_reference':true}:{})}),/canonical/i);assert.equal(writes.length,0);
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

const observedKey='rendering:gpu_observed',referenceKey='rendering:gpu_reference';
test('observed request is a strict boolean and requires reference before any partial writes',()=>{
 for(const bad of ['true','false',0,1,{},[],NaN]){
  const {context,writes}=fixture();
  assert.throws(()=>context.setOverrides(6,{'navigator.language':'fr', [observedKey]:bad}),/boolean/i);
  assert.equal(writes.length,0);
 }
 const {context,values,writes}=fixture();
 values.set('cloakfox.opt.container_rendering_profiles',true);
 assert.throws(()=>context.setOverrides(6,{'navigator.language':'fr',[observedKey]:true}),/reference/i);
 assert.equal(writes.length,0);
 assert.equal(context.KEY_TYPES?.[observedKey]??vm.runInContext('KEY_TYPES["rendering:gpu_observed"]',context),'bool');
});
test('observed saved request blocks backing removal and remains removable with no dependencies or identity',()=>{
 const {context,values,writes}=fixture();
 values.set(branch(0)+observedKey,true);
 assert.throws(()=>context.requireContainerRenderingModesDisabled(),/container/i);
 values.set('cloakfox.experimental.canvas_pipeline',false);
 values.delete(prefix+'6');
 values.set(branch(6)+observedKey,true);
 context.setOverrides(6,{[observedKey]:false});
 assert.equal(values.get(branch(6)+observedKey),false);
 assert.deepEqual(writes,[branch(6)+observedKey]);
 assert.equal(values.get(branch(0)+observedKey),true);
});

function renderingControls(context,values){
 const controls=['geometry:canonical',referenceKey,observedKey].map(key=>({dataset:{containerRendering:key},closest:()=>({hidden:false})}));
 const status={textContent:''};
 context.document={querySelectorAll:()=>controls,getElementById:()=>status};
 context.getCloakCfg=id=>context.applyOverrides(id,cfg(),undefined,true);
 context.rebuildCloakCfg=(id,recovery)=>context.applyOverrides(id,cfg(),undefined,recovery);
 context.refreshContainer=()=>context.refreshContainerRenderingOptions(6,context.getCloakCfg(6));
 const source=fs.readFileSync(new URL('../../additions/browser/components/cloakfox/content/settings.js',import.meta.url),'utf8');
 const start=source.indexOf('  function refreshContainerRenderingOptions('),end=source.indexOf('  function refreshContainer()',start);
 vm.runInContext(source.slice(start,end),context);
 context.refreshContainerRenderingOptions(6,{});
 return {controls,status};
}
test('real settings handler disables reference and observed requests atomically during backing loss',()=>{
 const {context,values,writes}=fixture();
 values.set(branch(6)+referenceKey,true);values.set(branch(6)+observedKey,true);
 values.set('cloakfox.experimental.canvas_pipeline',false);
 const {controls}=renderingControls(context,values);
 assert.equal(controls[2].checked,true);assert.equal(controls[2].disabled,false);
 controls[1].checked=false;controls[1].onchange();
 assert.equal(values.get(branch(6)+referenceKey),false);
 assert.equal(values.get(branch(6)+observedKey),false);
 assert.deepEqual(writes,[branch(6)+referenceKey,branch(6)+observedKey]);
});
test('inactive observed control requires saved reference; removing observed preserves reference and other owners',()=>{
 const {context,values,writes}=fixture();
 values.set('cloakfox.opt.container_rendering_profiles',true);
 let ui=renderingControls(context,values);assert.equal(ui.controls[2].disabled,true);
 values.set(branch(6)+referenceKey,true);values.set(branch(6)+observedKey,true);
 values.set(branch(7)+observedKey,true);
 ui=renderingControls(context,values);ui.controls[2].checked=false;ui.controls[2].onchange();
 assert.equal(values.get(branch(6)+referenceKey),true);
 assert.equal(values.get(branch(6)+observedKey),false);
 assert.equal(values.get(branch(7)+observedKey),true);
 assert.deepEqual(writes,[branch(6)+observedKey]);
});

function pairedConfig(family='intel') {
 const pair=REFERENCE_GPU_PROFILES.find(p=>p.family===family);
 return {...cfg(),'webGl:vendor':pair.vendor,'webGl:renderer':pair.renderer,
  'navigator.platform':pair.os==='mac'?'MacIntel':'Win32',
  'navigator.oscpu':pair.os==='mac'?'Intel Mac OS X 10.15':'Windows NT 10.0; Win64; x64'};
}
test('observed activation validates complete profiles for owner zero and preserves all identity inputs',()=>{
 for(const owner of [0,6]) for(const family of ['intel','amd','nvidia']) {
  const {context,values,writes}=fixture();const base=pairedConfig(family);
  context.ChromeUtils.importESModule=()=>({fillPersonaKeys:()=>base});
  values.set(prefix+owner,JSON.stringify(base));
  values.set('cloakfox.opt.container_rendering_profiles',true);
  const other=values.get(prefix+'7');
  context.setOverrides(owner,{[referenceKey]:true,[observedKey]:true});
  const applied=context.applyOverrides(owner,base);
  assert.equal(applied['rendering:gpu_profile'].version,4);
  assert.equal(applied['rendering:gpu_profile'].mode,'observed-reference');
  assert.equal(applied['rendering:gpu_profile'].owner,owner);
  assert.equal(applied['fingerprint:secret'],base['fingerprint:secret']);
  assert.equal(applied['canvas:seed'],base['canvas:seed']);
  assert.equal(values.get(prefix+'7'),other);
  assert.deepEqual(writes,[branch(owner)+referenceKey,branch(owner)+observedKey]);
  context.setOverride(owner,observedKey,false);
  assert.equal(context.applyOverrides(owner,base)['rendering:gpu_profile'].version,3);
 }
});
test('unsupported Apple observed activation cannot partially change the existing reference or another override',()=>{
 const {context,values,writes}=fixture();const base=pairedConfig('apple');
 context.ChromeUtils.importESModule=()=>({fillPersonaKeys:()=>base});
 values.set(prefix+'6',JSON.stringify(base));values.set('cloakfox.opt.container_rendering_profiles',true);
 context.setOverride(6,referenceKey,true);writes.length=0;
 const before=[...values];
 assert.throws(()=>context.setOverrides(6,{'navigator.language':'fr',[observedKey]:true}),/supported/i);
 assert.deepEqual([...values],before);assert.equal(writes.length,0);
 assert.equal(context.applyOverrides(6,base)['rendering:gpu_profile'].version,3);
});
test('clearing all observed overrides restores same owner and seeds without changing other owners',()=>{
 const {context,values}=fixture();const base=pairedConfig();
 context.ChromeUtils.importESModule=()=>({fillPersonaKeys:()=>base});
 values.set(prefix+'6',JSON.stringify(base));values.set('cloakfox.opt.container_rendering_profiles',true);
 context.setOverrides(6,{[referenceKey]:true,[observedKey]:true});
 const before=values.get(prefix+'7');
 context.clearAllOverrides(6);
 const applied=context.applyOverrides(6,base);
 assert.equal(applied[observedKey],undefined);assert.equal(applied[referenceKey],undefined);
 assert.equal(applied['rendering:gpu_profile'].version,2);
 assert.equal(applied['fingerprint:secret'],base['fingerprint:secret']);
 assert.equal(applied['canvas:seed'],base['canvas:seed']);assert.equal(values.get(prefix+'7'),before);
});

test('observed compatibility defaults on only for compatible reference owners without an explicit choice',()=>{
 for(const family of ['intel','amd','nvidia']) {
  const {context,values,writes}=fixture();const base=pairedConfig(family);
  values.set('cloakfox.opt.container_rendering_profiles',true);
  values.set(branch(6)+referenceKey,true);
  const applied=context.applyOverrides(6,base);
  assert.equal(applied[observedKey],true);
  assert.equal(applied['rendering:gpu_profile'].mode,'observed-reference');
  assert.equal(applied['rendering:gpu_profile'].owner,6);
  assert.equal(applied['fingerprint:secret'],base['fingerprint:secret']);
  assert.equal(writes.length,0,'automatic defaults must not become saved overrides');
  assert.equal(context.applyOverrides(7,base)[observedKey],undefined);
  values.set(branch(6)+observedKey,false);
  assert.equal(context.applyOverrides(6,applied)['rendering:gpu_profile'].mode,'reference');
  assert.equal(context.applyOverrides(6,applied)[observedKey],false);
  values.delete(branch(6)+observedKey);
  assert.equal(context.applyOverrides(6,applied)[observedKey],true);
 }
});
test('automatic observed preference reevaluates compatibility and never enables prerequisites',()=>{
 const {context,values}=fixture();values.set('cloakfox.opt.container_rendering_profiles',true);
 values.set(branch(6)+referenceKey,true);
 const active=context.applyOverrides(6,pairedConfig());
 const apple=context.applyOverrides(6,{...active,...pairedConfig('apple')});
 assert.equal(apple[observedKey],undefined);
 assert.equal(apple['rendering:gpu_profile'].mode,'reference');
 values.set(branch(6)+referenceKey,false);
 assert.equal(context.applyOverrides(6,active)[observedKey],undefined);
 values.set('cloakfox.experimental.canvas_pipeline',false);
 values.set('cloakfox.opt.container_rendering_profiles',false);
 assert.equal(context.applyOverrides(6,pairedConfig())[observedKey],undefined);
 assert.equal(values.get('cloakfox.experimental.canvas_pipeline'),false);
});
test('real settings control reflects automatic observed admission without saving an override',()=>{
 const {context,values}=fixture();values.set('cloakfox.opt.container_rendering_profiles',true);
 values.set(branch(6)+referenceKey,true);
 const {controls}=renderingControls(context,values);
 context.refreshContainerRenderingOptions(6,{[observedKey]:true,'rendering:gpu_profile':{mode:'observed-reference'}});
 assert.equal(controls[2].checked,true);
 assert.equal(controls[2].disabled,false);
 assert.equal(values.has(branch(6)+observedKey),false);
 controls[2].checked=false;controls[2].onchange();
 assert.equal(values.get(branch(6)+observedKey),false);
});
