/* MPL-2.0. Settings are separate from identity seeds. */
export const PRIVACY_PRESETS = ['standard', 'strict', 'compatibility'];
const VECTORS = ['geometry', 'canvas', 'audio'];
function id(value) {
  if (!Number.isInteger(value) || value < 0 || value > 0x7fffffff) throw new Error('Invalid container');
  return value;
}
function keys(value, allowed) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).some(k => !allowed.includes(k))) throw new Error('Invalid privacy policy');
}
export function normalizePolicySite(value) {
  if (typeof value !== 'string' || value.length > 300) throw new Error('Enter a schemeful site such as https://example.com');
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.port ||
      url.search || url.hash || url.pathname !== '/' || value !== url.origin) throw new Error('Use a site origin without a path, port or credentials');
  const host = Services.eTLD.getBaseDomainFromHost(url.hostname);
  if (host !== url.hostname) throw new Error(`Use the top-level site ${url.protocol}//${host}; this includes its subdomains`);
  return url.origin;
}
export function validatePrivacyPolicy(value) {
  keys(value, ['version','preset','exceptions']);
  if (value.version !== 1 || !PRIVACY_PRESETS.includes(value.preset) || !Array.isArray(value.exceptions) || value.exceptions.length > 100) throw new Error('Unsupported privacy policy');
  const sites = new Set();
  return {version:1,preset:value.preset,exceptions:value.exceptions.map(record => {
    keys(record,['site','vectors','expiresAt']);
    const site=normalizePolicySite(record.site);
    if (sites.has(site)) throw new Error('Duplicate site exception');
    sites.add(site);
    if (!Array.isArray(record.vectors) || !record.vectors.length || record.vectors.some(v=>!VECTORS.includes(v)) || new Set(record.vectors).size!==record.vectors.length ||
        !Number.isSafeInteger(record.expiresAt) || record.expiresAt <= 0) throw new Error('Invalid exception vectors or expiry');
    return {site,vectors:[...record.vectors],expiresAt:record.expiresAt};
  })};
}
export function getPrivacyPolicy(ucid) {
  const raw=Services.prefs.getStringPref(`cloakfox.container.${id(ucid)}.privacy_policy`, '');
  if (!raw) return {version:1,preset:'standard',exceptions:[]};
  return validatePrivacyPolicy(JSON.parse(raw));
}
export function setPrivacyPolicy(ucid, value) {
  const policy=validatePrivacyPolicy(value);
  Services.prefs.setStringPref(`cloakfox.container.${id(ucid)}.privacy_policy`,JSON.stringify(policy));
  if (Services.prefs.getStringPref(`cloakfox.container.${ucid}.math_seed`, '')) {
    ChromeUtils.importESModule('resource:///modules/CloakfoxSeedSync.sys.mjs').refreshContainerConfig(ucid);
  }
  Services.prefs.savePrefFile(null);
  return policy;
}
export function policyAllows(policy, vector, partitionKey, now=Date.now()) {
  if (vector === 'geometry' && policy.preset === 'compatibility') return false;
  const match=/^\((https?),([^(),\s]+)(?:,f)?\)$/.exec(partitionKey || '');
  if (!match) return true;
  const site=`${match[1]}://${match[2]}`;
  return !policy.exceptions.some(e=>e.site===site && e.expiresAt>now && e.vectors.includes(vector));
}
export function applyPrivacyPolicy(ucid, config) {
  const policy=getPrivacyPolicy(ucid);
  const result={...config,'privacy:policy':policy};
  if (policy.preset==='strict') {
    result['mediaDevices:enabled']=false;
    result['navigator:clipboard:disabled']=true;
  }
  return result;
}
