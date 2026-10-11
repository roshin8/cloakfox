/* MPL-2.0. Reuse native stripping and bounce protection; no content injections. */
export const BOUNCE_PERMISSION='cloakfox-bounce';
export function bouncePermissionType(ucid, privateBrowsingId=0) {
  if(!Number.isInteger(ucid)||ucid<0||ucid>0x7fffffff||![0,1].includes(privateBrowsingId))throw new Error('Invalid bounce exception scope');
  return `${BOUNCE_PERMISSION}:${ucid}:${privateBrowsingId}`;
}
export function normalizeTrackingHost(input) {
  if(typeof input!=='string'||input.length>253||/[\s\/:?#@*\\]/.test(input)||!input)throw new Error('Enter a registrable hostname, without scheme or path');
  const host=new URL('https://'+input.replace(/\.$/,'')).hostname;
  return Services.eTLD.getBaseDomainFromHost(host);
}
export function getTrackingProtection() {
  return {strip:Services.prefs.getBoolPref('privacy.query_stripping.enabled',true),stripPrivate:Services.prefs.getBoolPref('privacy.query_stripping.enabled.pbmode',true),bounceMode:Services.prefs.getIntPref('privacy.bounceTrackingProtection.mode',1),queryExceptions:Services.prefs.getStringPref('privacy.query_stripping.allow_list','').split(',').filter(Boolean)};
}
export function setTrackingProtection({strip,stripPrivate,bounceMode}) {
  if(typeof strip!=='boolean'||typeof stripPrivate!=='boolean'||![0,1,2,3].includes(bounceMode))throw new Error('Invalid tracking protection');
  Services.prefs.setBoolPref('privacy.query_stripping.enabled',strip);
  Services.prefs.setBoolPref('privacy.query_stripping.enabled.pbmode',stripPrivate);
  Services.prefs.setIntPref('privacy.bounceTrackingProtection.mode',bounceMode);
  Services.prefs.savePrefFile(null);
}
export function setQueryException(input,enabled) {
  if(typeof enabled!=='boolean')throw new Error('Invalid exception setting');
  const host=normalizeTrackingHost(input),list=new Set(getTrackingProtection().queryExceptions);
  if(enabled)list.add(host);else list.delete(host);
  Services.prefs.setStringPref('privacy.query_stripping.allow_list',[...list].sort().join(','));Services.prefs.savePrefFile(null);
}
export function listBounceExceptions(ucid) {
  const type=bouncePermissionType(ucid);
  return Services.perms.getAllByTypes([type]).filter(p=>p.capability===Services.perms.ALLOW_ACTION&&(!p.expireTime||p.expireTime>Date.now())).map(p=>({host:p.principal.URI.host,expiresAt:p.expireTime}));
}
export function setBounceException(ucid,input,expiresAt) {
  const type=bouncePermissionType(ucid);
  if(!Number.isSafeInteger(expiresAt)||expiresAt<0||expiresAt>Date.now()+31*86400000)throw new Error('Choose a valid container and expiry within 31 days');
  const host=normalizeTrackingHost(input),principal=Services.scriptSecurityManager.createContentPrincipal(Services.io.newURI('https://'+host),{});
  if(expiresAt<=Date.now())Services.perms.removeFromPrincipal(principal,type);
  else Services.perms.addFromPrincipal(principal,type,Services.perms.ALLOW_ACTION,Services.perms.EXPIRE_TIME,expiresAt);
}

// These private permission types use a bare principal, so native OA clearing
// cannot remove them. Delete exactly the named container's two browsing scopes.
export function clearBounceExceptions(ucid) {
  const types=[bouncePermissionType(ucid,0),bouncePermissionType(ucid,1)];
  for(const type of types)Services.perms.removeByType(type);
}
