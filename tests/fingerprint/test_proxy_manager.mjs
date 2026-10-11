import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
function load() {
 const prefs=new Map(),logins=[];let sequence=0;
 const Services={uuid:{generateUUID:()=>`{00000000-0000-4000-8000-${String(++sequence).padStart(12,'0')}}`},prefs:{
 getStringPref:(k,d)=>prefs.get(k)??d,setStringPref:(k,v)=>prefs.set(k,v),setIntPref:(k,v)=>prefs.set(k,v),getIntPref:(k,d)=>prefs.get(k)??d,
 getChildList:p=>[...prefs.keys()].filter(k=>k.startsWith(p)),savePrefFile(){},clearUserPref:k=>prefs.delete(k)},logins:{
 async searchLoginsAsync({origin}){return logins.filter(l=>l.origin===origin)},async addLoginAsync(l){const u=new URL(l.origin);const saved={...l,origin:`${u.protocol}//${u.host}`};logins.push(saved);return saved;},async removeLoginAsync(l){logins.splice(logins.indexOf(l),1)},async modifyLoginAsync(old,l){logins.splice(logins.indexOf(old),1,l)}}};
 const network={normalizeProxyURL(s){const u=new URL(s);if(u.username||u.password||!['http:','https:','socks5:'].includes(u.protocol))throw Error('Invalid proxy');return s;},getContainerNetwork:id=>({mode:prefs.get(`cloakfox.container.${id}.network_mode`)??0,proxyURL:prefs.get(`cloakfox.container.${id}.proxy_url`)??'',webrtcMode:0})};
 const requests=[];
 Services.io={newURI:url=>({spec:url})};Services.scriptSecurityManager={createContentPrincipal:(uri,originAttributes)=>({uri,originAttributes})};
 const netUtil={newChannel(options){const channel={options,loadFlags:0,responseStatus:200,QueryInterface(){return this;},asyncOpen(listener){this.listener=listener;},cancel(status){this.listener.onStopRequest(this,status);}};requests.push(channel);return channel;},readInputStreamToString:()=>''};
 const context=vm.createContext({Services,URL,TextEncoder,btoa:s=>Buffer.from(s,'binary').toString('base64'),ChromeUtils:{importESModule:url=>url.includes('NetUtil')?{NetUtil:netUtil}:url.includes('Timer')?{setTimeout,clearTimeout}:network},Cc:{'@mozilla.org/login-manager/loginInfo;1':{createInstance:()=>({init(origin,formActionOrigin,httpRealm,username,password){Object.assign(this,{origin,formActionOrigin,httpRealm,username,password})}})}},Ci:{nsILoginInfo:{},nsIHttpChannel:{},nsILoadInfo:{SEC_ALLOW_CROSS_ORIGIN_SEC_CONTEXT_IS_NULL:1},nsIContentPolicy:{TYPE_OTHER:1},nsIRequest:{LOAD_BYPASS_CACHE:1,INHIBIT_CACHING:2,LOAD_ANONYMOUS:4}},Components:{isSuccessCode:status=>status===0},Cr:{NS_ERROR_NET_TIMEOUT:1,NS_ERROR_FAILURE:2,NS_ERROR_FILE_TOO_BIG:3},setTimeout,clearTimeout});
 const src=readFileSync(new URL('../../additions/browser/components/cloakfox/CloakfoxProxyManager.sys.mjs',import.meta.url),'utf8').replaceAll('export async function','async function').replaceAll('export function','function');
 vm.runInContext(src+'\nthis.api={listProxies,saveProxy,bindProxy,getProxyReference,removeProxy,resolveContainerProxy,testContainerProxy,getProxyCheck};',context);
 return {api:context.api,prefs,logins,Services,requests};
}
test('named proxy stores credentials only in LoginManager and emits redacted references',async()=>{
 const s=load(),p=await s.api.saveProxy({name:'Work',url:'http://proxy.test:8080',username:'alice',password:'secret-sentinel'});
 assert.equal(s.logins.length,1);assert.equal(s.logins[0].password,'secret-sentinel');
 assert.ok(!JSON.stringify([...s.prefs]).includes('secret-sentinel'));assert.ok(!JSON.stringify(p).includes('alice'));
 s.api.bindProxy(2,p.id);assert.equal(s.api.getProxyReference(2),p.id);
 assert.equal(s.prefs.get('cloakfox.container.2.proxy_url'),p.url);
 const route=await s.api.resolveContainerProxy(2);assert.equal(route.username,'alice');assert.equal(route.password,'secret-sentinel');
 assert.equal(s.api.getProxyReference(3),null);
});
test('missing reference and deleted credential fail closed; deletion blocks bound containers',async()=>{
 const s=load();assert.throws(()=>s.api.bindProxy(2,'missing'));
 const p=await s.api.saveProxy({name:'Work',url:'socks5://proxy.test:1080',username:'a',password:'b'});s.api.bindProxy(2,p.id);
 s.logins.length=0;await assert.rejects(s.api.resolveContainerProxy(2));
 await s.api.removeProxy(p.id);assert.equal(s.prefs.get('cloakfox.container.2.network_mode'),2);assert.equal(s.api.listProxies().length,0);
});
test('credential changes rotate connection isolation revision and apply to bound route',async()=>{
 const s=load(),p=await s.api.saveProxy({name:'Work',url:'http://proxy.test:8080',username:'a',password:'b'});s.api.bindProxy(2,p.id);
 const updated=await s.api.saveProxy({id:p.id,name:'Work',url:'http://other.test:8080',username:'a',password:'c'});
 assert.notEqual(updated.revision,p.revision);assert.equal(s.prefs.get('cloakfox.container.2.proxy_url'),updated.url);
 assert.equal((await s.api.resolveContainerProxy(2)).password,'c');
});


