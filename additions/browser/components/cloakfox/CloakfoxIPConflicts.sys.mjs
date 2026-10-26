/* MPL-2.0. Route-scoped, opt-in public-IP comparison. Local, bounded IP history; private windows excluded. */
const records = new Map(), pending = new Map();
const TTL = 5 * 60 * 1000;
const CHECK_ROUTE_PREF = 'cloakfox.ip_conflicts.check_route';
let routeGeneration = 0;
const activeProbes = new Set();
export function getIPCheckRoute() {
  return Services.prefs.getStringPref(CHECK_ROUTE_PREF, 'background') === 'tab' ? 'tab' : 'background';
}
export function setIPCheckRoute(mode) {
  if (!['tab', 'background'].includes(mode)) throw new Error('Invalid IP check route');
  if (mode === getIPCheckRoute()) return;
  Services.prefs.setStringPref(CHECK_ROUTE_PREF, mode);
  Services.prefs.savePrefFile(null);
  clearIPCheckCache();
}

export function clearIPCheckCache() {
  ++routeGeneration;
  records.clear();
  pending.clear();
  warningContexts.clear();
  for (const cancel of [...activeProbes]) cancel();
  Services.obs.notifyObservers(null, 'cloakfox-ip-conflicts-updated');
}
export function normalizeObservedIP(value) {
  if (typeof value !== 'string' || value.length > 64) throw new Error('Invalid IP response');
  const ip = value.trim();
  if (/^(?:\d{1,3}\.){3}\d{1,3}$/.test(ip)) {
    if (ip.split('.').some(part => Number(part) > 255)) throw new Error('Invalid IPv4');
    return ip.split('.').map(Number).join('.');
  }
  if (!/^[0-9a-f:]+$/i.test(ip) || !ip.includes(':')) throw new Error('Invalid IP response');
  return new URL(`http://[${ip}]/`).hostname.slice(1,-1);
}
function observedAddresses(record) {
  const addresses = {ipv4:record?.ipv4 || null,ipv6:record?.ipv6 || null};
  // Old callers and cached records expose only the single-address alias.
  if (record?.ip && !('ipv4' in record) && !('ipv6' in record)) {
    addresses[record.ip.includes(':') ? 'ipv6' : 'ipv4'] = record.ip;
  }
  return addresses;
}
export function matchingIPRecords(current, others, now = Date.now()) {
  if (!current || current.expires <= now) return [];
  const addresses = Object.values(observedAddresses(current)).filter(Boolean);
  return others.filter(other => other.ucid !== current.ucid && other.expires > now &&
    Object.values(observedAddresses(other)).some(ip => ip && addresses.includes(ip)));
}
function validateId(id) {
  if (!Number.isInteger(id) || id < 0 || id > 0x7fffffff) throw new Error('Invalid container');
}
function routeKey(id) {
  const prefixes = [`cloakfox.container.${id}.`, 'network.proxy.'];
  const keys = prefixes.flatMap(prefix => Services.prefs.getChildList(prefix)).filter(key =>
    key.startsWith('network.proxy.') || /\.(network_mode|proxy_url|proxy_ref|proxy_revision|network_epoch)$/.test(key)).sort();
  return getIPCheckRoute() + JSON.stringify(keys.map(key => {
    const type = Services.prefs.getPrefType(key);
    return [key,type === 128 ? Services.prefs.getBoolPref(key) : type === 64 ? Services.prefs.getIntPref(key) : Services.prefs.getStringPref(key)];
  }));
}
export function ipConflictResults() {
  const now = Date.now();
  for (const [id,record] of records) if (record.expires <= now || record.route !== routeKey(id)) records.delete(id);
  const fresh = [...records.values()];
  return fresh.map(record => {
    const matches = Object.entries(observedAddresses(record)).flatMap(([family,ip]) => {
      const conflicts = ip ? fresh.filter(other => other.ucid !== record.ucid &&
        observedAddresses(other)[family] === ip).map(other=>other.ucid) : [];
      return conflicts.length ? [{ip,family,conflicts}] : [];
    });
    return {ucid:record.ucid,ip:record.ip,ipv4:record.ipv4,ipv6:record.ipv6,errors:record.errors,checkedAt:record.checkedAt,error:record.error,
      matches,conflicts:[...new Set(matches.flatMap(match=>match.conflicts))]};
  });
}
export function allowSharedIP(id, allowed) {
  validateId(id);
  if (typeof allowed !== 'boolean') throw new Error('Invalid exception');
  Services.prefs.setBoolPref(`cloakfox.container.${id}.allow_shared_ip`,allowed);
  Services.prefs.savePrefFile(null);
}
export async function checkContainerIP(id, {force=false} = {}) {
  validateId(id); ipConflictResults();
  if (pending.has(id)) return pending.get(id);
  if (!force && records.has(id)) return records.get(id);
  const route = routeKey(id);
  const generation = routeGeneration;
  const mode = getIPCheckRoute();
  const task = measure(id, mode, generation).then(result => {
    const record = {ucid:id,...result,lookupRoute:mode,route,checkedAt:Date.now(),expires:Date.now()+(result.ip?TTL:30000)};
    if (generation !== routeGeneration || route !== routeKey(id)) {
      record.ip=record.ipv4=record.ipv6=null;
      record.error='Route changed during check. Check again.';
      record.errors={ipv4:record.error,ipv6:record.error};
      record.expires=Date.now()+30000;
    }
    if (generation !== routeGeneration) return record;
    records.set(id,record);
    Services.obs.notifyObservers(null,'cloakfox-ip-conflicts-updated');
    return record;
  }).finally(()=>{ if (pending.get(id) === task) pending.delete(id); });
  pending.set(id,task);return task;
}
async function measure(id, mode, generation) {
  const families = await Promise.all([
    measureFamily(id,'ipv4',['https://api.ipify.org?format=json','https://httpbin.org/ip'],mode,generation),
    measureFamily(id,'ipv6',['https://api6.ipify.org?format=json','https://api64.ipify.org?format=json'],mode,generation),
  ]);
  const [v4,v6]=families;
  return {ip:v4.ip || v6.ip,ipv4:v4.ip,ipv6:v6.ip,errors:{ipv4:v4.error,ipv6:v6.error},
    ...(!v4.ip && !v6.ip ? {error:'IP check failed or route unavailable. Result unknown.'} : {})};
}
async function measureFamily(id,family,endpoints,mode,generation) {
  let detail = '';
  for (const endpoint of endpoints) {
    try {
      const ip = await measureEndpoint(id,endpoint,mode,generation);
      if ((ip.includes(':') ? 'ipv6' : 'ipv4') === family) return {ip,error:null};
    } catch(error) { detail = error.message; }
  }
  return {ip:null,error:`${family === 'ipv4' ? 'IPv4' : 'IPv6'} check failed or route unavailable. Result unknown.${detail ? ' ' + detail : ''}`};
}
async function measureEndpoint(id, endpoint, mode, generation) {
  if (generation !== routeGeneration) throw new Error('Route changed during check');
  const {getContainerNetwork} = ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkPolicy.sys.mjs');
  if (getContainerNetwork(id).mode === 2) throw new Error('Blocked route');
  if (mode === 'tab') return measureTabEndpoint(id, endpoint);
  const {NetUtil} = ChromeUtils.importESModule('resource://gre/modules/NetUtil.sys.mjs');
  const {setTimeout,clearTimeout} = ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');
  const uri = Services.io.newURI(endpoint);
  // A content principal with origin attributes is essential: a system principal
  // bypasses container routing. Never replace this with background fetch.
  const principal = Services.scriptSecurityManager.createContentPrincipal(uri,{userContextId:id});
  const channel = NetUtil.newChannel({uri,loadingPrincipal:principal,
    securityFlags:Ci.nsILoadInfo.SEC_ALLOW_CROSS_ORIGIN_SEC_CONTEXT_IS_NULL,contentPolicyType:Ci.nsIContentPolicy.TYPE_OTHER});
  channel.loadFlags |= Ci.nsIRequest.LOAD_ANONYMOUS | Ci.nsIRequest.LOAD_BYPASS_CACHE | Ci.nsIRequest.INHIBIT_CACHING;
  channel.QueryInterface(Ci.nsIHttpChannel).redirectionLimit = 0;
  return new Promise((resolve,reject) => {
    let body='';
    const cancel=()=>channel.cancel(Cr.NS_ERROR_NET_TIMEOUT);
    activeProbes.add(cancel);
    const timer=setTimeout(cancel,10000);
    try { channel.asyncOpen({onStartRequest(){},onDataAvailable(_request,stream,_offset,count){
      if (body.length+count>4096) {channel.cancel(Cr.NS_ERROR_FILE_TOO_BIG);return;}
      body+=NetUtil.readInputStreamToString(stream,count);
    },onStopRequest(_request,status){
      clearTimeout(timer);
      activeProbes.delete(cancel);
      try {
        if (!Components.isSuccessCode(status) || channel.QueryInterface(Ci.nsIHttpChannel).responseStatus!==200) throw new Error('Lookup failed');
        resolve(normalizeObservedIP((JSON.parse(body).ip || JSON.parse(body).origin?.split(',')[0]?.trim())));
      } catch(error) {reject(error);}
    }}); } catch(error) {clearTimeout(timer);activeProbes.delete(cancel);reject(error);}
  });
}
let started=false;
export function initIPConflicts() {
  if (started) return;started=true;
  ipHistory();
  const attach = win => {
    if (!win.gBrowser || win.__cloakfoxIPMonitor) return;
    const listener={onLocationChange(browser,progress,_request,uri){
      if (browser.__cloakfoxIPProbe || !progress.isTopLevel || !/^https?:$/.test(uri?.scheme+':') ||
          !Services.prefs.getBoolPref('cloakfox.ip_conflicts.enabled',false)) return;
      const attrs=browser.contentPrincipal?.originAttributes;
      if (!attrs || attrs.privateBrowsingId) return;
      const id=attrs.userContextId||0;
      const url = uri.spec;
      if (!shouldCheckWebsite(id,url) || hasTemporaryIPAllowance(id)) return;
      checkContainerIP(id).then(async()=>{
        if (!browser.isConnected || !Services.prefs.getBoolPref('cloakfox.ip_conflicts.enabled',false) ||
            browser.contentPrincipal?.originAttributes.userContextId!==id) return;
        if (browser.currentURI.spec !== url || !shouldCheckWebsite(id,url) || hasTemporaryIPAllowance(id)) return;
        const result=ipConflictResults().find(row=>row.ucid===id);
        if (!result?.ip) return;
        const matches=warningMatches(id,result,url);
        if (!matches.length ||
            Services.prefs.getBoolPref(`cloakfox.container.${id}.allow_shared_ip`,false)) { recordAddresses(result,id,url); return; }
        if (Services.prefs.getStringPref('cloakfox.ip_conflicts.response','warning') === 'warning') {
          showIPWarning(browser,id,url,result); return;
        }
        const box=win.gBrowser.getNotificationBox(browser);
        if (box.getNotificationWithValue('cloakfox-ip-conflict')) return;
        await box.appendNotification('cloakfox-ip-conflict',{
          label:'Your public IP lookup matches a result recorded for another container visiting this hostname. This does not confirm the IP seen by this website; proxy rules and IPv4/IPv6 routing can differ.',
          priority:box.PRIORITY_WARNING_MEDIUM,
        },[{label:'Review IP conflicts',callback(){win.openTrustedLinkIn(`about:cloakfox?ucid=${id}#cfx-ip-conflict-panel`,'tab');}},
          {label:'Allow sharing for this container',callback(){allowSharedIP(id,true);}}]);
        recordAddresses(result,id,url);
      }).catch(Cu.reportError);
    }};
    win.__cloakfoxIPMonitor=listener;win.gBrowser.addTabsProgressListener(listener);
    win.addEventListener('unload',()=>win.gBrowser?.removeTabsProgressListener(listener),{once:true});
  };
  for (const win of Services.wm.getEnumerator('navigator:browser')) attach(win);
  Services.obs.addObserver({observe(win){attach(win);}},'browser-delayed-startup-finished');
}

