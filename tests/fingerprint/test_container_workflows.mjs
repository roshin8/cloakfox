import assert from 'node:assert/strict';
import { webcrypto } from 'node:crypto';
import test from 'node:test';
import { normalizeRuleHost, encryptIdentityBackup, decryptIdentityBackup, validateIdentityBackup,
  restoreIdentityBackup, cleanupTemporaryContainer, backupAppearanceWarnings } from '../../additions/browser/components/cloakfox/CloakfoxContainerWorkflows.sys.mjs';

const schemas = { keyTypes: { 'navigator.platform': 'string', 'screen.width': 'int' },
  normalizeHost: host => normalizeRuleHost(host, host => { if (!host.includes('.') || host === 'co.uk') throw Error(); return host; }),
  colors: ['blue'], icons: ['fingerprint'], normalizeProxy: value => value };
const fixture = () => ({ format: 'cloakfox-identity-settings', version: 1,
  containers: [{ sourceId: 0, name: 'Default', color: 'blue', icon: 'fingerprint',
    seeds: { math_seed: btoa('a'.repeat(32)), keyboard_seed: btoa('b'.repeat(32)), timing_seed: btoa('c'.repeat(32)) },
    settings: { timezone: 'UTC', persona_index: -1 }, overrides: { 'screen.width': 1200 },
    network: { mode: 0, proxyURL: '', webrtcMode: 0 } }],
  rules: [{ host: 'example.com', sourceId: 0 }] });

test('canonical exact hosts reject URLs, wildcards, suffixes and malformed hosts', () => {
  const normalize = schemas.normalizeHost;
  assert.equal(normalize('WWW.Example.COM.'), 'www.example.com');
  assert.equal(normalize('bücher.de'), 'xn--bcher-kva.de');
  for (const value of ['*.example.com', 'https://example.com', 'example.com/path', 'a@b.com', 'co.uk', 'localhost']) {
    assert.throws(() => normalize(value));
  }
});

test('encrypted backups roundtrip, randomize and reject tampering/wrong passwords', async () => {
  const payload = fixture();
  const first = await encryptIdentityBackup(payload, 'a sufficiently long password', webcrypto);
  const second = await encryptIdentityBackup(payload, 'a sufficiently long password', webcrypto);
  assert.notEqual(first.ciphertext, second.ciphertext);
  assert.equal(JSON.stringify(first).includes(payload.containers[0].seeds.math_seed), false);
  assert.deepEqual(await decryptIdentityBackup(first, 'a sufficiently long password', webcrypto), payload);
  await assert.rejects(decryptIdentityBackup(first, 'a different long password', webcrypto));
  const bytes = Uint8Array.from(atob(first.ciphertext), c => c.charCodeAt(0));
  bytes[0] ^= 1;
  await assert.rejects(decryptIdentityBackup({ ...first, ciphertext: btoa(String.fromCharCode(...bytes)) }, 'a sufficiently long password', webcrypto));
  await assert.rejects(decryptIdentityBackup({ ...first, iterations: 999999999 }, 'a sufficiently long password', webcrypto));
});

test('untrusted backup rejects duplicate IDs, unknown keys, malformed seeds and missing rule targets', () => {
  assert.deepEqual(validateIdentityBackup(fixture(), schemas), fixture());
  for (const mutate of [
    data => data.containers.push(structuredClone(data.containers[0])),
    data => { data.containers[0].settings['general.config.filename'] = 'evil.cfg'; },
    data => { data.containers[0].seeds.math_seed = 'short'; },
    data => { data.rules[0].sourceId = 404; },
    data => { data.containers[0].overrides['__proto__'] = { polluted: true }; },
    data => { data.containers[0].overrides['screen.width'] = '1200'; },
  ]) {
    const data = fixture(); mutate(data);
    assert.throws(() => validateIdentityBackup(data, schemas));
  }
});

