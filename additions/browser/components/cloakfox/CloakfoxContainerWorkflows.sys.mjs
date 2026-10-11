/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

const BACKUP_FORMAT = 'cloakfox-identity-settings';
const ENCRYPTED_FORMAT = 'cloakfox-encrypted-identity-settings';
const ITERATIONS = 600000;
const MAX_BYTES = 2 * 1024 * 1024;
const TEMP_PREF = 'cloakfox.temporary_containers';
const SEEDS = ['math_seed', 'keyboard_seed', 'timing_seed'];
const temporaryOperations = new Set();
let initialized = false;
let restoreInProgress = false;

export function normalizeRuleHost(input, registrableDomain = host => Services.eTLD.getBaseDomainFromHost(host)) {
  if (typeof input !== 'string') throw new Error('Enter a hostname');
  const value = input.trim().replace(/\.$/, '');
  if (!value || /[\s\/:@?#*\\]/.test(value)) throw new Error('Enter an exact hostname, without a URL, path or wildcard');
  const host = new URL('https://' + value).hostname.toLowerCase();
  if (host.length > 253 || host.split('.').some(label => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))) {
    throw new Error('Invalid hostname');
  }
  try { registrableDomain(host); } catch (_) { throw new Error('Use a registrable hostname, not an IP address or public suffix'); }
  return host;
}

function exactKeys(value, keys) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid backup object');
  const proto = Object.getPrototypeOf(value);
  if (proto !== null && Object.getPrototypeOf(proto) !== null) throw new Error('Invalid backup prototype');
  if (Object.keys(value).some(key => !keys.includes(key))) throw new Error('Unknown backup field');
}
function validId(value) { return Number.isInteger(value) && value >= 0 && value <= 0x7fffffff; }
function validSeed(value) {
  try { return typeof value === 'string' && value.length === 44 && atob(value).length === 32 && btoa(atob(value)) === value; }
  catch (_) { return false; }
}

