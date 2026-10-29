import assert from 'node:assert/strict';
import test from 'node:test';
import { webcrypto } from 'node:crypto';
import { validateTemplate, validateStartPages, migrateTemplate, templatePresets, captureTemplate,
  saveTemplate, listTemplates, exportTemplates, importTemplates, createFromTemplate } from '../../additions/browser/components/cloakfox/CloakfoxTemplates.sys.mjs';
import { validateRegion } from '../../additions/browser/components/cloakfox/CloakfoxRegions.sys.mjs';
import { validatePrivacyPolicy } from '../../additions/browser/components/cloakfox/CloakfoxPrivacyPolicy.sys.mjs';
const schemas = { colors: ['blue', 'gray', 'orange', 'purple'], icons: ['fingerprint', 'briefcase'], region: validateRegion,
  policy: validatePrivacyPolicy };
const fixture = () => { const {personaGeneration, ...value} = templatePresets()[0]; return {...value, version:1}; };
function store() {
  let saved = '[]', count = 0;
  return { schemas, read: () => saved, write: value => { saved = value; }, uuid: () => 'template-' + ++count };
}
test('strict settings schema rejects secrets, IDs, arbitrary overrides and malformed settings', () => {
  assert.deepEqual(validateTemplate(fixture(), schemas), fixture());
  for (const field of ['seeds', 'masterSeed', 'cookies', 'logins', 'password', 'proxyURL', 'overrides', 'sourceId']) {
    assert.throws(() => validateTemplate({ ...fixture(), [field]: 'secret' }, schemas));
  }
  for (const change of [{ personaIndex: 30 }, { personaIndex: -2 }, { temporary: 'true' }, { proxyRef: '../secret' }, { version: 2 }, { startPages: null }, { region: { masterSeed: 'secret' } }]) {
    assert.throws(() => validateTemplate({ ...fixture(), ...change }, schemas));
  }
  assert.throws(() => validateTemplate(Object.assign(Object.create({ polluted: true }), fixture()), schemas));
});
test('opening pages reject privileged schemes and embedded authentication', () => {
  assert.deepEqual(validateStartPages(['https://example.com', 'about:blank']), ['https://example.com/', 'about:blank']);
  for (const page of ['javascript:alert(1)', 'file:///secret', 'about:config', 'data:text/plain,x', 'https://user:pass@example.com', 'chrome://browser/content/browser.xhtml']) assert.throws(() => validateStartPages([page]));
  assert.throws(() => validateStartPages(Array(21).fill('about:blank')));
});
test('version 0 migration preserves settings and derives required route without accepting future versions', () => {
  const old = { ...fixture(), version: 0, proxyRef: 'saved-proxy' }; delete old.proxyRequired;
  const migrated = migrateTemplate(old, schemas);
  assert.equal(migrated.version, 1); assert.equal(migrated.proxyRequired, true);
  assert.deepEqual(migrateTemplate(migrated, schemas), migrated);
  assert.throws(() => migrateTemplate({ ...old, cookies: [] }, schemas));
  assert.throws(() => migrateTemplate({ ...old, version: 999 }, schemas));
});
test('capture copies only enumerated settings and detaches records from source objects', () => {
  const policy = fixture().policy;
  const deps = { schemas, identity: () => ({ color: 'blue', icon: 'fingerprint', seeds: 'secret' }), temporary: () => false,
    personaIndex: () => 3, region: () => null, policy: () => policy, proxyRef: () => 'proxy-1', networkMode: () => 1 };
  const record = captureTemplate(7, 'Work copy', ['https://example.com'], deps);
  assert.equal(record.personaIndex, 3); assert.equal(record.proxyRequired, true);
  assert.equal(JSON.stringify(record).includes('secret'), false);
  record.policy.preset = 'strict'; assert.equal(policy.preset, 'standard');
});
test('catalog import creates fresh IDs, survives reload, and rejects hostile imports atomically', () => {
  const deps = store(); const original = saveTemplate(fixture(), deps);
  const payload = exportTemplates(deps); const [imported] = importTemplates(payload, deps);
  assert.notEqual(imported.id, original.id); assert.deepEqual(imported.settings, original.settings);
  assert.equal(listTemplates({ ...deps }).length, 2);
  const previous = deps.read();
  assert.throws(() => importTemplates({ ...payload, templates: [fixture(), { ...fixture(), seeds: 'secret' }] }, deps));
  assert.equal(deps.read(), previous);
  assert.equal(JSON.stringify(payload).includes(original.id), false);
});
test('creation writes distinct persistent secrets into fresh containers before opening pages', async () => {
  const events = [], containers = new Map(); let nextId = 80;
  const deps = { schemas, hasProxy: () => true, create: value => { const id = ++nextId; containers.set(id, { name: value.name }); return id; },
    initialize: (id, value) => { containers.get(id).seed = Buffer.from(webcrypto.getRandomValues(new Uint8Array(32))).toString('base64'); containers.get(id).settings = value; events.push('initialize'); },
    save: () => events.push('save'), remove: id => containers.delete(id), open: (id, pages) => { assert.equal(events.at(-1), 'save'); events.push('open'); assert.ok(containers.get(id).seed); } };
  const a = await createFromTemplate(fixture(), null, deps), b = await createFromTemplate(fixture(), null, deps);
  assert.notEqual(a, b); assert.notEqual(containers.get(a).seed, containers.get(b).seed);
  const disk = JSON.stringify([...containers]); const restarted = new Map(JSON.parse(disk));
  assert.equal(restarted.get(a).seed, containers.get(a).seed);
});
test('missing proxy is rejected before creation, unbound required preset remains explicitly blocked', async () => {
  let creates = 0;
  await assert.rejects(createFromTemplate({ ...fixture(), proxyRef: 'missing' }, null, { schemas, hasProxy: () => false, create: () => { creates++; } }), /missing/);
  assert.equal(creates, 0);
  const value = templatePresets()[3];
  await createFromTemplate(value, null, { schemas, hasProxy: () => false, create: () => 1,
    initialize: (id, settings) => { assert.equal(settings.proxyRequired, true); assert.equal(settings.proxyRef, null); }, save() {}, remove() {}, open() {} });
});
test('failed initialization removes only newly created identity and saves cleanup; opening failure preserves configured container', async () => {
  const removed = [], events = [];
  const deps = { schemas, hasProxy: () => true, create: () => 99, initialize: () => { throw Error('invalid configuration'); },
    save: () => events.push('save'), remove: id => removed.push(id), open: () => events.push('open') };
  await assert.rejects(createFromTemplate(fixture(), null, deps), /invalid configuration/);
  assert.deepEqual(removed, [99]); assert.deepEqual(events, ['save']);
  removed.length = 0; deps.initialize = () => {}; deps.open = () => { throw Error('tab failed'); };
  await assert.rejects(createFromTemplate(fixture(), null, deps), /tab failed/); assert.deepEqual(removed, []);
});