test('restore creates fresh IDs and remaps rules without overwriting old identities', async () => {
  const events = [];
  const deps = { schemas, getRule: () => 0,
    create: record => { events.push(['create', record.sourceId]); return 99; },
    write: (id, record) => events.push(['write', id, record.seeds.math_seed]),
    setRule: (host, id) => events.push(['rule', host, id]),
    removeRule: () => {}, remove: () => events.push(['remove']), save: () => {},
  };
  assert.deepEqual(await restoreIdentityBackup(fixture(), deps), [{ sourceId: 0, userContextId: 99 }]);
  assert.deepEqual(events.at(-1), ['rule', 'example.com', 99]);
  assert.equal(events.some(event => event[0] === 'write' && event[1] === 0), false);
  events.length = 0;
  deps.getRule = () => 42;
  await assert.rejects(restoreIdentityBackup(fixture(), deps), /already/);
  assert.deepEqual(events, []);
});

test('failed import removes only newly created identities', async () => {
  const removed = [];
  await assert.rejects(restoreIdentityBackup(fixture(), { schemas, getRule: () => 0,
    create: () => 100, write: () => { throw Error('disk failure'); },
    setRule: () => {}, removeRule: () => {}, remove: id => removed.push(id), save: () => {},
  }), /disk failure/);
  assert.deepEqual(removed, [100]);
});

test('temporary cleanup waits for successful clear and retains recovery marker on failure', async () => {
  const events = [];
  const deps = { hasTabs: () => false, forget: async () => { throw Error('quota failed'); },
    remove: id => events.push(['remove', id]), unmark: id => events.push(['unmark', id]) };
  await assert.rejects(cleanupTemporaryContainer(8, deps), /quota failed/);
  assert.deepEqual(events, []);
  deps.forget = async () => { events.push(['clear']); };
  await cleanupTemporaryContainer(8, deps);
  assert.deepEqual(events, [['clear'], ['remove', 8], ['unmark', 8]]);
  events.length = 0; deps.hasTabs = () => true;
  assert.equal(await cleanupTemporaryContainer(8, deps), false);
  assert.deepEqual(events, []);
});

test('a rule added during import is retained and only new containers are rolled back', async () => {
  let existing = false;
  const writes = [], removed = [];
  await assert.rejects(restoreIdentityBackup(fixture(), { schemas, getRule: () => existing ? 42 : 0,
    create: () => 100, write: () => { existing = true; },
    setRule: (...args) => writes.push(args), removeRule: () => { throw Error('must not remove existing rule'); },
    remove: id => removed.push(id), save: () => {},
  }), /added while importing/);
  assert.deepEqual(writes, []);
  assert.deepEqual(removed, [100]);
  assert.equal(existing, true);
});

test('startup recovery clears temporary tabs rather than treating them as permanent', async () => {
  const events = [];
  assert.equal(await cleanupTemporaryContainer(8, { hasTabs: () => true,
    forget: async () => events.push('forget'), remove: async () => events.push('remove'),
    unmark: () => events.push('unmark') }, { recovery: true }), true);
  assert.deepEqual(events, ['forget', 'remove', 'unmark']);
});

test('failed import retains a rule reassigned by the user while save was pending', async () => {
  const rules = new Map();
  const removedRules = [], removedContainers = [];
  await assert.rejects(restoreIdentityBackup(fixture(), {
    schemas, getRule: host => rules.get(host) || 0, create: () => 100, write: () => {},
    setRule: (host, id) => rules.set(host, id),
    removeRule: host => { removedRules.push(host); rules.delete(host); },
    remove: id => removedContainers.push(id),
    save: async () => { rules.set('example.com', 77); throw Error('save failed'); },
  }), /save failed/);
  assert.equal(rules.get('example.com'), 77);
  assert.deepEqual(removedRules, []);
  assert.deepEqual(removedContainers, [100]);
});

test('whole-window close schedules cleanup without TabClose and keeps temporary tabs in another window', async () => {
  const fresh = await import('../../additions/browser/components/cloakfox/CloakfoxContainerWorkflows.sys.mjs?whole-window-close');
  const observers = new Map();
  let tracked = [];
  const pending = [], deleted = [];
  const previousServices = globalThis.Services;
  globalThis.Services = { wm: { getEnumerator: () => [] },
    obs: { addObserver: (callback, topic) => observers.set(topic, callback) },
    prefs: { getStringPref: () => '[]' } };
  try { fresh.initCloakfoxContainerWorkflows({
    windows: () => [], observe: (callback, topic) => observers.set(topic, callback),
    tracked: () => tracked,
    schedule: id => pending.push(cleanupTemporaryContainer(id, {
      hasTabs: value => value === 9, // a surviving second window still has UCID 9
      forget: async value => deleted.push(value), remove: () => {}, unmark: () => {},
    })),
    report: error => { throw error; },
  }); } finally {
    if (previousServices === undefined) delete globalThis.Services;
    else globalThis.Services = previousServices;
  }
  tracked = [8, 9];
  assert.equal(typeof observers.get('domwindowclosed'), 'function');
  observers.get('domwindowclosed')({}); // no TabClose event is delivered
  await Promise.all(pending);
  assert.deepEqual(deleted, [8]);
});

