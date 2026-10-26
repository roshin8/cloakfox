import {test} from 'node:test';
import assert from 'node:assert/strict';
let serial = 0;
async function harness() {
 const prefs = new Map([['cloakfox.ip_conflicts.enabled',true]]), calls=[];
 const replies = new Map(), windows=[];
 globalThis.Services = {
  prefs:{getStringPref:(k,d)=>prefs.get(k)??d,getBoolPref:(k,d)=>prefs.get(k)??d,getIntPref:(k,d)=>prefs.get(k)??d,getChildList:p=>[...prefs.keys()].filter(k=>k.startsWith(p)),getPrefType:k=>typeof prefs.get(k)==='boolean'?128:typeof prefs.get(k)==='number'?64:32,setStringPref:(k,v)=>prefs.set(k,v),setBoolPref:(k,v)=>prefs.set(k,v),savePrefFile(){}},
  obs:{notifyObservers(){},addObserver(){}},wm:{getEnumerator:()=>windows},
  io:{newURI:spec=>({spec})},uuid:{generateUUID:()=>({toString:()=>`token-${serial}`})},
  scriptSecurityManager:{createContentPrincipal:(uri,attrs)=>({uri,attrs}),getSystemPrincipal:()=>({system:true})}
 };
 globalThis.Ci={nsILoadInfo:{SEC_ALLOW_CROSS_ORIGIN_SEC_CONTEXT_IS_NULL:1},nsIContentPolicy:{TYPE_OTHER:2},nsIRequest:{LOAD_ANONYMOUS:1,LOAD_BYPASS_CACHE:2,INHIBIT_CACHING:4},nsIHttpChannel:{}};
 globalThis.Cr={NS_ERROR_NET_TIMEOUT:1,NS_ERROR_FILE_TOO_BIG:2};
 globalThis.Components={isSuccessCode:s=>s===0}; globalThis.Cu={reportError:e=>{throw e;}};
 globalThis.ChromeUtils={importESModule(path){
  if(path.includes('PrivateBrowsingUtils'))return {PrivateBrowsingUtils:{isWindowPrivate:w=>!!w.isPrivate}};
  if(path.includes('NetworkPolicy'))return {getContainerNetwork:()=>({mode:0})};
  if(path.includes('Timer'))return {setTimeout:()=>1,clearTimeout(){}};
  return {NetUtil:{readInputStreamToString:s=>s,newChannel(options){
   const channel={loadFlags:0,responseStatus:200,QueryInterface(){return this;},cancel(){},asyncOpen(listener){
    calls.push({options,channel}); const answer=replies.get(options.uri.spec);
    queueMicrotask(()=>{if(answer instanceof Error||answer===undefined)listener.onStopRequest(channel,1);else {const body=JSON.stringify({ip:answer});listener.onDataAvailable(channel,body,0,body.length);listener.onStopRequest(channel,0);}});
   }};return channel;
  }}};
 }};
 const m=await import(`../../additions/browser/components/cloakfox/CloakfoxIPConflicts.sys.mjs?dual=${++serial}`);
 function addresses(v4='192.0.2.1',v6='2001:db8::1') {replies.clear();if(v4)replies.set('https://api.ipify.org?format=json',v4);if(v6)replies.set('https://api6.ipify.org?format=json',v6);}
 async function visit(id,url='https://example.com/path?secret=1',{privateBrowsingId=0}={}) {
  const browser={isConnected:true,contentPrincipal:{originAttributes:{userContextId:id,privateBrowsingId}},currentURI:{spec:url},loadURI(uri){this.currentURI=uri;}};
  const win={gBrowser:{addTabsProgressListener(l){this.listener=l;},getNotificationBox(){throw Error('unexpected notice');}},addEventListener(){}};
  windows.push(win);m.initIPConflicts();
  // Each harness attaches its single test window on the first visit.
  win.gBrowser.listener.onLocationChange(browser,{isTopLevel:true},null,{scheme:'https',spec:url});
  await new Promise(r=>setImmediate(r));return browser;
 }
 return {m,prefs,calls,replies,addresses,visit,windows};
}
test('dual measurements preserve routing/privacy, cache and each address family',async()=>{
 const {m,calls,addresses}=await harness();addresses();
 const r=await m.checkContainerIP(2);assert.equal(r.ipv4,'192.0.2.1');assert.equal(r.ipv6,'2001:db8::1');assert.equal(r.ip,r.ipv4);assert.deepEqual(r.errors,{ipv4:null,ipv6:null});
 assert.equal(calls.length,2);for(const {options,channel} of calls){assert.equal(options.loadingPrincipal.attrs.userContextId,2);assert.equal(channel.loadFlags,7);assert.equal(channel.redirectionLimit,0);}
 assert.equal(await m.checkContainerIP(2),r);assert.equal(calls.length,2);
 assert.equal(m.ipConflictResults()[0].ipv6,r.ipv6);
 m.clearIPHistory(r.ipv6);await m.checkContainerIP(2);assert.equal(calls.length,4);
});
test('family mismatches fail closed, fallback validates, and a route change invalidates both',async()=>{
 const {m,prefs,addresses,replies}=await harness();addresses(null,'2001:db8::4');replies.set('https://api.ipify.org?format=json','2001:db8::9');replies.set('https://httpbin.org/ip','2001:db8::9');
 const r=await m.checkContainerIP(1);assert.equal(r.ipv4,null);assert.equal(r.ipv6,'2001:db8::4');assert.ok(r.errors.ipv4);assert.equal(r.ip,r.ipv6);
 addresses('192.0.2.2',null);replies.set('https://api64.ipify.org?format=json','192.0.2.3');const partial=await m.checkContainerIP(1,{force:true});assert.equal(partial.ipv6,null);assert.ok(partial.errors.ipv6);
 addresses();const pending=m.checkContainerIP(1,{force:true});prefs.set('cloakfox.container.1.network_epoch',1);const changed=await pending;assert.equal(changed.ip,null);assert.equal(changed.ipv4,null);assert.equal(changed.ipv6,null);assert.ok(changed.errors.ipv4);assert.ok(changed.errors.ipv6);
});
test('comparison includes IPv6 overlap and supports legacy IPv6 records',async()=>{
 const {m}=await harness();const current={ucid:1,ipv4:'192.0.2.1',ipv6:'2001:db8::1',expires:200};
 assert.deepEqual(m.matchingIPRecords(current,[{ucid:2,ip:'2001:db8::1',expires:200},{ucid:3,ipv4:'192.0.2.9',ipv6:'2001:db8::1',expires:200}],100).map(r=>r.ucid),[2,3]);
});
test('IPv6-only hostname warning retains unknown family on recheck and records both on continue',async()=>{
 const {m,addresses,prefs,visit}=await harness();addresses();m.recordIPAccess('2001:db8::1',9,'https://example.com/old');
 const browser=await visit(2);const token=browser.currentURI.spec.split('token=')[1];assert.ok(token);
 let warning=m.getIPWarning(token);assert.equal(warning.ipv4,'192.0.2.1');assert.equal(warning.ipv6,'2001:db8::1');assert.deepEqual(warning.matches,[{ip:'2001:db8::1',family:'ipv6',conflicts:[9]}]);
 addresses('192.0.2.7',null);const unknown=await m.resolveIPWarning(token,'recheck');assert.ok(unknown.error);assert.equal(unknown.continued,undefined);warning=m.getIPWarning(token);assert.equal(warning.ipv4,'192.0.2.7');assert.equal(warning.ipv6,null);
 addresses('192.0.2.7','2001:db8::7');assert.deepEqual(await m.resolveIPWarning(token,'recheck'),{continued:true});
 assert.equal(browser.currentURI.spec,'https://example.com/path?secret=1');assert.deepEqual(m.ipHistory().filter(r=>r.ucid===2).map(r=>r.ip).sort(),['192.0.2.7','2001:db8::7']);assert.ok(m.ipHistory().every(r=>r.urls.every(u=>!u.includes('?'))));
});
test('IP action exempts only matching addresses, and cross-host observations never warn',async()=>{
 const {m,addresses,visit}=await harness();addresses();m.recordIPAccess('2001:db8::1',9,'https://example.com/');
 const browser=await visit(2);const token=browser.currentURI.spec.split('token=')[1];await m.resolveIPWarning(token,'ip');assert.deepEqual(m.ipExceptions(),['2001:db8::1']);assert.equal(m.ipHistory().filter(r=>r.ucid===2).length,2);
});
test('website action excludes the warning hostname only in its container and preserves other rules',async()=>{
 const {m,addresses,visit,prefs,calls}=await harness();addresses();
 m.setIPRules({mode:'selected',include:['example.com','other.test'],exclude:['existing.test']});
 m.recordIPAccess('192.0.2.1',9,'https://example.com/');
 const browser=await visit(2);const token=browser.currentURI.spec.split('token=')[1];
 assert.deepEqual(await m.resolveIPWarning(token,'website'),{continued:true});
 assert.equal(browser.currentURI.spec,'https://example.com/path?secret=1');
 assert.deepEqual(m.getIPRules(2),{mode:'selected',include:['example.com','other.test'],exclude:['existing.test','example.com']});
 assert.deepEqual(m.getIPRules(),{mode:'selected',include:['example.com','other.test'],exclude:['existing.test']});
 assert.equal(m.shouldCheckWebsite(2,'https://sub.example.com/'),false);
 assert.equal(m.shouldCheckWebsite(2,'https://other.test/'),true);
 assert.equal(m.shouldCheckWebsite(3,'https://example.com/'),true);
 assert.deepEqual(m.ipExceptions(),[]);
 assert.equal(prefs.has('cloakfox.container.2.allow_shared_ip'),false);
 assert.equal(m.hasTemporaryIPAllowance(2),false);
 assert.equal(calls.length,2);
 await assert.rejects(m.resolveIPWarning(token,'website'),/expired/);
});
test('website action refuses a full exclusion list rather than dropping an existing rule',async()=>{
 const {m,addresses,visit}=await harness();addresses();
 const exclude=Array.from({length:200},(_,i)=>`host${i}.test`);
 m.setIPRules({mode:'all',include:[],exclude},2);m.recordIPAccess('192.0.2.1',9,'https://example.com/');
 const browser=await visit(2);const token=browser.currentURI.spec.split('token=')[1];
 await assert.rejects(m.resolveIPWarning(token,'website'),/limit/i);
 assert.deepEqual(m.getIPRules(2).exclude,exclude);assert.ok(browser.currentURI.spec.includes('ip-warning.html'));
});
test('actual visits record both addresses without creating unscoped history',async()=>{
 const {m,addresses,visit}=await harness();addresses();m.recordIPAccess('2001:db8::1',9,'https://elsewhere.test/');
 const browser=await visit(0);assert.equal(browser.currentURI.spec,'https://example.com/path?secret=1');assert.deepEqual(m.ipHistory().filter(r=>r.ucid===0).map(r=>r.ip).sort(),['192.0.2.1','2001:db8::1']);
});
test('fallbacks retain separate families; fully failed result remains unknown',async()=>{
 const {m,addresses,replies}=await harness();addresses(null,null);
 replies.set('https://httpbin.org/ip','192.0.2.50');replies.set('https://api64.ipify.org?format=json','2001:db8::50');
 const fallback=await m.checkContainerIP(3);assert.equal(fallback.ipv4,'192.0.2.50');assert.equal(fallback.ipv6,'2001:db8::50');
 replies.clear();const unknown=await m.checkContainerIP(3,{force:true});assert.equal(unknown.ip,null);assert.equal(unknown.ipv4,null);assert.equal(unknown.ipv6,null);assert.ok(unknown.error);assert.ok(unknown.errors.ipv4);assert.ok(unknown.errors.ipv6);
});
test('required conflicting families persist through repeated unknown rechecks',async()=>{
 const {m,addresses,visit}=await harness();addresses();m.recordIPAccess('2001:db8::1',9,'https://example.com/');
 const browser=await visit(2);const token=browser.currentURI.spec.split('token=')[1];addresses('192.0.2.9',null);
 assert.ok((await m.resolveIPWarning(token,'recheck')).error);assert.ok((await m.resolveIPWarning(token,'recheck')).error);
 assert.ok(browser.currentURI.spec.includes('ip-warning.html'));
 addresses('192.0.2.9','2001:db8::1');const conflict=await m.resolveIPWarning(token,'recheck');assert.equal(conflict.conflict,true);assert.equal(conflict.matches[0].family,'ipv6');assert.equal(conflict.ipv4,'192.0.2.9');
});
test('an allowed family cannot hide a conflicting other family',async()=>{
 const {m,addresses,visit}=await harness();addresses();m.recordIPAccess('192.0.2.1',7,'https://example.com/');m.recordIPAccess('2001:db8::1',9,'https://example.com/');m.setIPException('192.0.2.1',true);
 const browser=await visit(2);const warning=m.getIPWarning(browser.currentURI.spec.split('token=')[1]);assert.deepEqual(warning.matches,[{ip:'2001:db8::1',family:'ipv6',conflicts:[9]}]);assert.deepEqual(warning.conflicts,[9]);
});

