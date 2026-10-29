import test from 'node:test';import assert from 'node:assert/strict';import vm from 'node:vm';import {readFileSync} from 'node:fs';
const context=vm.createContext({});
vm.runInContext(readFileSync(new URL('../../additions/browser/components/cloakfox/CloakfoxInspector.sys.mjs',import.meta.url),'utf8').replaceAll('export function','function').replaceAll('export async function','async function')+'\nthis.inspect=inspectConsistency;',context);
const cfg={'navigator.userAgent':'Mozilla/5.0 Firefox/155.0','headers.User-Agent':'Mozilla/5.0 Firefox/155.0','navigator.platform':'Win32','navigator.language':'en-US','screen.width':1920,'screen.height':1080,'screen.availWidth':1920,'screen.availHeight':1040,'navigator.hardwareConcurrency':8};
test('coherent window and worker measurements show no contradictions',()=>{
 const measured={window:{userAgent:cfg['navigator.userAgent'],platform:'Win32',language:'en-US',hardwareConcurrency:8},worker:{userAgent:cfg['navigator.userAgent'],platform:'Win32',language:'en-US',hardwareConcurrency:8}};
 assert.equal(context.inspect(cfg,measured).filter(x=>x.level==='contradiction').length,0);
});
test('config contradictions are distinguished from measured mismatches and unavailable worker',()=>{
 const results=context.inspect({...cfg,'headers.User-Agent':'other','screen.availWidth':2000},{window:{language:'de-DE'},workerError:'CSP blocked'});
 assert.ok(results.some(x=>x.code==='header-ua'&&x.source==='configuration'));
 assert.ok(results.some(x=>x.code==='available-width'));
 assert.ok(results.some(x=>x.code==='window-language'&&x.source==='measurement'));
 assert.ok(results.some(x=>x.level==='unavailable'&&x.code==='worker-unavailable'));
});

function runtime({raw=JSON.stringify({...cfg,'headers.User-Agent':'wrong'}), initialOverrides={},windows=[]}={}) {
 const prefs=new Map([['cloakfox.s.cloak_cfg_7',raw],['cloakfox.container.7.math_seed','retained-secret']]);
 const overrides={...initialOverrides},writes=[];
 const sandbox=vm.createContext({Services:{prefs:{getStringPref:(key,fallback='')=>prefs.get(key)??fallback,
  setStringPref:(key,value)=>{prefs.set(key,value);writes.push(key);},savePrefFile:()=>writes.push('save')},wm:{getEnumerator:()=>windows}},
  ChromeUtils:{importESModule:url=>url.includes('PrivateBrowsingUtils')?{PrivateBrowsingUtils:{isWindowPrivate:win=>win.private}}:{
   readOverrides:()=>({...overrides}),setOverride:(_id,key,value)=>{overrides[key]=value;},clearOverride:(_id,key)=>{delete overrides[key];}}}});
 vm.runInContext(readFileSync(new URL('../../additions/browser/components/cloakfox/CloakfoxInspector.sys.mjs',import.meta.url),'utf8')
  .replaceAll('export function','function').replaceAll('export async function','async function')+'\nthis.api={repairConsistency,undoConsistencyRepair,measureContainer};',sandbox);
 return {api:sandbox.api,prefs,overrides,writes,raw};
}
test('production repair recomputes allowed changes and undo restores original override without rotating seed',()=>{
 const r=runtime({initialOverrides:{'headers.User-Agent':'prior-override'}});
 const record=r.api.repairConsistency(7,{code:'header-ua',repair:{'fingerprint:secret':'malicious'}},r.raw);
 assert.equal(r.overrides['headers.User-Agent'],cfg['navigator.userAgent']);
 assert.equal(r.prefs.get('cloakfox.container.7.math_seed'),'retained-secret');
 assert.equal(JSON.parse(record.after)['fingerprint:secret'],undefined);
 r.api.undoConsistencyRepair(record);
 assert.equal(r.prefs.get('cloakfox.s.cloak_cfg_7'),r.raw);
 assert.equal(r.overrides['headers.User-Agent'],'prior-override');
 assert.equal(r.prefs.get('cloakfox.container.7.math_seed'),'retained-secret');
 assert.equal(r.writes.filter(key=>key==='save').length,2);
});
test('production undo clears an override introduced by repair and stale repair cannot write',()=>{
 const r=runtime();
 assert.throws(()=>r.api.repairConsistency(7,{code:'header-ua'},'older config'),/Settings changed/);
 assert.deepEqual(r.writes,[]);
 const record=r.api.repairConsistency(7,{code:'header-ua'},r.raw);
 r.api.undoConsistencyRepair(record);
 assert.equal(Object.hasOwn(r.overrides,'headers.User-Agent'),false);
 assert.equal(r.prefs.get('cloakfox.s.cloak_cfg_7'),r.raw);
});
test('production undo refuses newer config and independently changed overrides',()=>{
 const a=runtime(),record=a.api.repairConsistency(7,{code:'header-ua'},a.raw);
 a.prefs.set('cloakfox.s.cloak_cfg_7','newer config');
 assert.throws(()=>a.api.undoConsistencyRepair(record),/newer changes/);
 assert.equal(a.prefs.get('cloakfox.s.cloak_cfg_7'),'newer config');
 const b=runtime(),second=b.api.repairConsistency(7,{code:'header-ua'},b.raw);
 b.overrides['headers.User-Agent']='user-edit';
 assert.throws(()=>b.api.undoConsistencyRepair(second),/override changed/);
 assert.equal(b.overrides['headers.User-Agent'],'user-edit');
 assert.equal(b.prefs.get('cloakfox.s.cloak_cfg_7'),second.after);
});
function fixtureTab(id,site,query) {
 const global={getActor:name=>{assert.equal(name,'CloakfoxMath');return {sendQuery:query};}};
 return {getAttribute:()=>String(id),linkedBrowser:{currentURI:{scheme:'https',prePath:site},browsingContext:{currentWindowGlobal:global}}};
}
test('production measurement excludes private windows and other containers even for default container',async()=>{
 const queries=[];
 const privateTab=fixtureTab(0,'https://private.example',()=>{queries.push('private');throw Error('must never inspect private');});
 const other=fixtureTab(7,'https://other.example',()=>{queries.push('other');throw Error('must never inspect another container');});
 const normal=fixtureTab(0,'https://normal.example',()=>{queries.push('normal');return {window:{language:'en-US'}};});
 const r=runtime({windows:[{private:true,gBrowser:{tabs:[privateTab]}},{private:false,gBrowser:{tabs:[normal,other]}}]});
 const result=await r.api.measureContainer(0);
 assert.equal(result.site,'https://normal.example');assert.deepEqual(queries,['normal']);
 const privateOnly=runtime({windows:[{private:true,gBrowser:{tabs:[privateTab]}}]});
 const unavailable=await privateOnly.api.measureContainer(0);
 assert.equal(unavailable.site,undefined);assert.ok(unavailable.windowError);assert.deepEqual(queries,['normal']);
});
test('production measurement refuses a navigation race rather than attributing old readings to new page',async()=>{
 const tab=fixtureTab(7,'https://old.example',()=>{tab.linkedBrowser.browsingContext.currentWindowGlobal={};return {window:{language:'en-US'}};});
 const r=runtime({windows:[{private:false,gBrowser:{tabs:[tab]}}]});
 await assert.rejects(r.api.measureContainer(7),/navigated during measurement/);
});