test('native creation generates fresh independent seeds, config and opening tabs after route binding and persistence', async () => {
  const previous = { Services: globalThis.Services, ChromeUtils: globalThis.ChromeUtils, crypto: globalThis.crypto };
  const prefs = new Map(), events = [], identities = new Map(); let nextId = 100, persisted;
  const cis = { containerColors: schemas.colors, containerIcons: schemas.icons, _saver: { disarm() {} }, saveSoon() {},
    create: (name, icon, color) => { const identity = { userContextId: ++nextId, name, icon, color }; identities.set(nextId, identity); return identity; },
    save: async () => events.push('identities-saved'), remove: id => identities.delete(id) };
  const modules = {
    CloakfoxContainerWorkflows: {}, CloakfoxRegions: { validateRegion, setRegion: () => events.push('region') },
    CloakfoxPrivacyPolicy: { validatePrivacyPolicy: schemas.policy, setPrivacyPolicy: () => events.push('policy') },
    CloakfoxProxyManager: { listProxies: () => [{ id: 'proxy-1' }], bindProxy: id => { prefs.set(`cloakfox.container.${id}.network_mode`, 1); events.push('bound'); } },
    CloakfoxSeedSync: { refreshContainerConfig: id => { assert.equal(prefs.get(`cloakfox.container.${id}.math_seed`).length, 44); events.push('config'); } },
    CloakfoxNetworkPolicy: { setContainerNetwork: (id, value) => prefs.set(`cloakfox.container.${id}.network_mode`, value.mode) },
  };
  globalThis.Services = { prefs: { setIntPref: (key, value) => prefs.set(key, value), setStringPref: (key, value) => prefs.set(key, value),
    savePrefFile: () => { persisted = new Map(prefs); events.push('persisted'); } } };
  globalThis.ChromeUtils = { importESModule: url => url.includes('ContextualIdentityService') ? { ContextualIdentityService: cis } : modules[url.match(/\/([^/]+)\.sys\.mjs$/)[1]] };
  Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true });
  const opened = [];
  const win = { gBrowser: { tabs: [], addTrustedTab: (url, { userContextId: id }) => {
    assert.equal(events.at(-1), 'persisted'); assert.equal(persisted.get(`cloakfox.container.${id}.network_mode`), 1); opened.push({ url, id }); return {};
  } } };
  try {
    const value = { ...fixture(), proxyRef: 'proxy-1', startPages: ['https://example.com/'] };
    const first = await createFromTemplate(value, win), second = await createFromTemplate(value, win);
    const allSeeds = [first, second].flatMap(id => ['math_seed','keyboard_seed','timing_seed'].map(key => prefs.get(`cloakfox.container.${id}.${key}`)));
    assert.equal(new Set(allSeeds).size, 6); assert.ok(allSeeds.every(seed => atob(seed).length === 32));
    assert.deepEqual(opened, [{ url: 'https://example.com/', id: first }, { url: 'https://example.com/', id: second }]);
    assert.equal(persisted.get(`cloakfox.container.${first}.math_seed`), allSeeds[0]);
    assert.equal(prefs.has(`cloakfox.container.${first}.cookies`), false);
  } finally {
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete globalThis[key]; else Object.defineProperty(globalThis, key, { value, configurable: true, writable: true });
    }
  }
});

