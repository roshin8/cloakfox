import test from 'node:test';import assert from 'node:assert/strict';import vm from 'node:vm';import {readFileSync} from 'node:fs';
function load(name,exports){const prefs=new Map();const services={prefs:{getStringPref:(k,d)=>prefs.get(k)??d,getIntPref:(k,d)=>prefs.get(k)??d,getBoolPref:(k,d)=>prefs.get(k)??d,setStringPref:(k,v)=>prefs.set(k,v),setIntPref:(k,v)=>prefs.set(k,v),setBoolPref:(k,v)=>prefs.set(k,v),clearUserPref:k=>prefs.delete(k),savePrefFile(){}},dns:{clearCache(){}},eTLD:{getBaseDomainFromHost:h=>{if(!h.includes('.')||/^\d/.test(h))throw Error('invalid');return h.split('.').slice(-2).join('.');}}};const context=vm.createContext({URL,Services:services,Date});vm.runInContext(readFileSync(new URL(`../../additions/browser/components/cloakfox/${name}.sys.mjs`,import.meta.url),'utf8').replace(/^export /gm,'')+`\nthis.api={${exports}};`,context);return {api:context.api,prefs,services};}
test('tracking exceptions require registrable hosts and preserve unrelated lists',()=>{
 const {api,prefs}=load('CloakfoxTrackingProtection','normalizeTrackingHost,setQueryException,getTrackingProtection');
 for(const host of ['*','https://site.test','site.test/path','localhost','127.0.0.1'])assert.throws(()=>api.normalizeTrackingHost(host));
 assert.equal(api.normalizeTrackingHost('child.site.test'),'site.test');
 api.setQueryException('a.test',true);api.setQueryException('b.test',true);api.setQueryException('a.test',false);
 assert.equal(prefs.get('privacy.query_stripping.allow_list'),'b.test');
});
test('DNS secure-only needs numeric bootstrap and never turns guard off during apply',()=>{
 const {api,prefs}=load('CloakfoxDNS','validateDNSPolicy,setDNSPolicy,getDNSPolicy');
 assert.throws(()=>api.validateDNSPolicy({mode:'only',resolver:'https://resolver.test/dns-query',bootstrap:''}));
 for(const resolver of ['http://resolver.test/dns-query','https://user:pass@resolver.test/dns-query','https://resolver.test/dns-query#fragment'])assert.throws(()=>api.validateDNSPolicy({mode:'only',resolver,bootstrap:'1.1.1.1'}));
 api.setDNSPolicy({mode:'only',resolver:'https://resolver.test/dns-query',bootstrap:'1.1.1.1'});
 assert.equal(prefs.get('cloakfox.dns.fail_closed'),true);assert.equal(prefs.get('network.trr.mode'),3);
 api.setDNSPolicy({mode:'fallback',resolver:'https://resolver.test/dns-query',bootstrap:'1.1.1.1'});assert.equal(prefs.get('cloakfox.dns.fail_closed'),false);assert.equal(prefs.get('network.trr.mode'),2);
});

test('DNS rejects malformed input before changing prefs and Firefox defaults clear explicit policy',()=>{
 const {api,prefs}=load('CloakfoxDNS','validateDNSPolicy,setDNSPolicy,getDNSPolicy');
 for(const bootstrap of ['999.1.1.1','resolver.test',{},'1.2.3.4:53'])assert.throws(()=>api.setDNSPolicy({mode:'only',resolver:'https://resolver.test/dns-query',bootstrap}));
 assert.equal(prefs.size,0);
 api.setDNSPolicy({mode:'only',resolver:'https://resolver.test/dns-query',bootstrap:'2001:db8::1'});
 assert.equal(api.getDNSPolicy().bootstrap,'2001:db8::1');
 api.setDNSPolicy({mode:'firefox'});
 assert.equal(prefs.has('network.trr.uri'),false);
 assert.equal(prefs.has('network.trr.bootstrapAddr'),false);
 assert.equal(api.getDNSPolicy().mode,'firefox');
 assert.equal(prefs.get('cloakfox.dns.fail_closed'),false);
});

test('existing native encrypted-only mode is not displayed as Firefox defaults',()=>{
 const {api,prefs}=load('CloakfoxDNS','getDNSPolicy');
 prefs.set('network.trr.mode',3);prefs.set('network.trr.uri','https://owner.test/dns-query');
 assert.equal(api.getDNSPolicy().mode,'only');
 assert.equal(api.getDNSPolicy().resolver,'https://owner.test/dns-query');
});


