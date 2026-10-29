/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

const PREF = 'cloakfox.templates';
const FORMAT = 'cloakfox-container-templates';
const KEYS = ['version', 'name', 'color', 'icon', 'temporary', 'personaIndex', 'personaOSMode', 'region', 'policy', 'proxyRef', 'proxyRequired', 'startPages'];
function exact(value, keys) {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      (Object.getPrototypeOf(value) !== null && Object.getPrototypeOf(Object.getPrototypeOf(value)) !== null) ||
      Object.keys(value).some(key => !keys.includes(key))) throw new Error('Unknown or invalid template field');
}
function clone(value) { return JSON.parse(JSON.stringify(value)); }
export function validateStartPages(pages) {
  if (!Array.isArray(pages) || pages.length > 20) throw new Error('Use at most 20 opening pages');
  return pages.map(page => {
    if (typeof page !== 'string' || page.length > 4096) throw new Error('Invalid opening page');
    if (page === 'about:blank') return page;
    const url = new URL(page);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error('Opening pages must use HTTP or HTTPS without embedded credentials');
    return url.href;
  });
}
export function validatePersonaGeneration(value) {
  exact(value, ['source', 'os', 'hardware', 'browser', 'version']);
  if (!['fpgen', 'browserforge'].includes(value.source) ||
      !['auto', 'windows', 'macos', 'linux'].includes(value.os) ||
      !['auto', 'apple', 'intel', 'nvidia', 'amd', 'software', 'other'].includes(value.hardware) ||
      !['firefox', 'chrome', 'edge', 'chromium', 'safari'].includes(value.browser) ||
      typeof value.version !== 'string' || !/^(auto|random-recent|[1-9][0-9]{0,2})$/.test(value.version)) {
    throw new Error('Invalid persona generation settings');
  }
  return clone(value);
}
export function readPersonaGeneration(id) {
  const defaults = {source:'browserforge', os:'auto', hardware:'auto', browser:'firefox', version:'auto'};
  return validatePersonaGeneration(Object.fromEntries(Object.entries(defaults).map(([key, fallback]) =>
    [key, Services.prefs.getStringPref(`cloakfox.container.${id}.persona_${key}`, fallback)])));
}
function legacyPersonaGeneration() {
  return {source:'browserforge', os:'auto', hardware:'auto', browser:'firefox', version:'auto'};
}
export function validateTemplate(value, schemas = nativeSchemas()) {
  exact(value, [...KEYS, ...(value?.version === 2 ? ['personaGeneration'] : [])]);
  if (value.version === 2) {
    validatePersonaGeneration(value.personaGeneration);
    if (value.personaIndex >= 0 && value.personaGeneration.source !== 'browserforge') throw new Error('Pinned previews require BrowserForge');
  }
  if (![1, 2].includes(value.version) || typeof value.name !== 'string' || !value.name.trim() || value.name.length > 128 ||
      !schemas.colors.includes(value.color) || !schemas.icons.includes(value.icon) ||
      typeof value.temporary !== 'boolean' || typeof value.proxyRequired !== 'boolean' ||
      !(value.personaOSMode === undefined || ['host', 'legacy', 'windows', 'macos', 'linux'].includes(value.personaOSMode)) ||
      !Number.isInteger(value.personaIndex) || value.personaIndex < -1 || value.personaIndex >= 30 ||
      !(value.proxyRef === null || (typeof value.proxyRef === 'string' && /^[a-zA-Z0-9_-]{1,128}$/.test(value.proxyRef)))) {
    throw new Error('Invalid template settings');
  }
  const region = value.region === null ? null : schemas.region(value.region);
  const policy = schemas.policy(value.policy);
  return { ...clone(value), personaOSMode: value.personaOSMode ?? "legacy", name: value.name.trim(), region: clone(region), policy: clone(policy), startPages: validateStartPages(value.startPages) };
}
// Version 0 used the same settings but had no explicit required-route flag.
// Migrate only this known shape; unknown versions and fields fail closed.
export function migrateTemplate(value, schemas = nativeSchemas()) {
  if (value?.version === 0) {
    exact(value, KEYS.filter(key => key !== 'proxyRequired'));
    return validateTemplate({ ...value, version: 1, proxyRequired: value.proxyRef !== null }, schemas);
  }
  return validateTemplate(value, schemas);
}
export function templatePresets() {
  const base = { version: 2, personaGeneration: {...legacyPersonaGeneration(), source:'fpgen'}, color: 'blue', icon: 'fingerprint', temporary: false, personaIndex: -1, personaOSMode: 'legacy',
    region: null, policy: { version: 1, preset: 'standard', exceptions: [] }, proxyRef: null, proxyRequired: false, startPages: [] };
  return [ { ...clone(base), name: 'Personal browsing' }, { ...clone(base), name: 'Work', color: 'orange', icon: 'briefcase' },
    { ...clone(base), name: 'Temporary research', color: 'gray', temporary: true },
    { ...clone(base), name: 'Proxy-required browsing', color: 'purple', proxyRequired: true } ];
}
function module(name) { return ChromeUtils.importESModule(`resource:///modules/${name}.sys.mjs`); }
function identities() { return ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService; }
function nativeSchemas() {
  const cis = identities();
  return { colors: cis.containerColors, icons: cis.containerIcons,
    region: module('CloakfoxRegions').validateRegion,
    policy: module('CloakfoxPrivacyPolicy').validatePrivacyPolicy };
}
function storeDependencies() {
  return { schemas: nativeSchemas(), read: () => Services.prefs.getStringPref(PREF, '[]'),
    write: value => { Services.prefs.setStringPref(PREF, value); Services.prefs.savePrefFile(null); },
    uuid: () => Services.uuid.generateUUID().toString().slice(1, -1) };
}
export function listTemplates(deps = storeDependencies()) {
  const records = JSON.parse(deps.read());
  if (!Array.isArray(records) || records.length > 200) throw new Error('Invalid template catalog');
  const ids = new Set();
  return records.map(record => {
    exact(record, ['id', 'settings']);
    if (typeof record.id !== 'string' || !/^[a-zA-Z0-9_-]{1,128}$/.test(record.id) || ids.has(record.id)) throw new Error('Invalid template ID');
    ids.add(record.id);
    return { id: record.id, settings: migrateTemplate(record.settings, deps.schemas) };
  });
}
export function saveTemplate(settings, deps = storeDependencies()) {
  const records = listTemplates(deps);
  if (records.length >= 200) throw new Error('Template limit reached');
  const record = { id: deps.uuid(), settings: validateTemplate(settings, deps.schemas) };
  if (records.some(item => item.id === record.id)) throw new Error('Template ID collision');
  deps.write(JSON.stringify([...records, record]));
  return record;
}
export function removeTemplate(id, deps = storeDependencies()) {
  deps.write(JSON.stringify(listTemplates(deps).filter(record => record.id !== id)));
}
export function exportTemplates(deps = storeDependencies()) {
  return { format: FORMAT, version: 2, templates: listTemplates(deps).map(record => record.settings) };
}
export function importTemplates(payload, deps = storeDependencies()) {
  exact(payload, ['format', 'version', 'templates']);
  if (payload.format !== FORMAT || ![1, 2].includes(payload.version) || !Array.isArray(payload.templates) || payload.templates.length > 200 ||
      JSON.stringify(payload).length > 1024 * 1024) throw new Error('Unsupported template export');
  const records = listTemplates(deps);
  if (records.length + payload.templates.length > 200) throw new Error('Template limit reached');
  if (payload.version === 1 && payload.templates.some(value => value?.version === 2)) throw new Error('Template export version mismatch');
  const added = payload.templates.map(value => ({ id: deps.uuid(), settings: migrateTemplate(value, deps.schemas) }));
  if (new Set([...records, ...added].map(record => record.id)).size !== records.length + added.length) throw new Error('Template ID collision');
  deps.write(JSON.stringify([...records, ...added]));
  return added;
}
export function captureTemplate(id, name, startPages = [], deps = nativeCaptureDependencies()) {
  return validateTemplate({ version: 2, personaGeneration: deps.personaGeneration?.(id) ?? legacyPersonaGeneration(), name, color: deps.identity(id).color, icon: deps.identity(id).icon,
    temporary: deps.temporary(id), personaIndex: deps.personaIndex(id), personaOSMode: deps.personaOSMode?.(id) ?? "legacy", region: deps.region(id), policy: deps.policy(id),
    proxyRef: deps.proxyRef(id), proxyRequired: deps.networkMode(id) !== 0, startPages }, deps.schemas);
}
function nativeCaptureDependencies() {
  return { schemas: nativeSchemas(), identity: id => identities().getPublicIdentityFromId(id) || { color: 'blue', icon: 'fingerprint' },
    personaGeneration: readPersonaGeneration,
    temporary: id => module('CloakfoxContainerWorkflows').getTemporaryContainers().includes(id),
    personaOSMode: id => Services.prefs.getStringPref(`cloakfox.container.${id}.persona_os_mode`, "legacy"),
    personaIndex: id => Services.prefs.getIntPref(`cloakfox.container.${id}.persona_index`, -1),
    region: id => module('CloakfoxRegions').getRegion(id), policy: id => module('CloakfoxPrivacyPolicy').getPrivacyPolicy(id),
    proxyRef: id => module('CloakfoxProxyManager').getProxyReference(id),
    networkMode: id => module('CloakfoxNetworkPolicy').getContainerNetwork(id).mode };
}
export async function createFromTemplate(settings, win, deps = nativeCreationDependencies(win)) {
  const value = validateTemplate(settings, deps.schemas);
  if (value.proxyRef !== null && !deps.hasProxy(value.proxyRef)) throw new Error('The saved proxy reference is missing; select an existing proxy before creating this container');
  let id;
  try {
    id = await deps.create(value);
    await deps.initialize(id, value);
    await deps.save();
  } catch (error) {
    if (id !== undefined) {
      try { await deps.remove(id); await deps.save(); }
      catch (_) { throw new Error('Template creation failed and cleanup is incomplete. ' + error.message); }
    }
    throw error;
  }
  // Keep the successfully initialized container if opening a tab fails.
  await deps.open(id, value.startPages.length ? value.startPages : ['about:blank']);
  return id;
}
function nativeCreationDependencies(win) {
  const cis = identities(), workflows = module('CloakfoxContainerWorkflows');
  if (!win?.gBrowser) throw new Error('Open a browser window to create a container');
  const flush = async () => {
    if (cis._saver?.isRunning) await cis._saver.finalize();
    cis.saveSoon(); cis._saver.disarm(); await cis.save(); Services.prefs.savePrefFile(null);
  };
  return { schemas: nativeSchemas(), hasProxy: ref => module('CloakfoxProxyManager').listProxies().some(proxy => proxy.id === ref),
    create: async value => {
      if (!value.temporary) return cis.create(value.name, value.icon, value.color).userContextId;
      return workflows.createTemporaryContainer(win);
    },
    initialize: (id, value) => {
      const prefix = `cloakfox.container.${id}.`;
      if (value.temporary) cis.update(id, value.name, value.icon, value.color);
      Services.prefs.setIntPref(prefix + 'network_mode', 2);
      Services.prefs.setStringPref(prefix + 'persona_os_mode', value.personaOSMode);
      for (const [key, setting] of Object.entries(value.personaGeneration ?? legacyPersonaGeneration())) {
        Services.prefs.setStringPref(prefix + 'persona_' + key, setting);
      }
      for (const key of ['math_seed', 'keyboard_seed', 'timing_seed']) {
        const bytes = crypto.getRandomValues(new Uint8Array(32));
        Services.prefs.setStringPref(prefix + key, btoa(String.fromCharCode(...bytes)));
      }
      Services.prefs.setIntPref(prefix + 'persona_index', value.personaIndex);
      Services.prefs.setStringPref(prefix + 'start_pages', JSON.stringify(value.startPages));
      module('CloakfoxRegions').setRegion(id, value.region);
      module('CloakfoxPrivacyPolicy').setPrivacyPolicy(id, value.policy);
      module('CloakfoxSeedSync').refreshContainerConfig(id);
      if (value.proxyRef !== null) module('CloakfoxProxyManager').bindProxy(id, value.proxyRef);
      else module('CloakfoxNetworkPolicy').setContainerNetwork(id, { mode: value.proxyRequired ? 2 : 0, proxyURL: '', webrtcMode: value.proxyRequired ? 2 : 0 });
    }, save: flush,
    remove: async id => {
      for (const tab of [...win.gBrowser.tabs]) if (Number(tab.getAttribute('usercontextid')) === id) win.gBrowser.removeTab(tab);
      if (!cis.remove(id)) throw new Error('Could not remove new container');
      Services.prefs.deleteBranch(`cloakfox.container.${id}.`);
      Services.prefs.clearUserPref(`cloakfox.s.cloak_cfg_${id}`);
      // Temporary recovery owns any remaining marker and safely clears orphans.
    },
    open: (id, pages) => { for (const page of pages) win.gBrowser.selectedTab = win.gBrowser.addTrustedTab(page, { userContextId: id }); } };
}
