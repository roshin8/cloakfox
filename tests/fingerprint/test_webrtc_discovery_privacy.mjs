import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(process.env.SYNC_SOURCE || new URL('../../additions/browser/components/cloakfox/CloakfoxWebRTCSync.sys.mjs',import.meta.url),'utf8').replace('export function initCloakfoxWebRTCSync','function initCloakfoxWebRTCSync');
function fixture(){
 const prefs=new Map([['cloakfox.enabled',true]]), observers=new Map(),data=new Map(),requests=[];
 const context=vm.createContext({AbortController,setTimeout,clearTimeout,ChromeUtils:{importESModule:()=>({setTimeout,clearTimeout})},
 Services:{prefs:{getBoolPref:(k,f)=>prefs.get(k)??f,addObserver:(k,o)=>observers.set(k,o)},obs:{addObserver(){},removeObserver(){}},ppmm:{sharedData:{set:(k,v)=>data.set(k,v),delete:k=>data.delete(k),flush(){}}}},
 fetch:(url,opts)=>new Promise(resolve=>requests.push({url,signal:opts.signal,resolve}))});
 vm.runInContext(source+'\ninitCloakfoxWebRTCSync();',context);
 return {data,requests,set(k,v){prefs.set(k,v);observers.get(k)?.observe(null,'nsPref:changed',k)}};
}
test('external discovery requires separate opt-in',()=>{const f=fixture();assert.equal(f.requests.length,0)});
test('disabling discovery aborts pending requests and prevents late publication/fallback',async()=>{
 const f=fixture();f.set('cloakfox.webrtc.external_ip_discovery',true);assert.equal(f.requests.length,2);
 f.set('cloakfox.webrtc.external_ip_discovery',false);assert.ok(f.requests.every(r=>r.signal.aborted));
 for(const r of f.requests)r.resolve({ok:true,text:async()=>r.url.includes('api64')?'2001:db8::1':'192.0.2.1'});
 await new Promise(r=>setImmediate(r));assert.equal(f.data.size,0);assert.equal(f.requests.length,2);
});
test('master switch also cancels discovery',()=>{
 const f=fixture();f.set('cloakfox.webrtc.external_ip_discovery',true);f.set('cloakfox.enabled',false);
 assert.ok(f.requests.every(r=>r.signal.aborted));for(const r of f.requests)r.resolve({ok:false});
});
test('opted-in discovery publishes both valid families',async()=>{
 const f=fixture();f.set('cloakfox.webrtc.external_ip_discovery',true);
 for(const r of f.requests)r.resolve({ok:true,text:async()=>r.url.includes('api64')?'2001:db8::1':'192.0.2.1'});
 await new Promise(r=>setImmediate(r));
 assert.equal(f.data.get('cloakfox-public-ipv4'),'192.0.2.1');assert.equal(f.data.get('cloakfox-public-ipv6'),'2001:db8::1');
 f.set('cloakfox.webrtc.external_ip_discovery',false);assert.equal(f.data.size,0);
});