export function validateIdentityBackup(data, schemas = nativeSchemas()) {
  exactKeys(data, ['format', 'version', 'containers', 'rules', ...(data.version === 2 ? ['sourceOS'] : [])]);
  if (data.format !== BACKUP_FORMAT || ![1, 2].includes(data.version) ||
      !Array.isArray(data.containers) || !data.containers.length || data.containers.length > 500 ||
      !Array.isArray(data.rules) || data.rules.length > 5000) throw new Error('Unsupported identity backup');
  if (new TextEncoder().encode(JSON.stringify(data)).length > MAX_BYTES) throw new Error('Identity backup is too large');
  if (data.sourceOS !== undefined && !['macos', 'windows', 'linux'].includes(data.sourceOS)) throw new Error('Invalid backup source OS');
  const ids = new Set();
  for (const record of data.containers) {
    exactKeys(record, ['sourceId', 'name', 'color', 'icon', 'seeds', 'settings', 'overrides', 'network', ...(data.version === 2 ? ['region', 'policy', 'startPages'] : [])]);
    if (!validId(record.sourceId) || ids.has(record.sourceId)) throw new Error('Invalid or duplicate container ID');
    ids.add(record.sourceId);
    if (typeof record.name !== 'string' || !record.name.trim() || record.name.length > 128 ||
        !schemas.colors.includes(record.color) || !schemas.icons.includes(record.icon)) throw new Error('Invalid container identity');
    exactKeys(record.seeds, SEEDS);
    if (!SEEDS.every(key => validSeed(record.seeds[key]))) throw new Error('Invalid identity seed');
    exactKeys(record.settings, ['timezone', 'persona_index', ...(data.version === 2 ? ['persona_os_mode'] : [])]);
    if (data.version === 2) {
      if (!['host', 'legacy', 'windows', 'macos', 'linux'].includes(record.settings.persona_os_mode)) throw new Error('Invalid persona OS mode');
      if (record.region !== null) schemas.region(record.region);
      schemas.policy(record.policy);
      schemas.startPages(record.startPages);
    }
    if (record.settings.timezone !== undefined) {
      if (typeof record.settings.timezone !== 'string' || record.settings.timezone.length > 128) throw new Error('Invalid timezone');
      if (record.settings.timezone) new Intl.DateTimeFormat('en', { timeZone: record.settings.timezone });
    }
    if (record.settings.persona_index !== undefined &&
        (!Number.isInteger(record.settings.persona_index) || record.settings.persona_index < -1 || record.settings.persona_index >= 30)) {
      throw new Error('Invalid persona index');
    }
    exactKeys(record.overrides, Object.keys(schemas.keyTypes));
    for (const [key, value] of Object.entries(record.overrides)) {
      const type = schemas.keyTypes[key];
      const valid = type === 'string' ? typeof value === 'string' && value.length <= 8192 :
        type === 'bool' ? typeof value === 'boolean' :
        type === 'int' ? Number.isInteger(value) && value >= -0x80000000 && value <= 0x7fffffff :
        type === 'float' && typeof value === 'number' && Number.isFinite(value);
      if (!valid) throw new Error('Invalid persona override');
    }
    exactKeys(record.network, ['mode', 'proxyURL', 'webrtcMode', ...(data.version === 2 ? ['proxyRef'] : [])]);
    const net = record.network;
    if (![0, 1, 2].includes(net.mode) || ![0, 1, 2].includes(net.webrtcMode) || typeof net.proxyURL !== 'string') {
      throw new Error('Invalid connection settings');
    }
    if (data.version === 2 && !(net.proxyRef === null ||
        (typeof net.proxyRef === 'string' && /^[a-f0-9-]{36}$/.test(net.proxyRef)))) throw new Error('Invalid proxy reference');
    if (net.proxyRef) {
      if (net.mode === 0 || net.proxyURL !== '') throw new Error('Named proxy backups must not contain a fallback endpoint');
    } else if (net.mode === 1) schemas.normalizeProxy(net.proxyURL);
    else if (net.proxyURL !== '') throw new Error('Unexpected proxy address');
  }
  const hosts = new Set();
  for (const rule of data.rules) {
    exactKeys(rule, ['host', 'sourceId']);
    const normalized = schemas.normalizeHost(rule.host);
    if (normalized !== rule.host || hosts.has(normalized) || !ids.has(rule.sourceId)) throw new Error('Invalid or duplicate site rule');
    hosts.add(normalized);
  }
  return data;
}

function backupOS(value) {
  return ({Darwin:'macos',WINNT:'windows',Linux:'linux',macos:'macos',windows:'windows',linux:'linux'})[value] || null;
}
// This is a disclosure, not a migration: seeds and host/legacy mode are kept.
// Host mode intentionally samples against the destination native renderer.
export function backupAppearanceWarnings(payload, destinationOS = Services.appinfo.OS) {
  const destination = backupOS(destinationOS);
  return payload.containers.filter(record => record.settings.persona_os_mode === 'host' &&
    (!payload.sourceOS || !destination || payload.sourceOS !== destination)).map(record => {
    const source = payload.sourceOS || null;
    const reason = !source ? 'unknown-source-os' : !destination ? 'unknown-destination-os' : 'different-os';
    const message = source && destination ?
      `Host-mode appearance adapts from ${source} to ${destination}; saved seeds are preserved, but OS, hardware and pinned-persona appearance may change.` :
      `The ${!source ? 'backup source' : 'destination'} OS is unknown. Host-mode appearance adapts to ${destination || 'this computer'} during restore; saved seeds are preserved, but the original appearance cannot be guaranteed.`;
    return {sourceId:record.sourceId,sourceOS:source,destinationOS:destination,reason,message};
  });
}

