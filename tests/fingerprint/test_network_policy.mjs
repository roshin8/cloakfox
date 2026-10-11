import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

function load(entries = {}, resolveContainerProxy) {
  const prefs = new Map(Object.entries(entries)), callbacks = [], proxies = [];
  let filter, prefObserver;
  const Services = {prefs: {
    addObserver: (_prefix, observer) => {prefObserver=observer;},
    getChildList: prefix => [...prefs.keys()].filter(k=>k.startsWith(prefix)),
    PREF_INVALID:0, PREF_INT:64,
    getPrefType: k => !prefs.has(k) ? 0 : typeof prefs.get(k) === 'number' ? 64 : typeof prefs.get(k) === 'boolean' ? 128 : 32,
    getIntPref: (k,v) => typeof prefs.get(k) === 'number' ? prefs.get(k) : v,
    getStringPref: (k,v) => prefs.get(k) ?? v,
    setIntPref: (k,v) => prefs.set(k,v), setStringPref: (k,v) => prefs.set(k,v),
  }};
  const service = {newProxyInfoWithAuth(...args) {proxies.push(args);return {args};},newProxyInfo(...args) {proxies.push(args);return {args};},registerChannelFilter(f){filter=f;}};
  const context=vm.createContext({Services,URL,TextEncoder,btoa:s=>Buffer.from(s,'binary').toString('base64'),ChromeUtils:{importESModule:()=>({resolveContainerProxy,initIPConflicts(){}}),generateQI:()=>()=>{}},Cc:{'@mozilla.org/network/protocol-proxy-service;1':{getService:()=>service}},Ci:{nsIProtocolProxyService:{},nsIProxyInfo:{TRANSPARENT_PROXY_RESOLVES_HOST:1,ALWAYS_TUNNEL_VIA_PROXY:2}},Cr:{NS_ERROR_PROXY_CONNECTION_REFUSED:42}});
  let source=readFileSync(new URL('../../additions/browser/components/cloakfox/CloakfoxNetworkPolicy.sys.mjs',import.meta.url),'utf8').replaceAll('export function','function');
  vm.runInContext(source+'\nthis.api={normalizeProxyURL,getContainerNetwork,setContainerNetwork,initCloakfoxNetworkPolicy};',context);
  context.api.initCloakfoxNetworkPolicy();
  return {change(k,v) {prefs.set(k,v);prefObserver.observe(null,'nsPref:changed',k);},api:context.api,proxies,prefs,rawFilter:filter,filter(channel,proxy={inherited:true}) {let result='uncalled';filter.applyFilter(channel,proxy,{onProxyFilterResult: p=>{callbacks.push(p);result=p;}});return result;}};
}
const channel=(ucid=0)=>({loadInfo:{originAttributes:{userContextId:ucid}},cancel(code){this.cancelled=code;}});

test('inherit keeps existing system proxy, scoped proxy has no direct failover and resolves destination through proxy',()=>{
 const s=load({'cloakfox.container.2.network_mode':1,'cloakfox.container.2.proxy_url':'socks5://127.0.0.1:1080'});
 assert.equal(s.filter(channel(1)).inherited,true);
 s.filter(channel(2));assert.equal(s.proxies.length,1);
 const p=s.proxies[0];assert.equal(p[0],'socks');assert.equal(p[1],'127.0.0.1');assert.equal(p[2],1080);
 assert.equal(p[4],'cloakfox-container:2');assert.equal(p[5],3);assert.equal(p[7],null);
});

test('blocked and malformed strict routes cancel before returning null, never inherit direct',()=>{
 for(const entries of [
 {'cloakfox.container.2.network_mode':2},
 {'cloakfox.container.2.network_mode':1,'cloakfox.container.2.proxy_url':'garbage'},
 {'cloakfox.container.2.network_mode':17},
 ]){const s=load(entries),c=channel(2);assert.equal(s.filter(c),null);assert.equal(c.cancelled,42);assert.equal(s.proxies.length,0);}
});

test('proxy validation rejects embedded secrets, URL extras and unsafe ports',()=>{
 const s=load();for(const input of ['https://user:secret@host:443','http://host:0','http://host:65536','file:///tmp/socket','socks5://host:1080/path','http://host:8080?x=1']) assert.throws(()=>s.api.normalizeProxyURL(input));
 assert.equal(s.api.normalizeProxyURL(' http://localhost:8080 '),'http://localhost:8080');
});

test('invalid container or route cannot overwrite a working policy',()=>{
 const s=load();s.api.setContainerNetwork(3,{mode:1,proxyURL:'http://localhost:3128',webrtcMode:0});
 assert.equal(s.prefs.get('cloakfox.container.3.network_mode'),1);
 for(const id of [-1,1.5,'3',NaN])assert.throws(()=>s.api.setContainerNetwork(id,{mode:0,proxyURL:'',webrtcMode:0}));
 assert.throws(()=>s.api.setContainerNetwork(3,{mode:1,proxyURL:'bad',webrtcMode:0}));
 assert.equal(s.prefs.get('cloakfox.container.3.proxy_url'),'http://localhost:3128');
});