test('rollback awaits persistence before reporting that newly created identities were removed', async () => {
  let saves = 0;
  const prefs = new Map();
  let persisted = new Map();
  await assert.rejects(restoreIdentityBackup(fixture(), {
    schemas, getRule: () => 0, create: () => 100,
    write: id => prefs.set(id, 'new settings'), setRule: () => {}, removeRule: () => {},
    remove: id => prefs.delete(id),
    save: async () => { persisted = new Map(prefs); if (++saves === 1) throw Error('first save failed'); },
  }), /newly created containers were removed/);
  assert.equal(saves, 2);
  assert.equal(persisted.size, 0);
});

test('rollback save failure reports possible remaining state instead of completed removal', async () => {
  await assert.rejects(restoreIdentityBackup(fixture(), {
    schemas, getRule: () => 0, create: () => 100, write: () => {},
    setRule: () => {}, removeRule: () => {}, remove: () => {},
    save: async () => { throw Error('disk unavailable'); },
  }), /may remain or return after restart/);
});

test('adding a site rule while native routing is disabled rejects without changing associations', async () => {
  const { setSiteRule } = await import('../../additions/browser/components/cloakfox/CloakfoxContainerWorkflows.sys.mjs');
  const writes = [];
  const previousServices = globalThis.Services, previousChrome = globalThis.ChromeUtils;
  globalThis.Services = { prefs: { getBoolPref: () => false }, eTLD: { getBaseDomainFromHost: host => host } };
  globalThis.ChromeUtils = { importESModule: () => ({ ContextualIdentityService: {
    getPublicIdentityFromId: () => ({ userContextId: 7 }), setSiteAssociation: (...args) => writes.push(args),
  } }) };
  try {
    assert.throws(() => setSiteRule('example.com', 7), /routing is disabled/);
    assert.deepEqual(writes, []);
  } finally {
    if (previousServices === undefined) delete globalThis.Services; else globalThis.Services = previousServices;
    if (previousChrome === undefined) delete globalThis.ChromeUtils; else globalThis.ChromeUtils = previousChrome;
  }
});

// Version 2 uses the actual feature validators, not duplicate backup schemas.
const { validateRegion } = await import('../../additions/browser/components/cloakfox/CloakfoxRegions.sys.mjs');
const { validatePrivacyPolicy } = await import('../../additions/browser/components/cloakfox/CloakfoxPrivacyPolicy.sys.mjs');
const { validateStartPages } = await import('../../additions/browser/components/cloakfox/CloakfoxTemplates.sys.mjs');
const { normalizeProxyURL } = await import('../../additions/browser/components/cloakfox/CloakfoxNetworkPolicy.sys.mjs');
const { restoreBackupNetwork } = await import('../../additions/browser/components/cloakfox/CloakfoxContainerWorkflows.sys.mjs');
const schemasV2 = {...schemas, normalizeProxy: normalizeProxyURL, region: validateRegion,
  policy: validatePrivacyPolicy, startPages: validateStartPages};