const cases = {
 'app-version': {'navigator.appVersion':'Macintosh Firefox/158.0'},
 'oscpu-os': {'navigator.oscpu':'Intel Mac OS X'},
 'gpu-os': {'webGl:renderer':'Apple M1'},
 'gl-renderer': {'webGl:renderer':'GPU A','webGl:parameters':{'7937':'GPU B'}},
 'screen-width': {'screen.width':0}, 'available-width':{'screen.availWidth':-1},
 'viewport-width': {'window.innerWidth':1000,'window.outerWidth':900},
 dpr:{'window.devicePixelRatio':0}, 'locale-language':{'locale:language':'de'},
 'language-header':{'headers.Accept-Language':'de-DE'}, 'language-tag':{'navigator.language':'not_a_tag'},
};
const desktop={...cfg,'navigator.userAgent':'Windows Firefox/158.0','headers.User-Agent':'Windows Firefox/158.0'};
for (const [code,delta] of Object.entries(cases)) test(`detects missing configuration case ${code}`,()=>{
 assert.ok(context.inspect({...desktop,...delta}).some(i=>i.code===code));
});
test('optional fields, unknown GPUs, reduced appVersion and canonical language aliases are allowed',()=>{
 const result=context.inspect({...desktop,'navigator.appVersion':'5.0','webGl:renderer':'Unknown GPU',
 'navigator.language':'iw-IL','locale:language':'he','locale:region':'IL','headers.Accept-Language':'he-IL, en;q=0.5'});
 assert.equal(result.filter(i=>i.source==='configuration').length,0);
});
test('confirmation cancellation has no writes; accepting retains the exact candidate',async()=>{
 const api=await import('../../additions/browser/components/cloakfox/CloakfoxInspector.sys.mjs');
 const prior={...desktop},candidate={...prior,'window.devicePixelRatio':0,'fingerprint:secret':'keep'};
 let calls=0,writes=0;
 const save=accept=>{if(api.confirmConsistencyChange(prior,candidate,()=>{calls++;return accept;})){writes++;return candidate;}};
 assert.equal(save(false),undefined);assert.equal(writes,0);
 assert.equal(save(true),candidate);assert.equal(writes,1);assert.equal(candidate['fingerprint:secret'],'keep');
 assert.equal(api.confirmConsistencyChange(candidate,{...candidate},()=>{throw Error('existing conflict must not prompt')}),true);
 assert.equal(calls,2);
});

test('missing optional identity fields do not create configuration findings',()=>{
 assert.equal(context.inspect({'navigator.userAgent':'Windows Firefox/158.0'}).filter(i=>i.source==='configuration').length,0);
});
