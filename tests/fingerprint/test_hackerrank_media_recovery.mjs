import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

function harness(enabled = true, initiallyInitialized = true) {
  let initialized = initiallyInitialized;
  let id = 41, writes = 0, renders = 0, captures = 0;
  const timers = new Map();
  let nextTimer = 1;
  const state = {
    callStatus: 'connected', localZoomUserId: id,
    setLocalZoomUserId(value) { this.localZoomUserId = value; writes++; },
    incrementVideoRenderEpoch() { renders++; },
  };
  function client() {
    const listeners = new Map();
    return {
      on(type, fn) { if (!listeners.has(type)) listeners.set(type,new Set()); listeners.get(type).add(fn); },
      off(type, fn) { listeners.get(type)?.delete(fn); },
      emit(type, value) { for (const fn of listeners.get(type) || []) fn(value); },
      getCurrentUserInfo() { return {userId:id}; },
      startVideo() { captures++; }, startShareScreen() { captures++; },
      get listenerCount() { return [...listeners.values()].reduce((n,s)=>n+s.size,0); },
    };
  }
  const av = {provider:{zmClient:client()}, getLocalParticipantId(){return id;}};
  const store = Object.assign(()=>{}, {getState:()=>state,subscribe(){throw Error('No store interception');}});
  // Deliberately different module IDs and export names from the live site.
  function req(key) { return key === '891' ? {renamedStore:store} : {renamedGetter:getAV}; }
  function getAV() { if (!initialized) throw Error('Call initAV(provider) before using getAV()'); return av; }
  req.m = {
    891: function storeFactory(){ return 'setLocalZoomUserId incrementVideoRenderEpoch'; },
    777: function serviceFactory(){ return 'Call initAV(provider) before using getAV()'; },
  };
  const page = {webpackChunk_N_E:[]};
  page.webpackChunk_N_E.push = entry => { entry[2](req); return 1; };
  const win = {
    wrappedJSObject:page,
    setInterval(fn){const n=nextTimer++;timers.set(n,{fn,repeat:true});return n;},
    clearInterval(n){timers.delete(n);},
    setTimeout(fn){const n=nextTimer++;timers.set(n,{fn,repeat:false});return n;},
    clearTimeout(n){timers.delete(n);},
  };
  const context = vm.createContext({
    JSWindowActorChild:class {},
    Services:{prefs:{getBoolPref:()=>enabled}},
    Cu:{cloneInto:structuredClone,waiveXrays:x=>x,exportFunction:fn=>fn},
  });
  const source = readFileSync(new URL('../../additions/browser/components/cloakfox/actors/CloakfoxHackerRankMediaChild.sys.mjs',import.meta.url),'utf8');
  vm.runInContext(source.replace('export class CloakfoxHackerRankMediaChild','class CloakfoxHackerRankMediaChild')+'\nglobalThis.Actor=CloakfoxHackerRankMediaChild;',context);
  const actor=new context.Actor();actor.contentWindow=win;actor.browsingContext={id:19};
  actor.handleEvent({type:'DOMDocElementInserted'});
  function tick(){for(const [n,t] of [...timers]){if(!timers.has(n))continue;if(!t.repeat)timers.delete(n);t.fn();}}
  tick();
  return {state,av,actor,tick,client,setInitialized(value){initialized=value;},setId(value){id=value;},get writes(){return writes;},get renders(){return renders;},get captures(){return captures;},get timers(){return timers.size;}};
}

test('reconnect refreshes stale local ID and rerenders without starting capture',()=>{
  const h=harness();assert.equal(h.writes,0);
  h.state.callStatus='reconnecting';h.setId(52);h.av.provider.zmClient.emit('connection-change',{state:'Reconnecting'});h.tick();
  assert.equal(h.state.localZoomUserId,41);
  h.state.callStatus='connected';h.av.provider.zmClient.emit('connection-change',{state:'Connected'});h.tick();
  assert.equal(h.state.localZoomUserId,52);assert.equal(h.renders,1);assert.equal(h.captures,0);
  h.tick();assert.equal(h.writes,1);
  h.state.callStatus='reconnecting';h.setId(63);h.tick();h.state.callStatus='connected';h.tick();
  assert.equal(h.state.localZoomUserId,63);assert.equal(h.renders,2);
});

test('joining, closed and invalid SDK IDs never replace application state',()=>{
  const h=harness();
  for(const status of ['connecting','idle','error','reconnecting']){h.state.callStatus=status;h.setId(70);h.tick();assert.equal(h.writes,0);}
  h.state.callStatus='connected';for(const value of [0,-1,NaN,undefined,'70']){h.setId(value);h.tick();assert.equal(h.writes,0);}
});

test('new SDK clients detach old listeners and actor teardown cancels work',()=>{
  const h=harness(),old=h.av.provider.zmClient;
  assert.ok(old.listenerCount>0);h.av.provider.zmClient=h.client();h.tick();assert.equal(old.listenerCount,0);
  assert.ok(h.av.provider.zmClient.listenerCount>0);h.actor.didDestroy();
  assert.equal(h.av.provider.zmClient.listenerCount,0);assert.equal(h.timers,0);
  h.setId(82);old.emit('connection-change',{state:'Connected'});h.tick();assert.equal(h.writes,0);
});

test('compatibility opt-out leaves the application alone',()=>{
  const h=harness(false);h.setId(70);h.tick();assert.equal(h.writes,0);assert.equal(h.timers,0);assert.equal(h.av.provider.zmClient.listenerCount,0);
});

test('late service initialization is retried without recreating the service',()=>{
  const h=harness(true,false);h.setId(52);h.tick();assert.equal(h.writes,0);
  h.setInitialized(true);h.tick();assert.equal(h.state.localZoomUserId,52);assert.equal(h.captures,0);
});

test('teardown tolerates a destroyed content window and still detaches SDK callbacks',()=>{
  const h=harness();h.actor.contentWindow=null;
  assert.doesNotThrow(()=>h.actor.didDestroy());assert.equal(h.av.provider.zmClient.listenerCount,0);
});