function fixtureV2() {
  const data = fixture(); data.version = 2; data.sourceOS = "macos";
  const record = data.containers[0]; record.settings.persona_os_mode = 'host';
  record.region = {version:1,locale:'de-DE',languages:['de-DE','en-US'],timezone:'Europe/Berlin',geolocation:null};
  record.policy = {version:1,preset:'strict',exceptions:[]}; record.startPages = ['https://example.com/start'];
  record.network = {mode:1,proxyURL:'',webrtcMode:2,proxyRef:'11111111-1111-1111-1111-111111111111'};
  return data;
}
test('v2 validates region, policy, opening pages, OS mode and reference-only named routes', () => {
  assert.deepEqual(validateIdentityBackup(fixtureV2(), schemasV2), fixtureV2());
  for (const mutate of [
    r => {r.region.geolocation={latitude:400,longitude:0,accuracy:1000};},
    r => {r.policy.preset='unknown';}, r => {r.startPages=['javascript:alert(1)'];},
    r => {r.startPages=['https://username:secret@example.com'];},
    r => {r.settings.persona_os_mode='unsupported';}, r => {delete r.settings.persona_os_mode;},
    r => {r.network.proxyURL='http://localhost:8080';}, r => {r.network.mode=0;},
    r => {r.network.proxyRef='';}, r => {r.network.password='secret';},
    r => {r.region.cookies=[];}, r => {delete r.startPages;},
  ]) {const value=fixtureV2();mutate(value.containers[0]);assert.throws(()=>validateIdentityBackup(value,schemasV2));}
});
test('v2 encrypted roundtrip binds the version and preserves all identity settings', async () => {
  const payload=fixtureV2();const encrypted=await encryptIdentityBackup(payload,'a sufficiently long password',webcrypto);
  assert.equal(encrypted.version,2);
  assert.deepEqual(await decryptIdentityBackup(encrypted,'a sufficiently long password',webcrypto),payload);
  await assert.rejects(decryptIdentityBackup({...encrypted,version:1},'a sufficiently long password',webcrypto));
});
test('missing named proxy remains blocked with its reference and cannot become a manual route', () => {
  const events=[];
  const deps={setNetwork:(id,value)=>events.push(['network',id,value]),hasProxy:()=>false,
    retainReference:(id,ref)=>events.push(['reference',id,ref]),bind:()=>assert.fail('missing proxy must not bind')};
  const network=fixtureV2().containers[0].network;
  assert.deepEqual(restoreBackupNetwork(99,network,deps),{bindingRequired:network.proxyRef});
  assert.deepEqual(events[0],['network',99,{mode:2,proxyURL:'',webrtcMode:2}]);
  assert.deepEqual(events[1],['reference',99,network.proxyRef]);
  assert.equal(events.length,2);
});
test('present named proxy uses local binding, while previously blocked refs stay blocked', () => {
  const events=[];const network=fixtureV2().containers[0].network;
  const deps={setNetwork:(id,value)=>events.push(['network',value.mode]),hasProxy:()=>true,
    retainReference:()=>{},bind:(id,ref)=>events.push(['bind',ref])};
  assert.deepEqual(restoreBackupNetwork(99,network,deps),{});
  assert.deepEqual(events,[['network',2],['bind',network.proxyRef]]);
  events.length=0;
  assert.deepEqual(restoreBackupNetwork(99,{...network,mode:2},deps),{bindingRequired:network.proxyRef});
  assert.deepEqual(events,[['network',2]]);
});
test('v2 restore exposes missing binding status and forwards every saved field unchanged', async () => {
  const payload=fixtureV2();const events=[];
  const imported=await restoreIdentityBackup(payload,{schemas:schemasV2,destinationOS:()=>"Darwin",getRule:()=>0,
    create:()=>99,write:(id,record)=>{assert.deepEqual(record,payload.containers[0]);events.push('write');return {bindingRequired:record.network.proxyRef};},
    setRule:()=>events.push('rule'),removeRule:()=>{},remove:()=>{},save:()=>events.push('save')});
  assert.deepEqual(events,['write','rule','save']);
  assert.deepEqual(imported,[{sourceId:0,userContextId:99,bindingRequired:payload.containers[0].network.proxyRef}]);
});

