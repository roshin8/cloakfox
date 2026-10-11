import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

// Run the shipped sync module, replacing only Gecko/network dependencies.
function load({lookup = false, fetchImpl} = {}) {
  const prefs = new Map([['cloakfox.enabled', true], ['cloakfox.webrtc.ip_lookup.enabled', lookup]]);
  const prefObservers = new Map(), observers = new Map(), shared = new Map();
  const calls = [];
  const Services = {
    prefs: {
      getBoolPref: (key, fallback) => prefs.get(key) ?? fallback,
      addObserver: (key, obs) => prefObservers.set(key, obs),
    },
    obs: {
      addObserver: (obs, topic) => observers.set(topic, obs),
      removeObserver: (_obs, topic) => observers.delete(topic),
    },
    ppmm: {sharedData: {set: (k,v) => shared.set(k,v), delete: k => shared.delete(k), flush() {}}},
  };
  const context = vm.createContext({Services, AbortController,
    ChromeUtils: {importESModule: () => ({setTimeout, clearTimeout, initCloakfoxNetworkPolicy() {}, initCloakfoxContainerWorkflows() {}})},
    fetch: async (...args) => { calls.push(args[0]); return fetchImpl ? fetchImpl(...args) : {ok: true, text: async () => args[0].includes('api64') ? '2001:db8::1' : '198.51.100.7'}; },
  });
  const code = readFileSync(new URL('../../additions/browser/components/cloakfox/CloakfoxWebRTCSync.sys.mjs', import.meta.url), 'utf8').replace('export function initCloakfoxWebRTCSync', 'function initCloakfoxWebRTCSync');
  vm.runInContext(code + '\ninitCloakfoxWebRTCSync();', context);
  return {calls, shared, observers, set(key,value) {prefs.set(key,value);prefObservers.get(key)?.observe(null,'nsPref:changed',key);}};
}
const settled = () => new Promise(resolve => setImmediate(resolve));

test('default protection never contacts IP-echo services, including network changes', async () => {
  const state = load(); await settled();
  state.observers.get('network:link-status-changed')?.observe(null,'network:link-status-changed');
  await settled(); assert.deepEqual(state.calls, []);
});

test('lookup requires its separate opt-in and master protection', async () => {
  const state = load();
  state.set('cloakfox.webrtc.ip_lookup.enabled', true); await settled();
  assert.equal(state.shared.get('cloakfox-public-ipv4'), '198.51.100.7');
  assert.equal(state.shared.get('cloakfox-public-ipv6'), '2001:db8::1');
  state.set('cloakfox.enabled', false); await settled();
  assert.equal(state.shared.size, 0);
  const count = state.calls.length;
  state.set('cloakfox.webrtc.ip_lookup.enabled', false);
  state.set('cloakfox.webrtc.ip_lookup.enabled', true); await settled();
  assert.equal(state.calls.length, count);
});

test('disabling lookup while requests are pending cannot republish stale IPs', async () => {
  const pending = [];
  const state = load({lookup: true, fetchImpl: url => new Promise(resolve => pending.push(() => resolve({ok:true,text:async () => url.includes('api64') ? '2001:db8::2' : '198.51.100.8'})))});
  assert.equal(pending.length,2);
  state.set('cloakfox.webrtc.ip_lookup.enabled', false);
  for (const finish of pending) finish(); await settled(); await settled();
  assert.equal(state.shared.size,0);
  assert.equal(state.observers.size,0);
});

test('opt-out aborts active requests and starts no fallback service after failures', async () => {
  const pending = [], signals = [];
  const state = load({lookup:true,fetchImpl:(_url, options)=> {
    signals.push(options.signal);
    return new Promise(resolve=>pending.push(()=>resolve({ok:false})));
  }});
  state.set('cloakfox.webrtc.ip_lookup.enabled', false);
  assert.ok(signals.every(signal=>signal.aborted), 'Outstanding lookup requests were not aborted');
  for(const finish of pending.splice(0)) finish();
  await settled(); await settled();
  assert.equal(state.calls.length,2,'Fallback endpoint contacted after opt-out');
});

test('superseded refresh cannot start fallback requests after a newer generation begins', async () => {
 const pending=[];
 const state=load({lookup:true,fetchImpl:()=>new Promise(resolve=>pending.push(resolve))});
 state.observers.get('network:link-status-changed').observe(null,'network:link-status-changed');
 assert.equal(state.calls.length,4);
 for(const resolve of pending.splice(0,2)) resolve({ok:false});
 await settled();await settled();
 assert.equal(state.calls.length,4);
 state.set('cloakfox.webrtc.ip_lookup.enabled',false);
 for(const resolve of pending.splice(0)) resolve({ok:false});
 await settled();
});

test('RTC actor uses privileged setters without reading the page global', () => {
  const calls = [];
  const contentWindow = {
    setWebRTCIPv4(value) { calls.push(['v4', value]); },
    setWebRTCIPv6(value) { calls.push(['v6', value]); },
    get wrappedJSObject() { throw Error('Page-global access bypasses ChromeOnly setters'); },
  };
  const shared = new Map([['cloakfox-public-ipv4', '198.51.100.9'], ['cloakfox-public-ipv6', '2001:db8::9']]);
  const context = vm.createContext({JSWindowActorChild: class {}, Services: {
    prefs: {getBoolPref: () => true}, cpmm: {sharedData: shared},
  }});
  const source = readFileSync(new URL('../../additions/browser/components/cloakfox/actors/CloakfoxWebRTCChild.sys.mjs', import.meta.url), 'utf8');
  vm.runInContext(source.replace('export class CloakfoxWebRTCChild', 'this.Actor = class CloakfoxWebRTCChild'), context);
  const actor = new context.Actor(); actor.contentWindow = contentWindow;
  actor.handleEvent({type: 'DOMDocElementInserted'});
  assert.deepEqual(calls, [['v4', '198.51.100.9'], ['v6', '2001:db8::9']]);
});
