import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import vm from 'node:vm';

const file = new URL('../../additions/browser/components/cloakfox/CloakfoxNetworkProfiles.sys.mjs', import.meta.url);
function load() {
  assert.ok(existsSync(file), 'The shared network-profile registry must exist');
  const prefs = new Map(), observers = [];
  const get = (key, fallback) => prefs.has(key) ? prefs.get(key) : fallback;
  const context = vm.createContext({
    Services: {prefs: {
      getBoolPref:get, getIntPref:get, getStringPref:get,
      setIntPref:(k,v)=>prefs.set(k,v), setCharPref:(k,v)=>prefs.set(k,v),
      addObserver:(key,value)=>observers.push([key,value]),
      getBranch:prefix=>({getChildList:()=>[...prefs.keys()].filter(key=>key.startsWith(prefix)).map(key=>key.slice(prefix.length))}),
    }},
  });
  vm.runInContext(readFileSync(file,'utf8').replace(/^import\s+[\s\S]*?\s+from\s+"[^"]+";\n/gm,'').replace(/^export /gm,''),context);
  return {prefs, context, observers, select: options => JSON.parse(JSON.stringify(context.selectNetworkProfile(options)))};
}
const chrome = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36';
const firefox = 'Mozilla/5.0 Firefox/157.0';

test('native transport remains the default even for a Chrome identity', () => {
  const h=load(); const selected=h.select({ua:chrome});
  assert.equal(selected.profileId,0); assert.equal(selected.family,'firefox');
  assert.equal(selected.backend,'gecko'); assert.equal(selected.experimental,false);
});
test('opt-in Chrome intent selects one combined native adapter profile', () => {
  const h=load();const result=h.select({ua:chrome,followIdentity:true,enabled:true});
  assert.equal(result.profileId,1);assert.equal(result.family,'chrome');
  assert.deepEqual(result.protocols,{h2:'chrome',tls:1,quic:1,h3:1});
  assert.equal(result.experimental,true);
  assert.ok(result.gaps.includes('ALPS')); // Never report complete parity while unsupported.
  assert.equal(result.referenceMajor,155);
});
test('master off wins over the saved network choice', () => {
  const h=load();assert.equal(h.select({ua:chrome,followIdentity:true,enabled:false}).profileId,0);
});
test('Gecko-native and unsupported identities have explicit status', () => {
  const h=load();assert.equal(h.select({ua:firefox,followIdentity:true}).family,'firefox');
  for(const ua of ['nonsense','Mozilla/5.0 Version/17.0 Safari/605.1.15','Mozilla/5.0 CriOS/155.0 Mobile Safari/537.36']) {
    const result=h.select({ua,followIdentity:true});assert.equal(result.profileId,0);assert.equal(result.unsupported,true);
  }
});
test('a future engine cannot accidentally inherit the Gecko adapter', () => {
  const h=load();const result=h.select({ua:chrome,followIdentity:true,engine:'chromium'});
  assert.equal(result.available,false);assert.equal(result.profileId,0);assert.equal(result.backend,null);
});
test('network intent and atomic native profile remain scoped to exact container zero', () => {
  const h=load(); h.prefs.set('cloakfox.enabled',true);
  h.prefs.set('cloakfox.container.0.network_follow_identity',true);
  h.prefs.set('cloakfox.s.cloak_cfg_0',JSON.stringify({'navigator.userAgent':chrome}));
  h.prefs.set('cloakfox.s.cloak_cfg_7',JSON.stringify({'navigator.userAgent':chrome}));
  h.context.writeNetworkProfile(0); h.context.writeNetworkProfile(7);
  assert.equal(h.prefs.get('cloakfox.container.0.network_profile'),1);
  assert.equal(h.prefs.get('cloakfox.container.7.network_profile'),0);
  h.prefs.set('cloakfox.container.0.network_follow_identity',false);h.context.writeNetworkProfile(0);
  assert.equal(h.prefs.get('cloakfox.container.0.network_profile'),0);
});
test('UA changes and malformed cfg never retain an old Chrome network profile', () => {
  const h=load();h.prefs.set('cloakfox.enabled',true);h.prefs.set('cloakfox.container.7.network_follow_identity',true);
  h.context.writeNetworkProfile(7,chrome);assert.equal(h.prefs.get('cloakfox.container.7.network_profile'),1);
  h.prefs.set('cloakfox.s.cloak_cfg_7','{');h.context.writeNetworkProfile(7);
  assert.equal(h.prefs.get('cloakfox.container.7.network_profile'),0);
});
test('adapter names inherited from Object.prototype remain unavailable', () => {
  const h=load();
  for(const engine of ['constructor','__proto__','toString']) {
    const result=h.select({ua:chrome,followIdentity:true,engine});
    assert.equal(result.available,false);assert.equal(result.backend,null);
  }
});

test('registry startup reconciles persisted intent and discards stale adapter IDs', () => {
  const h=load();h.prefs.set('cloakfox.enabled',true);
  h.prefs.set('cloakfox.s.cloak_cfg_7',JSON.stringify({'navigator.userAgent':chrome}));
  h.prefs.set('cloakfox.container.7.network_follow_identity',true);
  h.prefs.set('cloakfox.s.cloak_cfg_0',JSON.stringify({'navigator.userAgent':chrome}));
  h.prefs.set('cloakfox.container.0.network_profile',1);
  h.context.initNetworkProfiles();
  assert.equal(h.prefs.get('cloakfox.container.7.network_profile'),1);
  assert.equal(h.prefs.get('cloakfox.container.0.network_profile'),0);
  h.context.initNetworkProfiles();assert.equal(h.observers.length,3);
  h.prefs.set('cloakfox.enabled',false);
  h.observers.find(([name])=>name==='cloakfox.enabled')[1].observe(null,'nsPref:changed','cloakfox.enabled');
  assert.equal(h.prefs.get('cloakfox.container.7.network_profile'),0);
});

test('config observer uses a complete branch compatible with native matching', () => {
  const h=load();h.context.initNetworkProfiles();
  assert.ok(h.observers.some(([branch])=>branch==='cloakfox.s.'));
  h.prefs.set('cloakfox.enabled',true);
  h.prefs.set('cloakfox.container.7.network_follow_identity',true);
  h.prefs.set('cloakfox.s.cloak_cfg_7',JSON.stringify({'navigator.userAgent':chrome}));
  const cfgObserver=h.observers.find(([branch])=>branch==='cloakfox.s.')[1];
  cfgObserver.observe(null,'nsPref:changed','cloakfox.s.cloak_cfg_7');
  assert.equal(h.prefs.get('cloakfox.container.7.network_profile'),1);
  h.prefs.set('cloakfox.s.cloak_cfg_7',JSON.stringify({'navigator.userAgent':firefox}));
  cfgObserver.observe(null,'nsPref:changed','cloakfox.s.cloak_cfg_7');
  assert.equal(h.prefs.get('cloakfox.container.7.network_profile'),0);
});


test('unmeasured Chrome versions retain native networking with explicit status', () => {
  const h=load();
  for(const major of [120,154,156,999]) {
    const result=h.select({ua:chrome.replace('Chrome/155.',`Chrome/${major}.`),followIdentity:true});
    assert.equal(result.profileId,0);assert.equal(result.unsupported,true);
  }
  assert.equal(h.select({ua:chrome.replace('Chrome/155.','Chromium/155.'),followIdentity:true}).profileId,1);
});