test('navigation checks remain opt-in and exclude private windows',async()=>{
 const disabled=await harness();disabled.addresses();disabled.prefs.set('cloakfox.ip_conflicts.enabled',false);await disabled.visit(1);assert.equal(disabled.calls.length,0);assert.deepEqual(disabled.m.ipHistory(),[]);
 const privateWindow=await harness();privateWindow.addresses();await privateWindow.visit(1,'https://example.com/',{privateBrowsingId:1});assert.equal(privateWindow.calls.length,0);assert.deepEqual(privateWindow.m.ipHistory(),[]);
});
test('pending requests coalesce and completed cache is discarded on route change',async()=>{
 const {m,addresses,prefs,calls}=await harness();addresses();
 const [first,second]=await Promise.all([m.checkContainerIP(4),m.checkContainerIP(4)]);assert.equal(first,second);assert.equal(calls.length,2);
 prefs.set('cloakfox.container.4.network_epoch',2);assert.deepEqual(m.ipConflictResults(),[]);await m.checkContainerIP(4);assert.equal(calls.length,4);
});
test('allow matching IPs rejects unknown results without silently continuing',async()=>{
 const {m,addresses,visit}=await harness();addresses();m.recordIPAccess('2001:db8::1',9,'https://example.com/');
 const browser=await visit(2);const token=browser.currentURI.spec.split('token=')[1];addresses('192.0.2.9',null);
 assert.ok((await m.resolveIPWarning(token,'recheck')).error);
 await assert.rejects(m.resolveIPWarning(token,'ip'),/Recheck|Continue once/);
 assert.ok(browser.currentURI.spec.includes('ip-warning.html'));assert.deepEqual(m.ipExceptions(),[]);assert.equal(m.ipHistory().filter(r=>r.ucid===2).length,0);
});
test('explicit unknown family fields cannot resurrect a stale legacy alias',async()=>{
 const {m}=await harness();const others=[{ucid:2,ip:'2001:db8::1',expires:200}];
 assert.deepEqual(m.matchingIPRecords({ucid:1,ip:'2001:db8::1',ipv4:null,ipv6:null,expires:200},others,100),[]);
 assert.deepEqual(m.matchingIPRecords({ucid:1,ip:'2001:db8::1',expires:200},others,100),others);
});
test('route results attribute overlap to the matching family instead of the primary alias',async()=>{
 const {m,addresses}=await harness();addresses('192.0.2.1','2001:db8::1');await m.checkContainerIP(1);
 addresses('192.0.2.2','2001:db8::1');await m.checkContainerIP(2);
 const rows=m.ipConflictResults();assert.deepEqual(rows[0].matches,[{ip:'2001:db8::1',family:'ipv6',conflicts:[2]}]);assert.deepEqual(rows[1].matches,[{ip:'2001:db8::1',family:'ipv6',conflicts:[1]}]);assert.deepEqual(rows[0].conflicts,[2]);
});
test('route results list each matching family and deduplicate aggregate containers',async()=>{
 const {m,addresses,prefs}=await harness();addresses();await m.checkContainerIP(1);await m.checkContainerIP(2);
 const row=m.ipConflictResults().find(r=>r.ucid===1);assert.deepEqual(row.matches,[{ip:'192.0.2.1',family:'ipv4',conflicts:[2]},{ip:'2001:db8::1',family:'ipv6',conflicts:[2]}]);assert.deepEqual(row.conflicts,[2]);
 prefs.set('cloakfox.container.2.network_epoch',1);assert.deepEqual(m.ipConflictResults()[0].matches,[]);assert.deepEqual(m.ipConflictResults()[0].conflicts,[]);
});