function encode(bytes) {
  let result = '';
  for (let i = 0; i < bytes.length; i += 8192) result += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return btoa(result);
}
function decode(value, maxLength) {
  if (typeof value !== 'string' || value.length > maxLength * 2) throw new Error('Invalid encrypted backup');
  const bytes = Uint8Array.from(atob(value), c => c.charCodeAt(0));
  if (bytes.length > maxLength || encode(bytes) !== value) throw new Error('Invalid encrypted backup');
  return bytes;
}
async function backupKey(password, salt, cryptoAPI) {
  if (typeof password !== 'string' || password.length < 12 || password.length > 1024) throw new Error('Use a password of 12 to 1024 characters');
  const material = await cryptoAPI.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveKey']);
  return cryptoAPI.subtle.deriveKey({ name: 'PBKDF2', hash: 'SHA-256', iterations: ITERATIONS, salt },
    material, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
}
function cipherParams(iv, version) {
  return { name: 'AES-GCM', iv, additionalData: new TextEncoder().encode(BACKUP_FORMAT + ':v' + version), tagLength: 128 };
}
export async function encryptIdentityBackup(payload, password, cryptoAPI = crypto) {
  if (![1, 2].includes(payload?.version)) throw new Error('Unsupported identity backup');
  const bytes = new TextEncoder().encode(JSON.stringify(payload));
  if (bytes.length > MAX_BYTES) throw new Error('Identity backup is too large');
  const salt = cryptoAPI.getRandomValues(new Uint8Array(16));
  const iv = cryptoAPI.getRandomValues(new Uint8Array(12));
  const key = await backupKey(password, salt, cryptoAPI);
  const ciphertext = await cryptoAPI.subtle.encrypt(cipherParams(iv, payload.version), key, bytes);
  return { format: ENCRYPTED_FORMAT, version: payload.version, kdf: 'PBKDF2-SHA256', iterations: ITERATIONS,
    salt: encode(salt), iv: encode(iv), ciphertext: encode(new Uint8Array(ciphertext)) };
}
export async function decryptIdentityBackup(envelope, password, cryptoAPI = crypto) {
  exactKeys(envelope, ['format', 'version', 'kdf', 'iterations', 'salt', 'iv', 'ciphertext']);
  if (envelope.format !== ENCRYPTED_FORMAT || ![1, 2].includes(envelope.version) || envelope.kdf !== 'PBKDF2-SHA256' || envelope.iterations !== ITERATIONS) {
    throw new Error('Unsupported encrypted identity backup');
  }
  const salt = decode(envelope.salt, 16), iv = decode(envelope.iv, 12);
  if (salt.length !== 16 || iv.length !== 12) throw new Error('Invalid encrypted backup');
  const ciphertext = decode(envelope.ciphertext, MAX_BYTES + 16);
  const key = await backupKey(password, salt, cryptoAPI);
  let plain;
  try { plain = await cryptoAPI.subtle.decrypt(cipherParams(iv, envelope.version), key, ciphertext); }
  catch (_) { throw new Error('Incorrect password or damaged identity backup'); }
  const payload = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(plain));
  if (payload?.version !== envelope.version) throw new Error('Identity backup version mismatch');
  return payload;
}