test('bounce exception scope lives in a private permission type, independent of shared OA preferences',()=>{
 const {api,prefs,services}=load('CloakfoxTrackingProtection','bouncePermissionType,setBounceException,listBounceExceptions');
 const records=new Map();
 services.io={newURI:value=>({host:new URL(value).hostname})};
 services.scriptSecurityManager={createContentPrincipal:(URI,attrs)=>({URI,originAttributes:attrs})};
 services.perms={ALLOW_ACTION:1,EXPIRE_TIME:2,
  addFromPrincipal:(principal,type,capability,expireType,expireTime)=>records.set(type,{principal,type,capability,expireType,expireTime}),
  removeFromPrincipal:(_principal,type)=>records.delete(type),
  getAllByTypes:types=>[...records.values()].filter(p=>types.includes(p.type))};
 prefs.set('permissions.isolateBy.userContext',false);
 api.setBounceException(7,'site.test',Date.now()+60000);
 assert.equal(api.listBounceExceptions(7).length,1);assert.equal(api.listBounceExceptions(8).length,0);
 assert.equal(records.get('cloakfox-bounce:7:0').principal.originAttributes.userContextId,undefined);
 assert.equal(api.bouncePermissionType(7,1),'cloakfox-bounce:7:1');
 prefs.set('permissions.isolateBy.userContext',true);
 assert.equal(api.listBounceExceptions(7).length,1);
 api.setBounceException(7,'site.test',0);assert.equal(records.size,0);
 for(const id of [-1,0x80000000,1.5])assert.throws(()=>api.bouncePermissionType(id));
});

test('native narrow bounce lookup stays out of the broad allowlist cache', t=>{
 let source;
 try{source=readFileSync(new URL('../../firefox-src/toolkit/components/antitracking/bouncetrackingprotection/BounceTrackingAllowList.cpp',import.meta.url),'utf8');}
 catch{t.skip('Native source absent');return;}
 const types=source.slice(source.indexOf('nsTArray<nsCString> BounceTrackingAllowList::GetAllowListPermissionTypes()'),source.indexOf('nsresult BounceTrackingAllowList::IsAllowListPermission'));
 assert.ok(!types.includes('cloakfox-bounce'));
 assert.ok(source.includes('ContentBlockingAllowListCache::CheckForBaseDomain('));
 assert.ok(source.includes('type.AppendInt(aOriginAttributes.mUserContextId)'));
 assert.ok(source.includes('type.AppendInt(aOriginAttributes.mPrivateBrowsingId)'));
 assert.ok(source.includes('CreateContentPrincipal(uri, OriginAttributes{})'));
 assert.ok(source.includes('TestExactPermissionFromPrincipal(principal, type,'));
});


test('bounce cleanup removes both exact scopes while retaining other containers and ordinary permissions',()=>{
 const {api,services}=load('CloakfoxTrackingProtection','clearBounceExceptions');
 const types=new Set(['cloakfox-bounce:7:0','cloakfox-bounce:7:1','cloakfox-bounce:70:0','cloakfox-bounce:8:0','camera','cookie']);
 const removed=[];services.perms={removeByType:type=>{removed.push(type);types.delete(type);}};
 api.clearBounceExceptions(7);
 assert.deepEqual(removed,['cloakfox-bounce:7:0','cloakfox-bounce:7:1']);
 assert.deepEqual([...types],['cloakfox-bounce:70:0','cloakfox-bounce:8:0','camera','cookie']);
 assert.throws(()=>api.clearBounceExceptions(-1));assert.equal(removed.length,2);
});

test('startup container-deleted observer clears typed grants without opening settings',()=>{
 const source=readFileSync(new URL('../../additions/browser/components/cloakfox/CloakfoxSeedSync.sys.mjs',import.meta.url),'utf8');
 const block=source.slice(source.indexOf('const CONTAINER_TOPICS ='),source.indexOf('// Bridge cloakfox.opt.timer_quantization_off'));
 const cleared=[];let seeded=0,published=0;
 const context=vm.createContext({ChromeUtils:{importESModule:()=>({clearBounceExceptions:id=>cleared.push(id)})},
   Cu:{reportError:error=>{throw error;}},ensureSeedsForAllContainers:()=>seeded++,publish:()=>published++});
 vm.runInContext(block+'\nthis.observer=containerObserver;this.topics=CONTAINER_TOPICS;',context);
 assert.ok(context.topics.includes('contextual-identity-deleted'));
 context.observer.observe({wrappedJSObject:{userContextId:7}},'contextual-identity-deleted');
 assert.deepEqual(cleared,[7]);assert.equal(seeded,0);assert.equal(published,0);
 context.observer.observe({},'contextual-identity-created');assert.equal(seeded,1);assert.equal(published,1);
});
