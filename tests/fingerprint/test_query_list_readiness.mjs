import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';
const sourceURL = new URL('../../firefox-src/toolkit/components/antitracking/URLQueryStrippingListService.sys.mjs', import.meta.url);
const patchURL = new URL('../../patches/cloakfox-privacy-completion.patch', import.meta.url);
function sourcesFromPatch(patch) {
  const path='toolkit/components/antitracking/URLQueryStrippingListService.sys.mjs';
  const header=`diff --git a/${path} b/${path}\n`;
  const offset=patch.indexOf(header);
  assert.notEqual(offset,-1,'Native query list service must remain in the shipped patch');
  const following=patch.indexOf('\ndiff --git ',offset+header.length);
  const section=patch.slice(offset,following<0?undefined:following+1);
  const lines=section.split('\n');
  const hunks=lines.filter(line=>line.startsWith('@@'));
  assert.equal(hunks.length,1,'Keep full native source context in the query list patch for clean-CI regression testing');
  const match=/^@@ -1,(\d+) \+1,(\d+) @@/.exec(hunks[0]);
  assert.ok(match,'Query list patch must contain full source starting at line 1');
  const before=[],after=[];
  for(const line of lines.slice(lines.indexOf(hunks[0])+1)) {
    if(line.startsWith(' ')){before.push(line.slice(1));after.push(line.slice(1));}
    else if(line.startsWith('-'))before.push(line.slice(1));
    else if(line.startsWith('+'))after.push(line.slice(1));
    else assert.equal(line,'','Unexpected query list patch metadata');
  }
  assert.equal(before.length,Number(match[1]));
  assert.equal(after.length,Number(match[2]));
  return {before:before.join('\n')+'\n',after:after.join('\n')+'\n'};
}
const sources=sourcesFromPatch(readFileSync(patchURL,'utf8'));
// The shipped patch is always exercised, including source-less CI. If a native
// tree is present, also reject drift between the patch and the implementation.
if(existsSync(sourceURL))assert.equal(readFileSync(sourceURL,'utf8'),sources.after,'Native query service drifted from shipped patch');
function fixture(source) {
  let resolveRemote;
  const pending = new Promise(resolve => { resolveRemote=resolve; });
  const prefs = new Map([['privacy.query_stripping.strip_list','utm_source fbclid'],['privacy.query_stripping.allow_list','except.test']]);
  const observers = new Map();
  const context = vm.createContext({
    Components:{ID:x=>x},
    console:{createInstance:()=>({debug(){},error(){}}),error(){}},
    ChromeUtils:{
      generateQI:()=>()=>{},
      defineESModuleGetters:target=>{target.RemoteSettings=()=>({get:()=>pending,on(){},off(){}});},
      defineLazyGetter(target,key,getter){Object.defineProperty(target,key,{configurable:true,get(){const value=getter();Object.defineProperty(target,key,{value});return value;}});},
    },
    XPCOMUtils:{defineLazyPreferenceGetter(target,key){target[key]=false;}},
    Services:{appinfo:{processType:0,PROCESS_TYPE_DEFAULT:0},
      prefs:{getStringPref:(key,fallback)=>prefs.get(key)??fallback,getBoolPref:()=>false,addObserver:(key,observer)=>observers.set(key,observer),removeObserver(){}},
      obs:{addObserver(){},removeObserver(){}},ppmm:{sharedData:{set(){},flush(){}}}},
    fetch:async()=>({ok:true,json:async()=>({global:{isGlobal:true,queryParams:[],origins:[]}})}),
  });
  const rewritten=source.replace(/import \{ XPCOMUtils \} from "resource:\/\/gre\/modules\/XPCOMUtils.sys.mjs";/,'').replace('export class URLQueryStrippingListService','globalThis.Service = class URLQueryStrippingListService');
  vm.runInContext(rewritten,context);
  return {service:new context.Service(),resolveRemote,change(key,value){prefs.set(key,value);observers.get(key)?.observe(null,'nsPref:changed',key);}};
}
function checkImmediate(source) {
  const f=fixture(source),calls=[];
  f.service.registerAndRunObserver({onQueryStrippingListUpdate:(strip,allow)=>calls.push({strip,allow})});
  return {f,calls};
}
test('native service supplies pref baseline before remote initialization and preserves live updates',async()=>{
  const {f,calls}=checkImmediate(sources.after);
  assert.ok(calls.length>0,'first navigation must not wait for Remote Settings');
  assert.equal(calls.at(-1).strip,'utm_source fbclid');
  assert.equal(calls.at(-1).allow,'except.test');
  f.change('privacy.query_stripping.allow_list','');
  assert.equal(calls.at(-1).allow,'','remove exception while remote init is pending');
  f.resolveRemote([{stripList:['remote_tag'],allowList:['remote.test']}]);
  await f.service.testWaitForInit();
  assert.equal(calls.at(-1).strip,'utm_source fbclid remote_tag');
  assert.equal(calls.at(-1).allow,'remote.test');
  f.change('privacy.query_stripping.strip_list','utm_campaign');
  assert.equal(calls.at(-1).strip,'utm_campaign remote_tag');
  f.change('privacy.query_stripping.allow_list','local.test');
  assert.equal(calls.at(-1).allow,'local.test,remote.test');
  f.change('privacy.query_stripping.allow_list','');
  assert.equal(calls.at(-1).allow,'remote.test');
});
test('original native source reproduces unprotected first-navigation initialization window',()=>{
  assert.equal(checkImmediate(sources.before).calls.length,0);
});