export async function restoreIdentityBackup(payload, deps = nativeRestoreDependencies()) {
  if (restoreInProgress) throw new Error('An identity import is already in progress');
  restoreInProgress = true;
  try { return await performRestore(payload, deps); }
  finally { restoreInProgress = false; }
}
async function performRestore(payload, deps) {
  validateIdentityBackup(payload, deps.schemas);
  for (const rule of payload.rules) {
    if (deps.getRule(rule.host)) throw new Error(`A site rule for ${rule.host} already exists; remove it before importing`);
  }
  const appearanceWarnings = backupAppearanceWarnings(payload, deps.destinationOS?.() ?? null);
  const imported = [], rules = [];
  try {
    for (const record of payload.containers) {
      const id = await deps.create(record);
      imported.push({ sourceId: record.sourceId, userContextId: id });
      const appearanceWarning = appearanceWarnings.find(item => item.sourceId === record.sourceId);
      const outcome = await deps.write(id, record, appearanceWarning);
      if (appearanceWarning) imported.at(-1).appearanceWarning = appearanceWarning;
      if (outcome?.bindingRequired) imported.at(-1).bindingRequired = outcome.bindingRequired;
    }
    for (const rule of payload.rules) {
      if (deps.getRule(rule.host)) throw new Error('A site rule was added while importing; no existing rule was replaced');
      const id = imported.find(record => record.sourceId === rule.sourceId).userContextId;
      await deps.setRule(rule.host, id);
      rules.push({ host: rule.host, userContextId: id });
    }
    await deps.save();
    return imported;
  } catch (error) {
    let rollbackFailed = false;
    for (const rule of rules) {
      try {
        // A different settings window may have reassigned the host during save.
        // Roll back only the association still owned by this import.
        if (deps.getRule(rule.host) === rule.userContextId) await deps.removeRule(rule.host);
      } catch (_) { rollbackFailed = true; }
    }
    for (const record of imported.reverse()) { try { await deps.remove(record.userContextId); } catch (_) { rollbackFailed = true; } }
    try { await deps.save(); } catch (_) { rollbackFailed = true; }
    throw new Error((rollbackFailed ? 'Import failed; cleanup could not be saved completely. Newly created containers or rules may remain or return after restart. ' : 'Import failed; newly created containers were removed. ') + error.message);
  }
}

export async function cleanupTemporaryContainer(id, deps, { recovery = false } = {}) {
  if (!validId(id) || id === 0) throw new Error('Invalid temporary container ID');
  if (temporaryOperations.has(id) || (!recovery && deps.hasTabs(id))) return false;
  temporaryOperations.add(id);
  try {
    await deps.forget(id);
    await deps.remove(id);
    await deps.unmark(id);
    return true;
  } finally { temporaryOperations.delete(id); }
}

function identities() {
  return ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs').ContextualIdentityService;
}
function nativeSchemas() {
  const cis = identities();
  return { keyTypes: ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs').KEY_TYPES,
    normalizeHost: normalizeRuleHost, colors: cis.containerColors, icons: cis.containerIcons,
    normalizeProxy: ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkPolicy.sys.mjs').normalizeProxyURL,
    region: ChromeUtils.importESModule('resource:///modules/CloakfoxRegions.sys.mjs').validateRegion,
    policy: ChromeUtils.importESModule('resource:///modules/CloakfoxPrivacyPolicy.sys.mjs').validatePrivacyPolicy,
    startPages: ChromeUtils.importESModule('resource:///modules/CloakfoxTemplates.sys.mjs').validateStartPages };
}
export function isSiteRoutingEnabled() {
  return Services.prefs.getBoolPref('privacy.containers.switchDuringNavigation.enabled', false);
}
export function getSiteRules() { return identities().getSiteAssociations(); }
export function setSiteRule(host, id) {
  if (!isSiteRoutingEnabled()) throw new Error('Automatic site-container routing is disabled. Enable it in Containers and backups before adding a rule.');
  if (!validId(id) || !id || !identities().getPublicIdentityFromId(id)) throw new Error('Select a named container');
  identities().setSiteAssociation(normalizeRuleHost(host), id);
}
export function removeSiteRule(host) { identities().removeSiteAssociation(normalizeRuleHost(host)); }