test('switching lookup route clears cached results and rejects invalid modes',async()=>{
 const {m,addresses}=await harness();addresses();
 assert.equal(m.getIPCheckRoute(),'background');
 await m.checkContainerIP(2);assert.equal(m.ipConflictResults().length,1);
 assert.throws(()=>m.setIPCheckRoute('anything'),/Invalid/);
 m.setIPCheckRoute('tab');assert.equal(m.getIPCheckRoute(),'tab');
 assert.deepEqual(m.ipConflictResults(),[]);
 m.setIPCheckRoute('background');
 assert.deepEqual(m.ipConflictResults(),[]);
});
test('route changes discard in-flight checks without repopulating the cache',async()=>{
 const {m,addresses}=await harness();addresses();
 const old=m.checkContainerIP(2);
 m.setIPCheckRoute('tab');
 const result=await old;
 assert.equal(result.ip,null);assert.match(result.error,/Route changed/);
 assert.deepEqual(m.ipConflictResults(),[]);
});
test('tab mode uses real container tabs, never background channels, and closes probes',async()=>{
 const {m,windows,calls}=await harness();
 const opened=[],removed=[];
 globalThis.Ci.nsIWebProgress={NOTIFY_STATE_WINDOW:1};
 globalThis.Ci.nsIWebNavigation={LOAD_FLAGS_BYPASS_CACHE:256};
 globalThis.Ci.nsIWebProgressListener={STATE_STOP:1,STATE_IS_WINDOW:2};
 globalThis.ChromeUtils.registerWindowActor=()=>{};
 globalThis.ChromeUtils.generateQI=()=>()=>{};
 const win={gBrowser:{
  addTab(_url,options){
   let listener;
   const browser={isConnected:true,addProgressListener(l){listener=l;},removeProgressListener(){},
    loadURI(uri){assert.equal(tab.hidden,true,'Probe must be hidden before navigation');this.currentURI=uri;this.browsingContext.currentWindowGlobal={getActor:()=>({sendQuery:async()=>({url:uri.spec,body:JSON.stringify({ip:uri.spec.includes('api6.')?'2001:db8::1':'192.0.2.2'})})})};queueMicrotask(()=>listener.onStateChange({isTopLevel:true},null,3,0));},
    browsingContext:{},currentURI:{spec:'about:blank'}};
   const tab={linkedBrowser:browser};opened.push({options,tab});return tab;
  },hideTab(tab){tab.hidden=true;},removeTab(tab){removed.push(tab);},
 },addEventListener(){}};
 windows.push(win);Services.wm.getMostRecentWindow=()=>win;
 m.setIPCheckRoute('tab');
 const result=await m.checkContainerIP(16);
 assert.equal(result.ipv4,'192.0.2.2');assert.equal(result.ipv6,'2001:db8::1');
 assert.equal(calls.length,0);assert.equal(opened.length,2);assert.equal(removed.length,2);
 assert.ok(opened.every(({options,tab})=>options.userContextId===16 && options.skipBackgroundNotify===true && tab.hidden && tab.linkedBrowser.__cloakfoxIPProbe));
 const stale=m.checkContainerIP(16,{force:true});m.setIPCheckRoute('background');
 assert.equal((await stale).ip,null);assert.equal(removed.length,4);
 assert.deepEqual(m.ipConflictResults(),[]);
});

test('saved history is retained but never compared across lookup modes',async()=>{
 const {m}=await harness();
 m.recordIPAccess('192.0.2.1',2,'https://example.com/');
 m.setIPCheckRoute('tab');
 assert.deepEqual(m.conflictForIP(3,'192.0.2.1','https://example.com/'),[]);
 m.recordIPAccess('192.0.2.1',4,'https://example.com/');
 assert.deepEqual(m.conflictForIP(3,'192.0.2.1','https://example.com/'),[4]);
 m.setIPCheckRoute('background');
 assert.deepEqual(m.conflictForIP(3,'192.0.2.1','https://example.com/'),[2]);
 assert.equal(m.ipHistory().length,2);
});