test('backup source OS metadata is optional for v2, strict when present, forbidden for v1',()=>{
 const old=fixtureV2();delete old.sourceOS;
 assert.equal(validateIdentityBackup(old,schemasV2),old);
 for(const value of [null,'Darwin','android',3,{}]) {
  const bad=fixtureV2();bad.sourceOS=value;assert.throws(()=>validateIdentityBackup(bad,schemasV2));
 }
 assert.throws(()=>validateIdentityBackup({...fixture(),sourceOS:'macos'},schemas));
});
test('appearance warning distinguishes changed, unknown and matching source OS without changing seeds or mode',()=>{
 const payload=fixtureV2(),before=JSON.stringify(payload);
 const [changed]=backupAppearanceWarnings(payload,'WINNT');
 assert.equal(changed.reason,'different-os');assert.equal(changed.sourceOS,'macos');assert.equal(changed.destinationOS,'windows');
 assert.match(changed.message,/saved seeds are preserved/);
 assert.deepEqual(backupAppearanceWarnings(payload,'Darwin'),[]);
 assert.equal(JSON.stringify(payload),before);
 delete payload.sourceOS;
 const [unknown]=backupAppearanceWarnings(payload,'Linux');
 assert.equal(unknown.reason,'unknown-source-os');assert.equal(unknown.sourceOS,null);assert.match(unknown.message,/original appearance cannot be guaranteed/);
 payload.containers[0].settings.persona_os_mode='legacy';
 assert.deepEqual(backupAppearanceWarnings(payload,'Linux'),[]);
 assert.deepEqual(backupAppearanceWarnings(fixture(),'Linux'),[]);
});
test('restore passes and returns adaptation metadata while preserving original record and seeds',async()=>{
 for(const sourceOS of ['macos',undefined]) {
  const payload=fixtureV2();if(sourceOS===undefined)delete payload.sourceOS;
  const original=JSON.stringify(payload),writes=[];
  const imported=await restoreIdentityBackup(payload,{schemas:schemasV2,destinationOS:()=> 'WINNT',getRule:()=>0,
   create:()=>99,write:(id,record,warning)=>{writes.push({id,record,warning});},setRule(){},removeRule(){},remove(){},save(){}});
  assert.equal(JSON.stringify(payload),original);assert.equal(writes[0].record,payload.containers[0]);
  assert.equal(writes[0].warning,imported[0].appearanceWarning);
  assert.equal(imported[0].appearanceWarning.reason,sourceOS?'different-os':'unknown-source-os');
 }
});

test('native identity writer persists restoration disclosure alongside unchanged imported seeds',async()=>{
 const {readFile}=await import('node:fs/promises');const vm=await import('node:vm');
 const prefs=new Map(),events=[];
 const context=vm.createContext({Services:{prefs:{setStringPref:(k,v)=>prefs.set(k,v),setIntPref:(k,v)=>prefs.set(k,v),clearUserPref:k=>prefs.delete(k)}},
  ChromeUtils:{importESModule:url=>url.includes('Overrides')?{setOverride(){}}:url.includes('SeedSync')?{refreshContainerConfig:id=>events.push(id)}:
   url.includes('NetworkPolicy')?{setContainerNetwork(){}}:{listProxies:()=>[]}}});
 const source=await readFile(new URL('../../additions/browser/components/cloakfox/CloakfoxContainerWorkflows.sys.mjs',import.meta.url),'utf8');
 vm.runInContext(source.replace(/^import .*;\n/gm,'').replace(/^export /gm,''),context);
 const payload=fixtureV2(),record=payload.containers[0];record.network={mode:0,proxyURL:'',webrtcMode:0,proxyRef:null};
 const [warning]=backupAppearanceWarnings(payload,'Linux');
 prefs.set('cloakfox.container.99.persona_source','fpgen');
 context.writeRestoredIdentity(99,record,warning);
 assert.equal(prefs.get('cloakfox.container.99.persona_source'),'browserforge');
 assert.equal(prefs.get('cloakfox.container.99.restore_appearance_notice'),warning.message);
 assert.equal(prefs.get('cloakfox.container.99.persona_os_mode'),'host');
 for(const [name,value] of Object.entries(record.seeds))assert.equal(prefs.get('cloakfox.container.99.'+name),value);
 assert.deepEqual(events,[99]);
 Object.assign(record.settings,{persona_source:'fpgen',persona_os:'linux',persona_hardware:'intel',persona_browser:'firefox',persona_version:'159'});
 context.writeRestoredIdentity(100,record);
 for(const key of ['source','os','hardware','browser','version']) assert.equal(prefs.get('cloakfox.container.100.persona_'+key),record.settings['persona_'+key]);
 assert.equal(prefs.has('cloakfox.container.100.restore_appearance_notice'),false);
});