export function captureIdentityBackup() {
  const cis = identities();
  const { readOverrides } = ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs');
  const { getContainerNetwork } = ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkPolicy.sys.mjs');
  const { getProxyReference } = ChromeUtils.importESModule('resource:///modules/CloakfoxProxyManager.sys.mjs');
  const { getRegion } = ChromeUtils.importESModule('resource:///modules/CloakfoxRegions.sys.mjs');
  const { getPrivacyPolicy } = ChromeUtils.importESModule('resource:///modules/CloakfoxPrivacyPolicy.sys.mjs');
  const temporary = new Set(getTemporaryContainers());
  const containers = [{ userContextId: 0, name: 'Default', icon: 'fingerprint', color: 'blue' }, ...cis.getPublicIdentities()]
    .filter(identity => !temporary.has(identity.userContextId)).map(identity => {
      const id = identity.userContextId, prefix = `cloakfox.container.${id}.`;
      const proxyRef = getProxyReference(id);
      const network = getContainerNetwork(id);
      const seeds = Object.fromEntries(SEEDS.map(key => [key, Services.prefs.getStringPref(prefix + key, '')]));
      return { sourceId: id, name: identity.name || cis.getUserContextLabel(id), color: identity.color, icon: identity.icon,
        seeds, settings: { timezone: Services.prefs.getStringPref(prefix + 'timezone', ''),
          persona_index: Services.prefs.getIntPref(prefix + 'persona_index', -1),
          persona_os_mode: Services.prefs.getStringPref(prefix + 'persona_os_mode', 'legacy') },
        region: getRegion(id), policy: getPrivacyPolicy(id),
        startPages: JSON.parse(Services.prefs.getStringPref(prefix + 'start_pages', '[]')),
        overrides: readOverrides(id), network: { ...network, proxyRef, proxyURL: proxyRef ? '' : network.proxyURL } };
    });
  const ids = new Set(containers.map(record => record.sourceId));
  const rules = getSiteRules().filter(rule => ids.has(rule.userContextId)).map(rule => ({ host: rule.site, sourceId: rule.userContextId }));
  return validateIdentityBackup({ format: BACKUP_FORMAT, version: 2, sourceOS: backupOS(Services.appinfo.OS), containers, rules });
}

function nativeRestoreDependencies() {
  const cis = identities();
  return { schemas: nativeSchemas(), destinationOS: () => Services.appinfo.OS, getRule: host => cis.getSiteAssociation(host),
    create: record => cis.create('Restored ' + record.name.slice(0, 110), record.icon, record.color).userContextId,
    write: writeRestoredIdentity,
    setRule: (host, id) => cis.setSiteAssociation(host, id), removeRule: host => cis.removeSiteAssociation(host),
    remove: id => {
      if (!cis.remove(id)) throw new Error('Could not remove imported container');
      Services.prefs.deleteBranch(`cloakfox.container.${id}.`);
      Services.prefs.clearUserPref(`cloakfox.s.cloak_cfg_${id}`);
    },
    save: async () => { await flushIdentities(); Services.prefs.savePrefFile(null); },
  };
}
// This helper deliberately leaves unresolved references present and blocked. A
// copied manual endpoint would silently bypass the credential/reference guard.
export function restoreBackupNetwork(id, network, deps = {
  setNetwork: (id, value) => ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkPolicy.sys.mjs').setContainerNetwork(id, value),
  hasProxy: ref => ChromeUtils.importESModule('resource:///modules/CloakfoxProxyManager.sys.mjs').listProxies().some(p => p.id === ref),
  bind: (id, ref) => ChromeUtils.importESModule('resource:///modules/CloakfoxProxyManager.sys.mjs').bindProxy(id, ref),
  retainReference: (id, ref) => Services.prefs.setStringPref(`cloakfox.container.${id}.proxy_ref`, ref),
}) {
  if (!network.proxyRef) { deps.setNetwork(id, network); return {}; }
  deps.setNetwork(id, { mode: 2, proxyURL: '', webrtcMode: network.webrtcMode });
  deps.retainReference(id, network.proxyRef);
  if (network.mode === 1 && deps.hasProxy(network.proxyRef)) {
    deps.bind(id, network.proxyRef);
    return {};
  }
  return { bindingRequired: network.proxyRef };
}
function writeRestoredIdentity(id, record, appearanceWarning) {
  const { setOverride } = ChromeUtils.importESModule('resource:///modules/CloakfoxOverrides.sys.mjs');
  const { refreshContainerConfig } = ChromeUtils.importESModule('resource:///modules/CloakfoxSeedSync.sys.mjs');
  const prefix = `cloakfox.container.${id}.`;
  // No imported rule can point at the new ID until all its settings are ready.
  Services.prefs.setIntPref(prefix + 'network_mode', 2);
  Services.prefs.setStringPref(prefix + 'persona_os_mode', record.settings.persona_os_mode || 'legacy');
  if (appearanceWarning) Services.prefs.setStringPref(prefix + 'restore_appearance_notice', appearanceWarning.message);
  else Services.prefs.clearUserPref(prefix + 'restore_appearance_notice');
  for (const [key, seed] of Object.entries(record.seeds)) Services.prefs.setStringPref(prefix + key, seed);
  if (record.settings.timezone !== undefined) Services.prefs.setStringPref(prefix + 'timezone', record.settings.timezone);
  if (record.settings.persona_index !== undefined) Services.prefs.setIntPref(prefix + 'persona_index', record.settings.persona_index);
  // Payload validation used the public feature schemas. Write their records
  // together, then rebuild once so region/policy are applied after overrides.
  if (record.region) Services.prefs.setStringPref(prefix + 'region', JSON.stringify(record.region));
  else Services.prefs.clearUserPref(prefix + 'region');
  Services.prefs.setStringPref(prefix + 'privacy_policy', JSON.stringify(record.policy || {version:1,preset:'standard',exceptions:[]}));
  Services.prefs.setStringPref(prefix + 'start_pages', JSON.stringify(record.startPages || []));
  for (const [key, value] of Object.entries(record.overrides)) setOverride(id, key, value);
  refreshContainerConfig(id);
  return restoreBackupNetwork(id, record.network);
}