test('settings UI mounts, saves selected container settings and creates edited templates through the native API', async () => {
  const { readFile } = await import('node:fs/promises'); const { runInNewContext } = await import('node:vm');
  class Element {
    constructor(tag) { this.tag = tag; this.children = []; this.listeners = {}; this.value = ''; this.checked = false; this.textContent = ''; }
    appendChild(child) { this.children.push(child); if (this.tag === 'select' && this.children.length === 1) Object.defineProperty(this, 'value', { get: () => this._value ?? this.children[0]?.value ?? '', set: value => { this._value = value; }, configurable: true }); return child; }
    replaceChildren() { this.children = []; this._value = undefined; }
    setAttribute() {} addEventListener(name, callback) { this.listeners[name] = callback; }
  }
  const section = new Element('section'), container = new Element('select'); container.value = '7';
  const deps = store(), captures = [], creations = [];
  const api = { templatePresets, listTemplates: () => listTemplates(deps), saveTemplate: value => saveTemplate(value, deps),
    captureTemplate: (id, name, pages) => { captures.push({ id, name, pages }); return { ...fixture(), name, startPages: pages }; },
    createFromTemplate: async value => { creations.push(value); return 123; } };
  runInNewContext(await readFile(new URL('../../additions/browser/components/cloakfox/content/template-settings.js', import.meta.url), 'utf8'), {
    document: { getElementById: id => id === 'cfx-template-settings' ? section : container, createElement: tag => new Element(tag) },
    ChromeUtils: { importESModule: url => url.includes('CloakfoxTemplates') ? api : url.includes('CloakfoxPersonas') ? {listPersonas: () => [{index:5,label:'Host persona'}]} : { listProxies: () => [{ id: 'proxy-1', name: 'Work proxy' }] } },
    Services: { appinfo: {OS: 'Darwin'}, wm: { getMostRecentWindow: () => ({}) } },
  });
  const buttons = section.children.filter(node => node.tag === 'button');
  const inputs = section.children.filter(node => node.tag === 'label').map(node => node.children[0]);
  const [choose, name, opening, proxy, required, temporary, mode, persona] = inputs;
  name.value = 'Research'; opening.value = 'https://example.com/';
  await buttons.find(button => button.textContent === 'Save selected container as template').listeners.click();
  assert.equal(captures.length, 1); assert.equal(captures[0].id, 7); assert.equal(captures[0].name, 'Research');
  mode.value = 'host'; mode.listeners.change(); assert.equal(persona.value, '-1');
  proxy.value = 'proxy-1'; required.checked = true; temporary.checked = true; persona.value = '5';
  await buttons.find(button => button.textContent === 'Create fresh container').listeners.click();
  assert.equal(creations.length, 1); assert.equal(creations[0].proxyRef, 'proxy-1'); assert.equal(creations[0].temporary, true); assert.equal(creations[0].personaIndex, 5); assert.equal(creations[0].personaOSMode,'host');
  assert.ok(section.children.some(node => node.textContent.includes('Container 123 created')));
});

