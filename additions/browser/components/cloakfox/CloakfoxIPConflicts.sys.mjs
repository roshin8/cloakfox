/* MPL-2.0. Route-scoped, opt-in public-IP comparison. Local, bounded IP history; private windows excluded. */
const records = new Map(), pending = new Map();
const TTL = 5 * 60 * 1000;
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
export function matchingIPRecords(current, others, now = Date.now()) {
  if (!current?.ip || current.expires <= now) return [];
  return others.filter(other => other.ucid !== current.ucid && other.ip === current.ip && other.expires > now);
}
function validateId(id) {
  if (!Number.isInteger(id) || id < 0 || id > 0x7fffffff) throw new Error('Invalid container');
}
function routeKey(id) {
  const prefixes = [`cloakfox.container.${id}.`, 'network.proxy.'];
  const keys = prefixes.flatMap(prefix => Services.prefs.getChildList(prefix)).filter(key =>
    key.startsWith('network.proxy.') || /\.(network_mode|proxy_url|proxy_ref|proxy_revision|network_epoch)$/.test(key)).sort();
  return JSON.stringify(keys.map(key => {
    const type = Services.prefs.getPrefType(key);
    return [key,type === 128 ? Services.prefs.getBoolPref(key) : type === 64 ? Services.prefs.getIntPref(key) : Services.prefs.getStringPref(key)];
  }));
}
export function ipConflictResults() {
  const now = Date.now();
  for (const [id,record] of records) if (record.expires <= now || record.route !== routeKey(id)) records.delete(id);
  return [...records.values()].map(record => ({ucid:record.ucid,ip:record.ip,checkedAt:record.checkedAt,error:record.error,
    conflicts:matchingIPRecords(record,[...records.values()],now).map(other=>other.ucid)}));
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
  const task = measure(id).then(ip => ({ip}), () => ({ip:null,error:'IP check failed or route unavailable. Result unknown.'})).then(result => {
    const record = {ucid:id,...result,route,checkedAt:Date.now(),expires:Date.now()+(result.ip?TTL:30000)};
    if (route !== routeKey(id)) { record.ip=null;record.error='Route changed during check. Check again.'; }
    records.set(id,record);
    Services.obs.notifyObservers(null,'cloakfox-ip-conflicts-updated');
    return record;
  }).finally(()=>pending.delete(id));
  pending.set(id,task);return task;
}
async function measure(id) {
  try { return await measureEndpoint(id,'https://api64.ipify.org?format=json'); }
  catch { return measureEndpoint(id,'https://httpbin.org/ip'); }
}
async function measureEndpoint(id, endpoint) {
  const {getContainerNetwork} = ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkPolicy.sys.mjs');
  if (getContainerNetwork(id).mode === 2) throw new Error('Blocked route');
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
    const timer=setTimeout(()=>channel.cancel(Cr.NS_ERROR_NET_TIMEOUT),10000);
    try { channel.asyncOpen({onStartRequest(){},onDataAvailable(_request,stream,_offset,count){
      if (body.length+count>4096) {channel.cancel(Cr.NS_ERROR_FILE_TOO_BIG);return;}
      body+=NetUtil.readInputStreamToString(stream,count);
    },onStopRequest(_request,status){
      clearTimeout(timer);
      try {
        if (!Components.isSuccessCode(status) || channel.QueryInterface(Ci.nsIHttpChannel).responseStatus!==200) throw new Error('Lookup failed');
        resolve(normalizeObservedIP((JSON.parse(body).ip || JSON.parse(body).origin?.split(',')[0]?.trim())));
      } catch(error) {reject(error);}
    }}); } catch(error) {clearTimeout(timer);reject(error);}
  });
}
let started=false;
export function initIPConflicts() {
  if (started) return;started=true;
  ipHistory();
  const attach = win => {
    if (!win.gBrowser || win.__cloakfoxIPMonitor) return;
    const listener={onLocationChange(browser,progress,_request,uri){
      if (!progress.isTopLevel || !/^https?:$/.test(uri?.scheme+':') ||
          !Services.prefs.getBoolPref('cloakfox.ip_conflicts.enabled',false)) return;
      const attrs=browser.contentPrincipal?.originAttributes;
      if (!attrs || attrs.privateBrowsingId) return;
      const id=attrs.userContextId||0;
      const url = uri.spec;
      if (!shouldCheckWebsite(id,url) || hasTemporaryIPAllowance(id)) return;
      checkContainerIP(id).then(async()=>{
        if (!browser.isConnected || !Services.prefs.getBoolPref('cloakfox.ip_conflicts.enabled',false) ||
            browser.contentPrincipal?.originAttributes.userContextId!==id ||
            Services.prefs.getBoolPref(`cloakfox.container.${id}.allow_shared_ip`,false)) return;
        if (browser.currentURI.spec !== url || !shouldCheckWebsite(id,url) || hasTemporaryIPAllowance(id)) return;
        const result=ipConflictResults().find(row=>row.ucid===id);
        if (!result?.ip) return;
        const conflicts=conflictForIP(id,result.ip);
        if (!conflicts.length || ipExceptions().includes(result.ip)) { recordIPAccess(result.ip,id,url); return; }
        if (Services.prefs.getStringPref('cloakfox.ip_conflicts.response','warning') === 'warning') {
          showIPWarning(browser,id,url,result.ip); return;
        }
        const box=win.gBrowser.getNotificationBox(browser);
        if (box.getNotificationWithValue('cloakfox-ip-conflict')) return;
        await box.appendNotification('cloakfox-ip-conflict',{
          label:'This container shares its measured public IP with another container. Websites may link these sessions.',
          priority:box.PRIORITY_WARNING_MEDIUM,
        },[{label:'Review IP conflicts',callback(){win.openTrustedLinkIn(`about:cloakfox?ucid=${id}#cfx-ip-conflict-panel`,'tab');}},
          {label:'Allow sharing for this container',callback(){allowSharedIP(id,true);}}]);
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
export function recordIPAccess(ip, id, url = '') {
  ip = normalizeObservedIP(ip); validateId(id);
  const rows = ipHistory(), old = rows.find(row => row.ip === ip);
  // A conflicting observation must not silently transfer ownership.
  if (old && old.ucid !== id) return;
  let safeURL = '';
  try { const u = new URL(url); if (/^https?:$/.test(u.protocol)) { u.username='';u.password='';u.search='';u.hash='';safeURL=u.href.slice(0,2048); } } catch {}
  const now = Date.now();
  const row = {ip,ucid:id,firstAccessed:old?.firstAccessed || now,lastAccessed:now,accessCount:(old?.accessCount || 0)+1,
    urls:[...(safeURL ? [safeURL] : []),...(old?.urls || [])].slice(0,10)};
  writeJSON(HISTORY_PREF, [row,...rows.filter(value => value.ip !== ip)].slice(0,500));
}
export function clearIPHistory(ip = null) {
  writeJSON(HISTORY_PREF, ip === null ? [] : ipHistory().filter(row => row.ip !== normalizeObservedIP(ip)));
  for (const [id,row] of records) if (ip === null || row.ip === ip) records.delete(id);
  Services.obs.notifyObservers(null,'cloakfox-ip-conflicts-updated');
}
export function reassignIP(ip,id) {
  validateId(id);ip=normalizeObservedIP(ip);
  writeJSON(HISTORY_PREF,ipHistory().map(row => row.ip === ip ? {...row,ucid:id} : row));
}
export function conflictForIP(id, ip) {
  if (!ip) return [];
  const recent = ipConflictResults().filter(row => row.ucid !== id && row.ip === ip).map(row => row.ucid);
  const history = ipHistory().filter(row => row.ucid !== id && row.ip === ip).map(row => row.ucid);
  return [...new Set([...recent,...history])];
}
const warningContexts = new Map();
export function getIPWarning(token) {
  const context = warningContexts.get(token);
  if (!context || !context.browser.isConnected || Date.now() - context.created > 3600000) return null;
  return {id:context.id,url:context.url,ip:context.ip,conflicts:conflictForIP(context.id,context.ip)};
}
export async function resolveIPWarning(token, action) {
  const context = warningContexts.get(token);
  if (!getIPWarning(token) || context.browser.currentURI.spec !== 'chrome://browser/content/cloakfox/ip-warning.html?token='+token) throw new Error('This warning has expired. Return to the website to check again.');
  if (action === 'recheck') {
    const result = await checkContainerIP(context.id,{force:true});
    if (context.browser.currentURI.spec !== 'chrome://browser/content/cloakfox/ip-warning.html?token='+token) throw new Error('The tab has navigated away.');
    if (!result.ip) return {error:result.error};
    context.ip = result.ip;
    if (conflictForIP(context.id,result.ip).length && !ipExceptions().includes(result.ip)) return {conflict:true,ip:result.ip};
  } else if (action === 'once') allowIPOnce(context.id);
  else if (action === 'container') allowSharedIP(context.id,true);
  else if (action === 'ip') setIPException(context.ip,true);
  else throw new Error('Unknown warning action');
  recordIPAccess(context.ip,context.id,context.url);
  const uri = Services.io.newURI(context.url);
  warningContexts.delete(token);
  context.browser.loadURI(uri,{triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
  return {continued:true};
}
function showIPWarning(browser,id,url,ip) {
  for (const [token,c] of warningContexts) if (!c.browser.isConnected || c.browser === browser || Date.now()-c.created>3600000) warningContexts.delete(token);
  const token=Services.uuid.generateUUID().toString().replace(/[{}]/g,'');
  warningContexts.set(token,{browser,id,url,ip,created:Date.now()});
  browser.loadURI(Services.io.newURI('chrome://browser/content/cloakfox/ip-warning.html?token='+token),{triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
}