export function getTemporaryContainers() {
  const result = JSON.parse(Services.prefs.getStringPref(TEMP_PREF, '[]'));
  if (!Array.isArray(result) || result.some(id => !validId(id) || !id) || new Set(result).size !== result.length) {
    throw new Error('Invalid temporary-container recovery list; no containers were removed');
  }
  return result;
}
function saveTemporary(ids) {
  Services.prefs.setStringPref(TEMP_PREF, JSON.stringify(ids));
  Services.prefs.savePrefFile(null);
}
function windows() { return Array.from(Services.wm.getEnumerator('navigator:browser')).filter(win => win.gBrowser && !win.closed); }
function hasTabs(id) {
  return windows().some(win => Array.from(win.gBrowser.tabs).some(tab => !tab.closing && Number(tab.getAttribute('usercontextid') || 0) === id));
}
export async function createTemporaryContainer(win) {
  getTemporaryContainers(); // validate recovery state before creating anything
  const identity = identities().create('Temporary ' + new Date().toLocaleTimeString(), 'fingerprint', 'gray');
  try {
    await flushIdentities();
    saveTemporary([...getTemporaryContainers(), identity.userContextId]);
    // Persist recovery ownership before opening a tab that can store site data.
    win.gBrowser.selectedTab = win.gBrowser.addTrustedTab('about:blank', { userContextId: identity.userContextId });
  } catch (error) {
    if (getTemporaryContainers().includes(identity.userContextId)) scheduleCleanup(identity.userContextId, true);
    else { identities().remove(identity.userContextId); await flushIdentities(); }
    throw error;
  }
  return identity.userContextId;
}
function nativeTemporaryDependencies() {
  const { forgetContainerData } = ChromeUtils.importESModule('resource:///modules/CloakfoxIdentityActions.sys.mjs');
  return { hasTabs, forget: id => forgetContainerData(id, { confirmed: true }),
    remove: async id => {
      if (!identities().remove(id)) throw new Error('Could not remove temporary container');
      Services.prefs.deleteBranch(`cloakfox.container.${id}.`);
      Services.prefs.clearUserPref(`cloakfox.s.cloak_cfg_${id}`);
      await flushIdentities();
    }, unmark: id => saveTemporary(getTemporaryContainers().filter(value => value !== id)) };
}
function reportError(error) {
  if (Services.prefs.getStringPref('cloakfox.workflows.last_error', '') !== error.message) {
    Services.prefs.setStringPref('cloakfox.workflows.last_error', error.message);
    Cu.reportError(error);
  }
}
function scheduleCleanup(id, recovery = false, attempt = 0) {
  const { setTimeout } = ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');
  setTimeout(async () => {
    try {
      if (!getTemporaryContainers().includes(id)) return;
      if (!identities().getPublicIdentityFromId(id)) {
        await clearOrphanTemporary(id);
        saveTemporary(getTemporaryContainers().filter(value => value !== id));
        return;
      }
      await cleanupTemporaryContainer(id, nativeTemporaryDependencies(), { recovery });
    } catch (error) {
      reportError(error);
      // A busy SessionStore or failed quota clearer must not silently abandon
      // an owned temporary container. Retry while retaining its recovery marker.
      scheduleCleanup(id, recovery, attempt + 1);
    }
  }, Math.min(60000, (recovery ? 5000 : 1000) * 2 ** Math.min(attempt, 6)));
}
export function initCloakfoxContainerWorkflows(deps = {
  windows, observe: (callback, topic) => Services.obs.addObserver(callback, topic),
  tracked: getTemporaryContainers, schedule: scheduleCleanup, report: reportError,
}) {
  if (initialized) return;
  initialized = true;
  const watch = win => {
    if (!win.gBrowser) return;
    win.gBrowser.tabContainer.addEventListener('TabClose', event => {
      const id = Number(event.target.getAttribute('usercontextid') || 0);
      try { if (deps.tracked().includes(id)) deps.schedule(id); } catch (error) { deps.report(error); }
    });
  };
  deps.windows().forEach(watch);
  deps.observe(win => win.addEventListener('load', () => watch(win), { once: true }), 'domwindowopened');
  // Whole-window teardown emits no TabClose. Schedule after it leaves window
  // enumeration; cleanup's hasTabs guard protects survivors in other windows.
  deps.observe(() => {
    try { deps.tracked().forEach(id => deps.schedule(id)); } catch (error) { deps.report(error); }
  }, 'domwindowclosed');
  try { deps.tracked().forEach(id => deps.schedule(id, true)); } catch (error) { deps.report(error); }
}

