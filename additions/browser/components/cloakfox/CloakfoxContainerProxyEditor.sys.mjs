/* MPL-2.0. Authentication editor for Mozilla Multi-Account Containers' popup. */
const MAC_ID = '@testpilot-containers';
let registered = false;
export function initContainerProxyEditor() {
  if (registered) return;
  ChromeUtils.registerWindowActor('CloakfoxContainerProxyEditor', {
    parent:{esModuleURI:'resource:///actors/CloakfoxContainerProxyEditorParent.sys.mjs'},
    child:{esModuleURI:'resource:///actors/CloakfoxContainerProxyEditorChild.sys.mjs',events:{DOMContentLoaded:{capture:true}}},
    matches:['moz-extension://*/popup.html'], remoteTypes:['extension'],
    allFrames:true, safeForUntrustedWebProcess:true,
  });
  registered = true;
}
export function readMACCredentials(proxy) {
  if (!proxy?.proxyAuthorizationHeader) {
    return {username:proxy?.username || '',password:proxy?.password || ''};
  }
  if (!proxy.proxyAuthorizationHeader.startsWith('Basic ')) throw new Error('Saved authentication cannot be edited safely.');
  const raw = atob(proxy.proxyAuthorizationHeader.slice(6));
  let decoded;
  try { decoded = new TextDecoder('utf-8',{fatal:true}).decode(Uint8Array.from(raw,c=>c.charCodeAt(0))); }
  catch { decoded = raw; }
  const colon = decoded.indexOf(':');
  if (colon < 0) throw new Error('Saved authentication cannot be decoded.');
  return {username:decoded.slice(0,colon),password:decoded.slice(colon+1)};
}
export function buildMACProxy(server, username, password, isolationKey) {
  if ([server,username,password].some(value=>typeof value!=='string')) throw new Error('Invalid proxy fields.');
  if (username.length>4096 || password.length>4096 || /[\r\n\0]/.test(username+password) || username.includes(':')) {
    throw new Error('Invalid proxy credentials. Usernames cannot contain a colon.');
  }
  if (!username && password) throw new Error('Enter a username for this password.');
  if (!server.trim()) {
    if (username || password) throw new Error('Enter a proxy server or clear both authentication fields.');
    return null;
  }
  let url;
  try {url=new URL(server.trim());} catch {throw new Error('Use type://host:port for the proxy server.');}
  const type=url.protocol.slice(0,-1);
  if (!['http','https','socks','socks4'].includes(type) || !url.hostname ||
      (url.pathname && url.pathname!=='/') || url.search || url.hash) throw new Error('Enter a valid HTTP, HTTPS, SOCKS or SOCKS4 proxy server.');
  if (url.username || url.password) throw new Error('Put credentials in the username and password fields, not the server address.');
  const port=Number(url.port || (type==='https'?443:type==='http'?80:1080));
  if (!Number.isInteger(port) || port<1 || port>65535) throw new Error('Invalid proxy port.');
  const proxy={type,host:url.hostname.replace(/^\[|\]$/g,''),port,mozProxyEnabled:false,connectionIsolationKey:isolationKey};
  if (username) {
    if (type==='http' || type==='https') {
      const bytes=new TextEncoder().encode(username+':'+password);
      proxy.proxyAuthorizationHeader='Basic '+btoa(Array.from(bytes,b=>String.fromCharCode(b)).join(''));
    } else {proxy.username=username;proxy.password=password;}
  }
  return proxy;
}
export async function macProxyStorage() {
  const {ExtensionParent}=ChromeUtils.importESModule('resource://gre/modules/ExtensionParent.sys.mjs');
  const {ExtensionStorageIDB}=ChromeUtils.importESModule('resource://gre/modules/ExtensionStorageIDB.sys.mjs');
  const extension=ExtensionParent.GlobalManager.getExtension(MAC_ID);
  if (!extension || extension.hasShutdown) throw new Error('Multi-Account Containers is not running.');
  const backend=await ExtensionStorageIDB.selectBackend({extension});
  if (!backend.backendEnabled) throw new Error('The extension storage backend is unavailable.');
  const db=await ExtensionStorageIDB.open(ExtensionStorageIDB.getStoragePrincipal(extension));
  return {extension,db,ExtensionStorageIDB};
}
function resolveContainer(data) {
  const {ContextualIdentityService:service}=ChromeUtils.importESModule('moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
  const identities=service.getPublicIdentities().map(identity=>({
    cookieStoreId:`firefox-container-${identity.userContextId}`,
    name:service.getUserContextLabel(identity.userContextId),id:identity.userContextId,
  }));
  const explicit=identities.find(identity=>identity.cookieStoreId===data.cookieStoreId);
  if (explicit && explicit.name===data.name) return explicit;
  const matching=identities.filter(identity=>identity.name===data.name);
  if (matching.length!==1) throw new Error('Select the container again so its proxy can be identified safely.');
  return matching[0];
}
export async function readMACProxy(data) {
  const container=resolveContainer(data);
  const {db}=await macProxyStorage();
  const saved=await db.get('proxifiedContainersKey');
  const proxy=saved.proxifiedContainersKey?.find(row=>row.cookieStoreId===container.cookieStoreId)?.proxy;
  return {...container,...readMACCredentials(proxy),server:proxy?.host?`${proxy.type}://${proxy.host.includes(':')?'['+proxy.host+']':proxy.host}:${proxy.port}`:''};
}
export async function saveMACProxy(data) {
  const container=resolveContainer(data);
  const {db,extension,ExtensionStorageIDB}=await macProxyStorage();
  if (!extension.hasPermission('proxy')) throw new Error('Enable the extension’s proxy permission first.');
  const isolationKey=`cloakfox-managed:mac-${container.id}-${Services.uuid.generateUUID()}`;
  const proxy=buildMACProxy(data.server,data.username,data.password,isolationKey);
  const saved=await db.get('proxifiedContainersKey');
  const rows=saved.proxifiedContainersKey || [];
  const index=rows.findIndex(row=>row.cookieStoreId===container.cookieStoreId);
  const row={cookieStoreId:container.cookieStoreId,proxy};
  if(index<0)rows.push(row);else rows[index]={...rows[index],...row};
  const changes=await db.set({proxifiedContainersKey:rows});
  if(changes)ExtensionStorageIDB.notifyListeners(MAC_ID,changes);
  ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs').clearIPCheckCache();
  return {name:container.name,server:proxy?`${proxy.type}://${proxy.host.includes(':')?'['+proxy.host+']':proxy.host}:${proxy.port}`:'',authenticated:!!data.username};
}