const temporaryAllows = new Map();
const HISTORY_PREF = 'cloakfox.ip_conflicts.history';
function readJSON(key, fallback) {
  try { return JSON.parse(Services.prefs.getStringPref(key, JSON.stringify(fallback))); } catch { return fallback; }
}
function writeJSON(key, value) {
  Services.prefs.setStringPref(key, JSON.stringify(value));
  Services.prefs.savePrefFile(null);
  Services.obs.notifyObservers(null, 'cloakfox-ip-conflicts-updated');
}
export function normalizeDomain(value) {
  const text = String(value).trim().toLowerCase().replace(/\.$/, '');
  if (!text || /[\s/:?#@*]/.test(text)) throw new Error('Enter a hostname such as example.com, without a URL, path or wildcard.');
  const host = new URL('https://' + text).hostname;
  if (host.length > 253 || host.split('.').some(part => !/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(part))) throw new Error('Invalid hostname');
  return host;
}
export function websiteMatches(url, domains) {
  try { const u = new URL(url); return /^https?:$/.test(u.protocol) && domains.some(d => u.hostname === d || u.hostname.endsWith('.' + d)); } catch { return false; }
}
export function getIPRules(id = null) {
  const fallback = {mode:'all',include:[],exclude:[]};
  const global = readJSON('cloakfox.ip_conflicts.rules', fallback);
  return id === null ? global : readJSON(`cloakfox.container.${id}.ip_rules`, global);
}
export function setIPRules(rules, id = null) {
  if (id !== null) validateId(id);
  if (!['all','selected'].includes(rules.mode)) throw new Error('Invalid website checking mode');
  const normalize = values => [...new Set(values.map(normalizeDomain))].slice(0,200);
  writeJSON(id === null ? 'cloakfox.ip_conflicts.rules' : `cloakfox.container.${id}.ip_rules`, {mode:rules.mode,include:normalize(rules.include),exclude:normalize(rules.exclude)});
}
export function resetIPRules(id) { validateId(id); Services.prefs.clearUserPref(`cloakfox.container.${id}.ip_rules`); Services.prefs.savePrefFile(null); }
export function shouldCheckWebsite(id, url) {
  const rules = getIPRules(id);
  return /^https?:\/\//i.test(url) && !websiteMatches(url,rules.exclude) && (rules.mode === 'all' || websiteMatches(url,rules.include));
}
export function allowIPOnce(id, now = Date.now()) { validateId(id); temporaryAllows.set(id, now + 30000); }
export function hasTemporaryIPAllowance(id, now = Date.now()) { return (temporaryAllows.get(id) || 0) > now; }
export function ipExceptions() { return readJSON('cloakfox.ip_conflicts.exceptions', []); }
export function setIPException(ip, allowed) {
  ip = normalizeObservedIP(ip);
  writeJSON('cloakfox.ip_conflicts.exceptions', allowed ? [...new Set([...ipExceptions(),ip])] : ipExceptions().filter(value => value !== ip));
}
export function ipHistory() {
  const cutoff = Date.now() - 30 * 86400000;
  const stored = readJSON(HISTORY_PREF, []);
  const rows = stored.filter(row => row.lastAccessed > cutoff).slice(0,500);
  if (rows.length !== stored.length) { Services.prefs.setStringPref(HISTORY_PREF,JSON.stringify(rows)); Services.prefs.savePrefFile(null); }
  return rows;
}
function visitedHostname(url) {
  try {
    const uri = new URL(url);
    return /^https?:$/.test(uri.protocol) ? uri.hostname.toLowerCase().replace(/\.$/, '') : '';
  } catch { return ''; }
}
export function recordIPAccess(ip, id, url = '') {
  ip = normalizeObservedIP(ip); validateId(id);
  const hostname = visitedHostname(url);
  if (!hostname) return;
  const rows = ipHistory();
  const lookupRoute = getIPCheckRoute();
  const matches = row => row.ip === ip && row.ucid === id && row.hostname === hostname &&
    (row.lookupRoute || 'background') === lookupRoute;
  const old = rows.find(matches);
  let safeURL = '';
  try { const u = new URL(url); if (/^https?:$/.test(u.protocol)) { u.username='';u.password='';u.search='';u.hash='';safeURL=u.href.slice(0,2048); } } catch {}
  const now = Date.now();
  const row = {ip,ucid:id,hostname,lookupRoute,firstAccessed:old?.firstAccessed || now,lastAccessed:now,accessCount:(old?.accessCount || 0)+1,
    urls:[...(safeURL ? [safeURL] : []),...(old?.urls || [])].slice(0,10)};
  writeJSON(HISTORY_PREF, [row,...rows.filter(value => !matches(value))].slice(0,500));
}
export function clearIPHistory(ip = null, id = null, hostname = null) {
  writeJSON(HISTORY_PREF, ip === null ? [] : ipHistory().filter(row => row.ip !== normalizeObservedIP(ip) ||
    (id !== null && row.ucid !== id) || (hostname !== null && (row.hostname ?? '') !== hostname)));
  for (const [id,row] of records) if (ip === null || Object.values(observedAddresses(row)).includes(normalizeObservedIP(ip))) records.delete(id);
  Services.obs.notifyObservers(null,'cloakfox-ip-conflicts-updated');
}
export function reassignIP(ip,id,fromId = null,hostname = null) {
  validateId(id);ip=normalizeObservedIP(ip);
  writeJSON(HISTORY_PREF,ipHistory().map(row => row.ip === ip &&
    (fromId === null || row.ucid === fromId) && (hostname === null || (row.hostname ?? '') === hostname) ? {...row,ucid:id} : row));
}
export function conflictForIP(id, ip, url = '') {
  const hostname = visitedHostname(url);
  if (!ip || !hostname) return [];
  return [...new Set(ipHistory().filter(row => row.ucid !== id && row.ip === ip &&
    row.hostname === hostname && (row.lookupRoute || 'background') === getIPCheckRoute()).map(row => row.ucid))];
}
function recordAddresses(result,id,url) {
  for (const ip of Object.values(observedAddresses(result)).filter(Boolean)) recordIPAccess(ip,id,url);
}
function warningMatches(id,result,url) {
  const exceptions = ipExceptions();
  return Object.entries(observedAddresses(result)).flatMap(([family,ip]) => {
    const conflicts = ip && !exceptions.includes(ip) ? conflictForIP(id,ip,url) : [];
    return conflicts.length ? [{ip,family,conflicts}] : [];
  });
}
const warningContexts = new Map();
export function getIPWarning(token) {
  const context = warningContexts.get(token);
  if (!context || !context.browser.isConnected || Date.now() - context.created > 3600000) return null;
  const matches = warningMatches(context.id,context.result,context.url);
  return {id:context.id,url:context.url,ip:context.result.ip,...observedAddresses(context.result),
    errors:context.result.errors,matches,conflicts:[...new Set(matches.flatMap(match=>match.conflicts))]};
}
export async function resolveIPWarning(token, action) {
  const context = warningContexts.get(token);
  if (!getIPWarning(token) || context.browser.currentURI.spec !== 'chrome://browser/content/cloakfox/ip-warning.html?token='+token) throw new Error('This warning has expired. Return to the website to check again.');
  if (action === 'recheck') {
    const result = await checkContainerIP(context.id,{force:true});
    if (context.browser.currentURI.spec !== 'chrome://browser/content/cloakfox/ip-warning.html?token='+token) throw new Error('The tab has navigated away.');
    context.result = result;
    const warning = getIPWarning(token);
    for (const match of warning.matches) context.requiredFamilies.add(match.family);
    // A successful other-family lookup cannot establish that the original conflict disappeared.
    if (!result.ip || [...context.requiredFamilies].some(family=>!result[family])) {
      return {...warning,error:result.error || 'A previously conflicting IP family could not be checked. Result unknown.'};
    }
    if (warning.matches.length) return {...warning,conflict:true};
  } else if (action === 'once') allowIPOnce(context.id);
  else if (action === 'container') allowSharedIP(context.id,true);
  else if (action === 'website') {
    const rules = getIPRules(context.id);
    if (!websiteMatches(context.url,rules.exclude)) {
      if (rules.exclude.length >= 200) throw new Error('Website exclusion limit reached. Manage IP rules to remove an exclusion first.');
      const hostname = normalizeDomain(new URL(context.url).hostname);
      setIPRules({...rules,exclude:[...rules.exclude,hostname]},context.id);
    }
  }
  else if (action === 'ip') {
    const matches = getIPWarning(token).matches;
    if (!matches.length) throw new Error('No currently matching IP addresses are known. Recheck or choose Continue once.');
    for (const match of matches) setIPException(match.ip,true);
  } else throw new Error('Unknown warning action');
  recordAddresses(context.result,context.id,context.url);
  const uri = Services.io.newURI(context.url);
  warningContexts.delete(token);
  context.browser.loadURI(uri,{triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
  return {continued:true};
}
function showIPWarning(browser,id,url,result) {
  for (const [token,c] of warningContexts) if (!c.browser.isConnected || c.browser === browser || Date.now()-c.created>3600000) warningContexts.delete(token);
  const token=Services.uuid.generateUUID().toString().replace(/[{}]/g,'');
  warningContexts.set(token,{browser,id,url,result,requiredFamilies:new Set(warningMatches(id,result,url).map(match=>match.family)),created:Date.now()});
  browser.loadURI(Services.io.newURI('chrome://browser/content/cloakfox/ip-warning.html?token='+token),{triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
}

let ipProbeActorRegistered = false;
function measureTabEndpoint(id, endpoint) {
  endpoint = new URL(endpoint).href;
  const {PrivateBrowsingUtils} = ChromeUtils.importESModule('resource://gre/modules/PrivateBrowsingUtils.sys.mjs');
  const win = [...Services.wm.getEnumerator('navigator:browser')].find(w =>
    w.gBrowser && !w.closed && !PrivateBrowsingUtils.isWindowPrivate(w));
  if (!win) throw new Error('No regular browser window available for a tab-route check');
  if (!ipProbeActorRegistered) {
    ChromeUtils.registerWindowActor('CloakfoxIPProbe', {
      safeForUntrustedWebProcess:true,
      child: {esModuleURI:'resource:///actors/CloakfoxIPProbeChild.sys.mjs'},
      matches:['https://api.ipify.org/*','https://api6.ipify.org/*',
        'https://api64.ipify.org/*','https://httpbin.org/ip'],
      allFrames:false,
    });
    ipProbeActorRegistered = true;
  }
  const {setTimeout,clearTimeout} = ChromeUtils.importESModule('resource://gre/modules/Timer.sys.mjs');
  const tab = win.gBrowser.addTab('about:blank', {
    userContextId:id, triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal(),
    skipAnimation:true, skipBackgroundNotify:true,
  });
  const browser = tab.linkedBrowser;
  // Prevent recursive checks, visit history and warnings on diagnostic tabs.
  browser.__cloakfoxIPProbe = true;
  return new Promise((resolve,reject) => {
    let settled = false, reading = false, timer;
    const finish = (error, ip) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      activeProbes.delete(cancel);
      try { browser.removeProgressListener(listener); } catch {}
      win.removeEventListener?.('TabClose', onClose, true);
      if (!tab.closing) win.gBrowser.removeTab(tab, {animate:false,skipPermitUnload:true});
      error ? reject(error) : resolve(ip);
    };
    const cancel = () => finish(new Error('Route changed during check'));
    const onClose = event => { if (event.target === tab) finish(new Error('IP check tab closed')); };
    const listener = {
      QueryInterface: ChromeUtils.generateQI(["nsIWebProgressListener", "nsISupportsWeakReference"]),
      onStateChange(progress, _request, flags, status) {
      if (!progress.isTopLevel || !(flags & Ci.nsIWebProgressListener.STATE_STOP) ||
          !(flags & Ci.nsIWebProgressListener.STATE_IS_WINDOW) || reading || settled ||
          browser.currentURI.spec === 'about:blank') return;
      let requestURL;
      try { requestURL = _request?.QueryInterface(Ci.nsIChannel).URI.spec; } catch {}
      if (requestURL && requestURL !== endpoint) return;
      reading = true;
      if (!Components.isSuccessCode(status) || browser.currentURI.spec !== endpoint) {
        finish(new Error(`Tab lookup failed or redirected (${status}; ${browser.currentURI.spec}). Result unknown.`));
        return;
      }
      try {
        browser.browsingContext.currentWindowGlobal.getActor('CloakfoxIPProbe')
          .sendQuery('ReadIPResponse').then(response => {
            if (response.url !== endpoint) throw new Error('IP check navigated away');
            const parsed = JSON.parse(response.body);
            finish(null, normalizeObservedIP(parsed.ip || parsed.origin?.split(',')[0]?.trim()));
          }).catch(error => finish(error));
      } catch(error) { finish(error); }
    }};
    activeProbes.add(cancel);
    win.addEventListener('TabClose', onClose, true);
    timer = setTimeout(() => finish(new Error('Tab IP lookup timed out')), 10000);
    try {
      win.gBrowser.hideTab(tab);
      if (!tab.hidden) throw new Error('Could not hide IP check tab');
      browser.addProgressListener(listener, Ci.nsIWebProgress.NOTIFY_STATE_WINDOW);
      browser.loadURI(Services.io.newURI(endpoint), {
      triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal(),
      loadFlags:Ci.nsIWebNavigation.LOAD_FLAGS_BYPASS_CACHE,
    }); } catch(error) { finish(error); }
  });
}
