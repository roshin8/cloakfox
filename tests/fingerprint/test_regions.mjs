import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
function load() {
  const prefs = new Map(), refreshed=[];
  const context = vm.createContext({Intl, Services:{prefs:{getStringPref:(k,d)=>prefs.get(k)??d,setStringPref:(k,v)=>prefs.set(k,v),clearUserPref:k=>prefs.delete(k),savePrefFile:()=>{}}},ChromeUtils:{importESModule:()=>({refreshContainerConfig:ucid=>refreshed.push(ucid)})}});
  const source = readFileSync(new URL('../../additions/browser/components/cloakfox/CloakfoxRegions.sys.mjs',import.meta.url),'utf8').replaceAll('export function','function');
  vm.runInContext(source+'\nthis.api={validateRegion,getRegion,setRegion,applyRegion}',context);
  return {api:context.api,prefs,refreshed};
}
const berlin={locale:'de-DE',languages:['de-DE','de','en-US'],timezone:'Europe/Berlin',geolocation:{latitude:52.52,longitude:13.4,accuracy:10000}};
test('manual region is canonical, coherent, isolated and preserves unrelated identity',()=>{
 const {api,prefs,refreshed}=load();prefs.set('cloakfox.container.1.math_seed','existing-seed');api.setRegion(1,berlin);
 const cfg=api.applyRegion(1,{'canvas:seed':42,'headers.Accept-Language':'en-US','geolocation:latitude':12});
 assert.equal(cfg['headers.Accept-Language'],'de-DE,de;q=0.9,en-US;q=0.8');
 assert.equal(cfg['navigator.language'],'de-DE');assert.deepEqual(Array.from(cfg['navigator.languages']),berlin.languages);
 assert.equal(cfg['locale:default'],'de-DE');assert.equal(cfg['geolocation:latitude'],52.52);assert.equal(cfg['canvas:seed'],42);
 assert.equal(api.getRegion(2),null);assert.equal(prefs.get('cloakfox.container.1.timezone'),'Europe/Berlin');assert.deepEqual(refreshed,[1]);
});
test('optional location is off for generated and manual defaults; independent bilingual preference persists',()=>{
 const {api}=load();const cfg={'geolocation:latitude':40,'geolocation:longitude':-74,'geolocation:accuracy':100,'canvas:seed':12};
 assert.equal(api.applyRegion(2,cfg)['geolocation:latitude'],undefined);
 api.setRegion(2,{...berlin,languages:['en-US','de'],geolocation:null});
 const out=api.applyRegion(2,cfg);assert.equal(out['locale:default'],'de-DE');assert.equal(out['navigator.language'],'en-US');assert.equal(out['geolocation:latitude'],undefined);assert.equal(cfg['geolocation:latitude'],40);
});
test('validation is atomic and rejects malformed, precise, future and dangerous input',()=>{
 const {api,prefs}=load();api.setRegion(1,berlin);const before=JSON.stringify([...prefs]);
 for(const update of [{unexpected:true},{locale:'x'.repeat(101)},{geolocation:{latitude:0,longitude:0,accuracy:1000,secret:'x'}},{locale:'<bad>'},{timezone:'Wrong/Zone'},{languages:[]},{languages:['']},{version:2},{geolocation:{latitude:91,longitude:0,accuracy:1000}},{geolocation:{latitude:0,longitude:0,accuracy:10}},{geolocation:{latitude:NaN,longitude:0,accuracy:1000}}]) assert.throws(()=>api.setRegion(1,{...berlin,...update}));
 assert.equal(JSON.stringify([...prefs]),before);assert.throws(()=>api.getRegion(-1));
});
test('reset and malformed storage do not reuse another container',()=>{
 const {api,prefs}=load();api.setRegion(1,berlin);api.setRegion(2,{...berlin,locale:'ja-JP',languages:['ja-JP'],timezone:'Asia/Tokyo'});
 api.setRegion(1,null);assert.equal(api.getRegion(1),null);assert.equal(api.getRegion(2).locale,'ja-JP');assert.equal(prefs.has('cloakfox.container.1.timezone'),false);
 prefs.set('cloakfox.container.1.region','{"version":99}');assert.equal(api.getRegion(1),null);
});
test('region native implementation gates geo on site permission and avoids ambient/cache mutation',()=>{
 const base=new URL('../../firefox-src/',import.meta.url);
 const geo=readFileSync(new URL('dom/geolocation/Geolocation.cpp',base),'utf8');
 const prompt=geo.slice(geo.indexOf('bool Geolocation::RegisterRequestWithPrompt'),geo.indexOf('Geolocation::GetSystemPermissionBehavior'));
 assert.ok(!prompt.includes('geolocation:latitude'));assert.match(geo,/principal->OriginAttributesRef\(\).mUserContextId/);
 const coords=readFileSync(new URL('dom/geolocation/GeolocationPosition.cpp',base),'utf8');assert.ok(!coords.includes('MaskConfig::'));
 const provider=readFileSync(new URL('dom/system/NetworkGeolocationProvider.sys.mjs',base),'utf8');assert.ok(!provider.includes('camouGetDouble'));
 const locale=readFileSync(new URL('intl/components/src/Locale.h',base),'utf8');assert.match(locale,/Language\(\) const \{ return mLanguage; \}/);
});