test('backup UI previews adaptation and reloads its persistent restoration notice',async()=>{
 const {readFile}=await import('node:fs/promises');const vm=await import('node:vm');
 class Element {
  constructor(tag){this.tag=tag;this.children=[];this.textContent='';this.listeners={};this.value='';}
  appendChild(node){this.children.push(node);return node;} replaceChildren(){this.children=[];}
  setAttribute(){} addEventListener(type,callback){this.listeners[type]=callback;}
 }
 const prefs=new Map(),confirmations=[],payload=fixtureV2();
 const [warning]=backupAppearanceWarnings(payload,'WINNT');
 const api={isSiteRoutingEnabled:()=>false,getSiteRules:()=>[],getTemporaryContainers:()=>[],nativeBackupAvailability:()=>({available:false,reason:'disabled'}),
  decryptIdentityBackup:async()=>payload,validateIdentityBackup:p=>validateIdentityBackup(p,schemasV2),backupAppearanceWarnings,
  restoreIdentityBackup:async()=>{prefs.set('cloakfox.container.99.restore_appearance_notice',warning.message);return [{userContextId:99,appearanceWarning:warning}];}};
 const source=await readFile(new URL('../../additions/browser/components/cloakfox/content/container-workflows.js',import.meta.url),'utf8');
 async function mount(){
  const main=new Element('main');
  const picker={init(){},appendFilter(){},open:callback=>callback(0),file:{path:'/virtual-backup'}};
  await vm.runInNewContext(source,{
   document:{createElement:tag=>new Element(tag),querySelector:()=>main},window:{browsingContext:{}},
   ChromeUtils:{importESModule:url=>url.includes('ContainerWorkflows')?api:url.includes('contextualidentity')?{ContextualIdentityService:{getPublicIdentities:()=>[{userContextId:99,name:'Restored'}]}}:
    url.includes('ProxyManager')?{listProxies:()=>[],getProxyReference:()=>null}:{getContainerNetwork:()=>({mode:0})}},
   Services:{appinfo:{OS:'WINNT'},prefs:{getStringPref:(key,fallback)=>prefs.get(key)??fallback},prompt:{confirm:(_win,_title,text)=>{confirmations.push(text);return true;}}},
   Cc:{'@mozilla.org/filepicker;1':{createInstance:()=>picker}},Ci:{nsIFilePicker:{modeSave:1,modeOpen:2,returnOK:0,returnReplace:1}},
   IOUtils:{stat:async()=>({size:10}),readUTF8:async()=> '{}'},Cu:{reportError:error=>{throw error;}}});
  return main.children[0];
 }
 const first=await mount();
 await first.children.find(node=>node.textContent==='Import as new containers').listeners.click();
 assert.match(confirmations[0],/adapts from macos to windows/);
 assert.match(confirmations[0],/saved seeds are preserved/);
 assert.match(first.children.find(node=>node.id==='cfx-workflows-status').textContent,/Appearance notice/);
 const reloaded=await mount();
 assert.ok(reloaded.children.some(node=>node.textContent.includes('Restored (container 99): '+warning.message)));
});

test('OS-specific generation modes survive backup validation', () => {
  for (const mode of ['windows','macos','linux']) {
    const data=fixtureV2();data.containers[0].settings.persona_os_mode=mode;
    assert.deepEqual(validateIdentityBackup(data,schemasV2),data);
  }
});


test('v3 backup strictly persists provider and filters with encrypted version binding', async () => {
 const value=fixture();value.version=3;value.sourceOS='linux';const record=value.containers[0];
 Object.assign(record,{region:null,policy:{version:1,preset:'standard',exceptions:[]},startPages:[]});record.network.proxyRef=null;
 Object.assign(record.settings,{persona_os_mode:'legacy',persona_source:'fpgen',persona_os:'linux',persona_hardware:'intel',persona_browser:'firefox',persona_version:'159'});
 const extended={...schemas,region:x=>x,policy:x=>x,startPages:x=>x};
 assert.deepEqual(validateIdentityBackup(value,extended),value);
 const envelope=await encryptIdentityBackup(value,'a sufficiently long password',webcrypto);
 assert.equal(envelope.version,3);assert.deepEqual(await decryptIdentityBackup(envelope,'a sufficiently long password',webcrypto),value);
 for(const [key,bad] of [['persona_source','bad'],['persona_os','android'],['persona_hardware','secret'],['persona_browser','other'],['persona_version','all']]) {
  const invalid=structuredClone(value);invalid.containers[0].settings[key]=bad;assert.throws(()=>validateIdentityBackup(invalid,extended));
 }
 const old=fixture();old.containers[0].settings.persona_source='fpgen';assert.throws(()=>validateIdentityBackup(old,extended));
});