test('configured wrong-type modes fail closed using actual Gecko default-getter semantics',()=>{
 for(const value of ['1', true, false]) {
  const s=load({'cloakfox.container.2.network_mode':value}),c=channel(2);
  assert.equal(s.filter(c),null);assert.equal(c.cancelled,42);
 }
 const s=load({'cloakfox.container.2.webrtc_mode':'1'});
 assert.equal(s.api.getContainerNetwork(2).webrtcMode,2);
});

test('system background channels retain browser route, content-triggered and expanded-principal channels do not bypass container policy',()=>{
 const s=load({'cloakfox.container.0.network_mode':2});
 const background=channel();background.loadInfo.loadingPrincipal={isSystemPrincipal:true};
 background.loadInfo.triggeringPrincipal={isSystemPrincipal:true};
 assert.equal(s.filter(background).inherited,true);assert.equal(background.cancelled,undefined);
 for(const [loading,triggering] of [[true,false],[false,true],[false,false]]) {
  const c=channel();c.loadInfo.loadingPrincipal={isSystemPrincipal:loading};
  c.loadInfo.triggeringPrincipal={isSystemPrincipal:triggering};
  assert.equal(s.filter(c),null);assert.equal(c.cancelled,42);
 }
});

test('callback exceptions cannot cause a second callback or cancel a valid channel',()=>{
 const s=load({'cloakfox.container.2.network_mode':1,'cloakfox.container.2.proxy_url':'http://localhost:8080'});
 const c=channel(2);let calls=0;
 assert.throws(()=>s.rawFilter.applyFilter(c,null,{onProxyFilterResult(){calls++;throw Error('callback failure');}}));
 assert.equal(calls,1);assert.equal(c.cancelled,undefined);
});


test('parent publishes numeric fail-closed policy and epoch for sanitized string changes',()=>{
 const s=load({'cloakfox.container.2.network_mode':0});
 const key='cloakfox.container.2.';
 const before=s.prefs.get(key+'network_epoch');
 s.change(key+'proxy_url','http://private-proxy:3128');
 assert.ok(s.prefs.get(key+'network_epoch') > before);
 assert.equal(s.prefs.get(key+'effective_webrtc_mode'),0);
 s.change(key+'network_mode','invalid-type');
 assert.equal(s.prefs.get(key+'effective_webrtc_mode'),2);
 s.change(key+'network_mode',0);
 s.change(key+'webrtc_mode',1);
 assert.equal(s.prefs.get(key+'effective_webrtc_mode'),1);
});


test('managed HTTP credentials remain proxy-only, with exact container identity and revision isolation',async()=>{
 const entry={id:'proxy-id',revision:'revision-1',url:'http://proxy.test:8080',username:'alice',password:'secret',hasCredentials:true};
 const s=load({'cloakfox.container.2.network_mode':1,'cloakfox.container.2.proxy_url':entry.url,'cloakfox.container.2.proxy_ref':entry.id},async()=>entry);
 const c=channel(2);let calls=0;
 await new Promise(resolve=>s.rawFilter.applyFilter(c,null,{onProxyFilterResult(result){calls++;resolve(result);}}));
 assert.equal(calls,1);assert.equal(c.cancelled,undefined);
 const args=s.proxies[0];assert.equal(args[3],'Basic '+Buffer.from('alice:secret').toString('base64'));
 assert.equal(args[4],'cloakfox-managed:2:proxy-id:revision-1');assert.equal(args[5],3);assert.equal(args[7],null);
});
test('managed SOCKS5 uses native username/password API with remote DNS and no fallback',async()=>{
 const entry={id:'proxy-id',revision:'revision-1',url:'socks5://proxy.test:1080',username:'alice',password:'secret',hasCredentials:true};
 const s=load({'cloakfox.container.3.network_mode':1,'cloakfox.container.3.proxy_url':entry.url,'cloakfox.container.3.proxy_ref':entry.id},async()=>entry);
 await new Promise(resolve=>s.rawFilter.applyFilter(channel(3),null,{onProxyFilterResult:resolve}));
 const args=s.proxies[0];assert.equal(args[0],'socks');assert.equal(args[3],'alice');assert.equal(args[4],'secret');
 assert.equal(args[5],'');assert.equal(args[6],'cloakfox-managed:3:proxy-id:revision-1');assert.equal(args[7],3);assert.equal(args[9],null);
});
test('locked or missing managed credentials cancel before exactly one callback',async()=>{
 const s=load({'cloakfox.container.2.network_mode':1,'cloakfox.container.2.proxy_url':'http://proxy.test:8080','cloakfox.container.2.proxy_ref':'missing'},async()=>{throw Error('Login store unavailable');});
 const c=channel(2);let calls=0;
 await new Promise(resolve=>s.rawFilter.applyFilter(c,{inherited:true},{onProxyFilterResult(result){assert.equal(c.cancelled,42);assert.equal(result,null);calls++;resolve();}}));
 assert.equal(calls,1);assert.equal(s.proxies.length,0);
});
