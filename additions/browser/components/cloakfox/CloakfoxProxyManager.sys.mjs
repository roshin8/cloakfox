/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// Parent-process only. The catalog contains references, never login material.
const CATALOG = 'cloakfox.proxy.catalog.v1';
const CONTAINERS = 'cloakfox.container.';
const REALM = 'Cloakfox named proxy';
const pending = new Set();
const network = () => ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkPolicy.sys.mjs');
const freshID = () => Services.uuid.generateUUID().toString().replace(/[{}]/g, '');
// Rust LoginManager storage normalizes away URL paths. Give each catalog
// entry a distinct origin, rather than putting the ID into a shared origin path.
const loginOrigin = id => `chrome://cloakfox-proxy-${id}`;
function validateContainer(ucid) {
  if (!Number.isInteger(ucid) || ucid < 0 || ucid > 0x7fffffff) throw new Error('Invalid container ID');
}
export function listProxies() {
  const data = JSON.parse(Services.prefs.getStringPref(CATALOG, '[]'));
  if (!Array.isArray(data) || data.length > 500) throw new Error('Invalid proxy catalog');
  return data.map(p => {
    if (!p || !/^[a-f0-9-]{36}$/.test(p.id) || typeof p.name !== 'string' ||
        !/^[a-f0-9-]{36}$/.test(p.revision) || typeof p.hasCredentials !== 'boolean') {
      throw new Error('Invalid proxy catalog entry');
    }
    return {id:p.id, name:p.name, url:network().normalizeProxyURL(p.url),
      revision:p.revision, hasCredentials:p.hasCredentials};
  });
}
function writeCatalog(entries) {
  Services.prefs.setStringPref(CATALOG, JSON.stringify(entries));
  Services.prefs.savePrefFile(null);
}
export function getProxyReference(ucid) {
  validateContainer(ucid);
  return Services.prefs.getStringPref(`${CONTAINERS}${ucid}.proxy_ref`, '') || null;
}
function boundContainers(id) {
  return Services.prefs.getChildList(CONTAINERS).filter(key => key.endsWith('.proxy_ref') &&
    Services.prefs.getStringPref(key, '') === id).map(key => Number(key.split('.')[2]));
}
export function bindProxy(ucid, id) {
  validateContainer(ucid);
  const entry = listProxies().find(p => p.id === id);
  if (!entry || pending.has(id)) throw new Error('Saved proxy is unavailable');
  const prefix = `${CONTAINERS}${ucid}.`;
  Services.prefs.setIntPref(prefix + 'network_mode', 2);
  Services.prefs.setStringPref(prefix + 'proxy_ref', id);
  Services.prefs.setStringPref(prefix + 'proxy_revision', entry.revision);
  // Keep the native required-proxy endpoint guard in sync with the reference.
  Services.prefs.setStringPref(prefix + 'proxy_url', entry.url);
  Services.prefs.setIntPref(prefix + 'network_mode', 1);
  Services.prefs.clearUserPref(`${CONTAINERS}${ucid}.proxy_last_check`);
  Services.prefs.savePrefFile(null);
}
async function savedLogin(id) {
  let entries;
  try { entries = await Services.logins.searchLoginsAsync({origin:loginOrigin(id), httpRealm:REALM}); }
  catch (_) { throw new Error('Proxy credentials are unavailable'); }
  if (entries.length > 1) throw new Error('Proxy credential store is ambiguous');
  return entries[0] || null;
}
export async function saveProxy({id, name, url, username, password, clearCredentials = false}) {
  name = String(name || '').trim();
  if (!name || name.length > 120) throw new Error('Enter a proxy name of up to 120 characters');
  url = network().normalizeProxyURL(url);
  const catalog = listProxies(), existing = id && catalog.find(p => p.id === id);
  if (id && !existing) throw new Error('Saved proxy is unavailable');
  id ||= freshID();
  if (pending.has(id)) throw new Error('Proxy update is already in progress');
  const changingCredentials = username !== undefined || password !== undefined;
  if (changingCredentials && (typeof username !== 'string' || typeof password !== 'string' ||
      !username || !password || /[:\r\n\0]/.test(username) || /[\r\n\0]/.test(password) ||
      new TextEncoder().encode(username).length > 255 || new TextEncoder().encode(password).length > 255)) {
    throw new Error('Enter both username and password (up to 255 bytes; username cannot contain a colon)');
  }
  const bindings = boundContainers(id);
  pending.add(id);
  // Keep bound routes blocked if storage or catalog updates fail.
  for (const ucid of bindings) Services.prefs.setIntPref(`${CONTAINERS}${ucid}.network_mode`, 2);
  try {
    let login = await savedLogin(id);
    if (clearCredentials) {
      if (login) await Services.logins.removeLoginAsync(login);
      login = null;
    } else if (changingCredentials) {
      const replacement = Cc['@mozilla.org/login-manager/loginInfo;1'].createInstance(Ci.nsILoginInfo);
      replacement.init(loginOrigin(id), null, REALM, username, password, '', '');
      if (login) await Services.logins.modifyLoginAsync(login, replacement);
      else await Services.logins.addLoginAsync(replacement);
      login = await savedLogin(id);
      if (!login || login.username !== username || login.password !== password) {
        throw new Error('Proxy credential persistence could not be verified');
      }
    }
    if (existing?.hasCredentials && !login && !clearCredentials) throw new Error('Proxy credentials are unavailable');
    const entry = {id,name,url,hasCredentials:!!login,revision:freshID()};
    // Re-read after async storage work so changes to another proxy are retained.
    writeCatalog([...listProxies().filter(p => p.id !== id),entry]);
    pending.delete(id);
    for (const ucid of bindings) if (getProxyReference(ucid) === id) bindProxy(ucid,id);
    return entry;
  } catch (_) {
    throw new Error('Could not save proxy; affected containers remain blocked');
  } finally { pending.delete(id); }
}
export async function removeProxy(id) {
  if (pending.has(id)) throw new Error('Proxy update is already in progress');
  if (!listProxies().some(p => p.id === id)) throw new Error('Saved proxy is unavailable');
  pending.add(id);
  try {
    for (const ucid of boundContainers(id)) {
      const prefix = `${CONTAINERS}${ucid}.`;
      Services.prefs.setIntPref(prefix + 'network_mode', 2);
      Services.prefs.clearUserPref(prefix + 'proxy_ref');
      Services.prefs.setStringPref(prefix + 'proxy_url', '');
      Services.prefs.clearUserPref(`${CONTAINERS}${ucid}.proxy_last_check`);
    }
    const login = await savedLogin(id);
    if (login) await Services.logins.removeLoginAsync(login);
    writeCatalog(listProxies().filter(p => p.id !== id));
  } catch (_) { throw new Error('Could not remove proxy; affected containers remain blocked'); }
  finally { pending.delete(id); }
}
// Internal privileged routing API. Never serialize its result to settings pages,
// exports, telemetry, or logs. Credentials are read per request, not cached here.
export async function resolveContainerProxy(ucid) {
  const id = getProxyReference(ucid), entry = listProxies().find(p => p.id === id);
  if (!entry || pending.has(id)) throw new Error('Saved proxy is unavailable');
  const login = entry.hasCredentials ? await savedLogin(id) : null;
  const current = listProxies().find(p => p.id === id), policy = network().getContainerNetwork(ucid);
  if (pending.has(id) || getProxyReference(ucid) !== id || current?.revision !== entry.revision ||
      policy.mode !== 1 || policy.proxyURL !== entry.url || (entry.hasCredentials && !login)) {
    throw new Error('Proxy route changed or credentials are unavailable');
  }
  return {...entry,username:login?.username || '',password:login?.password || ''};
}
function routeSignature(ucid) {
  const policy = network().getContainerNetwork(ucid);
  if (policy.mode !== 1) return null;
  return JSON.stringify([getProxyReference(ucid),policy.proxyURL,
    Services.prefs.getStringPref(`${CONTAINERS}${ucid}.proxy_revision`, '')]);
}
export function getProxyCheck(ucid) {
  validateContainer(ucid);
  try {
    const saved = JSON.parse(Services.prefs.getStringPref(`${CONTAINERS}${ucid}.proxy_last_check`, 'null'));
    return saved && saved.route === routeSignature(ucid) ? saved.result : null;
  } catch (_) { return null; }
}
// Explicit caller-selected HTTPS endpoint; never call this automatically. Uses a
// content principal with the target origin attributes, so native strict routing
// applies. Redirects and cookies are disabled; no provider response is persisted.
export async function testContainerProxy(ucid, endpoint) {
  validateContainer(ucid);
  const url = new URL(endpoint);
  if (url.protocol !== 'https:' || url.username || url.password || url.hash) {
    throw new Error('Choose an HTTPS diagnostic endpoint without credentials');
  }
  const policy = network().getContainerNetwork(ucid);
  if (policy.mode !== 1) throw new Error('Select a required proxy route before testing');
  if (getProxyReference(ucid)) await resolveContainerProxy(ucid);
  const {NetUtil} = ChromeUtils.importESModule('resource://gre/modules/NetUtil.sys.mjs');
  const uri = Services.io.newURI(url.href);
  const principal = Services.scriptSecurityManager.createContentPrincipal(uri, {userContextId:ucid});
  const channel = NetUtil.newChannel({uri,loadingPrincipal:principal,
    securityFlags:Ci.nsILoadInfo.SEC_ALLOW_CROSS_ORIGIN_SEC_CONTEXT_IS_NULL,
    contentPolicyType:Ci.nsIContentPolicy.TYPE_OTHER});
  channel.loadFlags |= Ci.nsIRequest.LOAD_BYPASS_CACHE | Ci.nsIRequest.INHIBIT_CACHING | Ci.nsIRequest.LOAD_ANONYMOUS;
  channel.QueryInterface(Ci.nsIHttpChannel).redirectionLimit = 0;
  const {setTimeout,clearTimeout} = ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');
  const started = Date.now(), reference = getProxyReference(ucid), signature = routeSignature(ucid);
  return new Promise(resolve => {
    const timer = setTimeout(() => channel.cancel(Cr.NS_ERROR_NET_TIMEOUT), 15000);
    let bytes = 0;
    const finish = status => {
      clearTimeout(timer);
      const current = network().getContainerNetwork(ucid);
      const unchanged = current.mode === 1 && current.proxyURL === policy.proxyURL && getProxyReference(ucid) === reference && routeSignature(ucid) === signature;
      let httpStatus = 0;
      try { httpStatus = channel.QueryInterface(Ci.nsIHttpChannel).responseStatus; } catch (_) {}
      const result = {checkedAt:new Date().toISOString(), ok:unchanged && Components.isSuccessCode(status) && httpStatus >= 200 && httpStatus < 300,
        elapsedMs:Date.now()-started, httpStatus, message:!unchanged ? 'Route changed during test' :
          Components.isSuccessCode(status) && httpStatus >= 200 && httpStatus < 300 ? 'HTTPS endpoint reached through required proxy' : 'Proxy connection, authentication, or endpoint failed'};
      if (unchanged) {
        Services.prefs.setStringPref(`${CONTAINERS}${ucid}.proxy_last_check`, JSON.stringify({route:signature,result}));
        Services.prefs.savePrefFile(null);
      }
      resolve(result);
    };
    try {
      channel.asyncOpen({onStartRequest(){},onDataAvailable(_request,stream,_offset,count){
        NetUtil.readInputStreamToString(stream,count);bytes += count;
        if (bytes > 65536) channel.cancel(Cr.NS_ERROR_FILE_TOO_BIG);
      },onStopRequest(_request,status){finish(status);}});
    } catch (_) {finish(Cr.NS_ERROR_FAILURE);}
  });
}