test('template mode preserves legacy pins and gives new presets mixed OS mode',()=>{
 const old=fixture();delete old.personaOSMode;
 assert.equal(validateTemplate(old,schemas).personaOSMode,'legacy');
 assert.ok(templatePresets().every(p=>p.personaOSMode==='legacy'));
 assert.throws(()=>validateTemplate({...old,personaOSMode:'foreign'},schemas));
 const host=validateTemplate({...old,personaOSMode:'host',personaIndex:5},schemas);
 assert.equal(host.personaOSMode,'host');assert.equal(host.personaIndex,5);
});

test('templates retain explicit generation operating systems', () => {
  for (const mode of ['windows','macos','linux']) assert.equal(validateTemplate({...fixture(),personaOSMode:mode},schemas).personaOSMode,mode);
});


test('version 2 templates retain provider and generation filters and reject malformed fields', () => {
 const generation={source:'fpgen',os:'linux',hardware:'intel',browser:'firefox',version:'159'};
 const value={...fixture(),version:2,personaGeneration:generation};
 assert.deepEqual(validateTemplate(value,schemas).personaGeneration,generation);
 for(const change of [{source:'other'},{os:'mobile'},{hardware:'bad'},{browser:'opera'},{version:'evil'},{secret:'captured'}]) {
  assert.throws(()=>validateTemplate({...value,personaGeneration:{...generation,...change}},schemas));
 }
 const deps=store();saveTemplate(value,deps); const payload=exportTemplates(deps);
 assert.equal(payload.version,2);assert.deepEqual(importTemplates(payload,deps)[0].settings.personaGeneration,generation);
 assert.throws(()=>importTemplates({...payload,version:1},deps));
 assert.equal(captureTemplate(7,'existing',[],{schemas,identity:()=>({color:'blue',icon:'fingerprint'}),temporary:()=>false,personaIndex:()=>-1,region:()=>null,policy:()=>fixture().policy,proxyRef:()=>null,networkMode:()=>0}).personaGeneration.source,'browserforge');
});

test('capture reads generation settings from the selected owner and creation persists them',async()=>{
 const generation={source:'fpgen',os:'linux',hardware:'intel',browser:'firefox',version:'159'};
 const owner=[];
 const record=captureTemplate(17,'selected',[],{schemas,identity:()=>({color:'blue',icon:'fingerprint'}),temporary:()=>false,personaIndex:()=>-1,personaGeneration:id=>{owner.push(id);return generation;},region:()=>null,policy:()=>fixture().policy,proxyRef:()=>null,networkMode:()=>0});
 assert.deepEqual(owner,[17]);assert.deepEqual(record.personaGeneration,generation);record.personaGeneration.hardware='amd';assert.equal(generation.hardware,'intel');
 let initialized;
 await createFromTemplate(record,null,{schemas,hasProxy:()=>true,create:()=>18,initialize:(_id,value)=>{initialized=value;},save(){},remove(){},open(){}});
 assert.deepEqual(initialized.personaGeneration,record.personaGeneration);
});