test('unconfigured personas receive explicit realm defaults without touching seeds',()=>{
 const {api,refreshed}=load();api.setRegion(9,berlin);assert.deepEqual(refreshed,[]);
 const out=api.applyRegion(0,{'navigator.language':'en-US','headers.Accept-Language':'en-US,en;q=0.9','math:trig_seed':99});
 assert.equal(out['locale:default'],'en-US');assert.equal(out['timezone'],'UTC');assert.deepEqual(Array.from(out['navigator.languages']),['en-US','en']);assert.equal(out['math:trig_seed'],99);
});

test('reapplying generated regions is byte-stable for legacy and partial configs',()=>{
 const {api}=load();
 for (const cfg of [
   {'math:trig_seed':42},
   {'navigator.languages':['fr-FR','en-US']},
   {'locale:all':'de-DE,de'},
   {'headers.Accept-Language':'ja-JP,en-US;q=0.9'},
   {'navigator.language':'en-US','headers.Accept-Language':'fr-FR,fr;q=0.9'},
 ]) {
   const once=api.applyRegion(0,cfg),twice=api.applyRegion(0,once);
   assert.equal(JSON.stringify(twice),JSON.stringify(once));
 }
 assert.deepEqual(Array.from(api.applyRegion(0,{'math:trig_seed':42})['navigator.languages']),['en-US','en']);
 assert.deepEqual(Array.from(api.applyRegion(0,{'navigator.language':'en-US','navigator.languages':['en-US','de']})['navigator.languages']),['en-US','de']);
});

test('HTTP language override is scoped to channel origin attributes, not a handler cache',()=>{
 const base=new URL('../../firefox-src/netwerk/protocol/http/',import.meta.url);
 const channel=readFileSync(new URL('HttpBaseChannel.cpp',base),'utf8');
 assert.match(channel,/CloakConfigOverlay_Get\(\s*mLoadInfo->GetOriginAttributes\(\).mUserContextId\)/);
 assert.match(channel,/languageOverride.Assign\(\s*cfg\["headers.Accept-Language"\]/);
 const handler=readFileSync(new URL('nsHttpHandler.cpp',base),'utf8');
 assert.ok(!handler.includes('MaskConfig::GetString("headers.Accept-Language")'));
});

test('synthetic location retains site prompt and avoids device-permission override before Allow',()=>{
 const geo=readFileSync(new URL('../../firefox-src/dom/geolocation/Geolocation.cpp',import.meta.url),'utf8');
 const request=geo.slice(geo.indexOf('void Geolocation::RequestIfPermitted'));
 const synthetic=request.slice(request.indexOf('if (request->PrepareSyntheticPosition())'),request.indexOf('auto getPermission'));
 assert.match(synthetic,/RegisterRequestWithPrompt\(request\)/);
 assert.ok(!synthetic.includes('DelayedTaskType::Allow'));
 assert.ok(request.indexOf('PrepareSyntheticPosition()') < request.indexOf('SendGetSystemGeolocationPermissionBehavior'));
 const allow=geo.slice(geo.indexOf('nsGeolocationRequest::Allow('),geo.indexOf('void nsGeolocationRequest::SetTimeoutTimer'));
 assert.match(allow,/Update\(mSyntheticPosition\)/);
});