// The native service has no public flush wrapper. Disarm its DeferredTask and
// await the actual write, whose rejection must reach the importing UI. Calling
// DeferredTask.finalize alone is insufficient: that task logs write errors.
async function flushIdentities() {
  const cis = identities();
  if (cis._saver?.isRunning) await cis._saver.finalize();
  cis.saveSoon();
  cis._saver.disarm();
  await cis.save();
}
async function clearOrphanTemporary(id) {
  if (hasTabs(id)) throw new Error('An orphan temporary container still has tabs; close them to finish cleanup');
  const { SessionStore } = ChromeUtils.importESModule('resource:///modules/sessionstore/SessionStore.sys.mjs');
  SessionStore.assertContainerForgetReady();
  await SessionStore.forgetContainerRestoreData(id);
  const failed = await new Promise(resolve => Services.clearData.deleteDataFromOriginAttributesPattern(
    { userContextId: id }, { onDataDeleted: resolve }));
  if (failed) throw new Error('Orphan temporary data cleanup failed; it will be retried');
  await SessionStore.forgetContainerRestoreData(id);
  await flushIdentities();
}
export function nativeBackupAvailability() {
  try {
    const { BackupService } = ChromeUtils.importESModule('resource:///modules/backup/BackupService.sys.mjs');
    const service = BackupService.init();
    return { available: service.archiveEnabledStatus.enabled || service.restoreEnabledStatus.enabled,
      reason: service.archiveEnabledStatus.reason || service.restoreEnabledStatus.reason || '' };
  } catch (error) { return { available: false, reason: 'Native backup service is unavailable in this build' }; }
}