test('binding changed while LoginManager is pending never releases stale credentials',async()=>{
 const s=load(),p=await s.api.saveProxy({name:'Work',url:'http://proxy.test:8080',username:'alice',password:'secret'});s.api.bindProxy(2,p.id);
 let release;s.Services.logins.searchLoginsAsync=()=>new Promise(resolve=>{release=resolve;});
 const pending=s.api.resolveContainerProxy(2);
 s.prefs.set('cloakfox.container.2.proxy_ref','different');release(s.logins);
 await assert.rejects(pending,/route changed/);
});
test('login storage failure leaves all existing bindings blocked and preserves reference',async()=>{
 const s=load(),p=await s.api.saveProxy({name:'Work',url:'http://proxy.test:8080',username:'alice',password:'secret'});s.api.bindProxy(2,p.id);s.api.bindProxy(3,p.id);
 s.Services.logins.modifyLoginAsync=async()=>{throw Error('secret-bearing storage error');};
 await assert.rejects(s.api.saveProxy({id:p.id,name:'Work',url:p.url,username:'alice',password:'new-secret'}),error=>!error.message.includes('secret-bearing'));
 assert.equal(s.prefs.get('cloakfox.container.2.network_mode'),2);assert.equal(s.prefs.get('cloakfox.container.3.network_mode'),2);
 assert.equal(s.api.getProxyReference(2),p.id);
});
test('reject partial, oversized, and protocol-invalid credentials before mutating store',async()=>{
 const s=load();
 for(const values of [{username:'only'}, {username:'bad:name',password:'secret'}, {username:'u',password:'x'.repeat(256)}]) {
  await assert.rejects(s.api.saveProxy({name:'Work',url:'http://proxy.test:8080',...values}));
 }
 assert.equal(s.logins.length,0);assert.equal(s.api.listProxies().length,0);
});


test('explicit diagnostics require proxy mode, preserve target origin attributes and prohibit redirects/cookies',async()=>{
 const s=load();await assert.rejects(s.api.testContainerProxy(2,'https://selected.test/'));assert.equal(s.requests.length,0);
 const p=await s.api.saveProxy({name:'Work',url:'http://proxy.test:8080'});s.api.bindProxy(2,p.id);
 await assert.rejects(s.api.testContainerProxy(2,'http://selected.test/'));assert.equal(s.requests.length,0);
 const pending=s.api.testContainerProxy(2,'https://selected.test/');await new Promise(resolve=>setImmediate(resolve));
 const channel=s.requests[0];assert.equal(channel.options.loadingPrincipal.originAttributes.userContextId,2);
 assert.equal(channel.redirectionLimit,0);assert.equal(channel.loadFlags,7);
 channel.listener.onStopRequest(channel,2);
 const result=await pending;assert.equal(result.ok,false);assert.equal(s.api.getProxyCheck(2).ok,false);assert.equal(s.api.getProxyCheck(3),null);
 assert.ok(!JSON.stringify([...s.prefs]).includes('selected.test'));
});
test('route changed during diagnostic cannot publish success for another route',async()=>{
 const s=load(),p=await s.api.saveProxy({name:'Work',url:'http://proxy.test:8080'});s.api.bindProxy(2,p.id);
 const pending=s.api.testContainerProxy(2,'https://selected.test/');await new Promise(resolve=>setImmediate(resolve));
 s.prefs.set('cloakfox.container.2.network_mode',2);
 const channel=s.requests[0];channel.listener.onStopRequest(channel,0);
 const result=await pending;assert.equal(result.ok,false);assert.equal(s.api.getProxyCheck(2),null);
});

test('Rust-style origin normalization cannot collapse two named proxy credential records',async()=>{
 const s=load(),first=await s.api.saveProxy({name:'First',url:'http://shared.test:8080',username:'first',password:'first-secret'});
 const second=await s.api.saveProxy({name:'Second',url:first.url,username:'second',password:'second-secret'});
 s.api.bindProxy(1,first.id);s.api.bindProxy(2,second.id);
 assert.notEqual(s.logins[0].origin,s.logins[1].origin);
 assert.equal((await s.api.resolveContainerProxy(1)).username,'first');
 assert.equal((await s.api.resolveContainerProxy(2)).username,'second');
 await s.api.removeProxy(first.id);
 assert.equal((await s.api.resolveContainerProxy(2)).password,'second-secret');
});
