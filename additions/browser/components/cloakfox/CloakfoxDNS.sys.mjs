/* MPL-2.0. Browser-wide native DNS policy, independent of container destinations. */
export function numericAddress(value) {
  if(typeof value!=='string'||value.length>45)return false;
  if(value.includes(':')){try{return value!=='::'&&new URL(`https://[${value}]/`).hostname.startsWith('[');}catch{return false;}}
  return /^(?:0|[1-9]\d{0,2})(?:\.(?:0|[1-9]\d{0,2})){3}$/.test(value)&&value.split('.').every(n=>Number(n)<=255);
}
export function validateDNSPolicy(value) {
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!['mode','resolver','bootstrap'].includes(k))||!['system','fallback','only','firefox'].includes(value.mode))throw new Error('Invalid DNS policy');
  if(['system','firefox'].includes(value.mode))return {mode:value.mode,resolver:'',bootstrap:''};
  if(typeof value.resolver!=='string'||value.resolver.length>2048)throw new Error('Enter an HTTPS DNS resolver URL');
  const url=new URL(value.resolver);
  if(url.protocol!=='https:'||url.username||url.password||url.hash)throw new Error('Use an HTTPS resolver without credentials or a fragment');
  if(value.bootstrap!==undefined&&typeof value.bootstrap!=='string')throw new Error('Bootstrap must be a numeric address');
  const bootstrap=(value.bootstrap||'').trim();
  if(bootstrap&&!numericAddress(bootstrap))throw new Error('Bootstrap must be a numeric IPv4 or IPv6 address');
  if(value.mode==='only'&&!bootstrap&&!numericAddress(url.hostname.replace(/^\[|\]$/g,'')))throw new Error('Encrypted-only DNS needs a numeric bootstrap address to avoid resolving the resolver through plaintext DNS');
  return {mode:value.mode,resolver:url.href,bootstrap};
}
export function getDNSPolicy() {
  const mode=Services.prefs.getIntPref('network.trr.mode',0),guard=Services.prefs.getBoolPref('cloakfox.dns.fail_closed',false);
  return {mode:guard||mode===3?'only':mode===2?'fallback':mode===5?'system':'firefox',resolver:Services.prefs.getStringPref('network.trr.uri',''),bootstrap:Services.prefs.getStringPref('network.trr.bootstrapAddr','')};
}
export function setDNSPolicy(value) {
  const policy=validateDNSPolicy(value),p=Services.prefs;
  // Guard first and release last so a partial strict-mode write cannot leak.
  if(policy.mode==='only')p.setBoolPref('cloakfox.dns.fail_closed',true);
  if(['only','fallback'].includes(policy.mode)) {
    p.setStringPref('network.trr.uri',policy.resolver);
    p.setStringPref('network.trr.bootstrapAddr',policy.bootstrap);
    p.setIntPref('network.trr.mode',policy.mode==='only'?3:2);
  }else if(policy.mode==='system')p.setIntPref('network.trr.mode',5);
  else {
    for(const key of ['network.trr.mode','network.trr.uri','network.trr.bootstrapAddr'])p.clearUserPref(key);
  }
  if(policy.mode!=='only')p.setBoolPref('cloakfox.dns.fail_closed',false);
  Services.dns.clearCache(true);
  p.savePrefFile(null);
  return policy;
}
