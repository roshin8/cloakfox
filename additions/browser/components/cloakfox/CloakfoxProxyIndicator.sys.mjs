/* MPL-2.0. Chrome-only indication of the selected container's configured route. */
const MAC_ID = '@testpilot-containers';
let initialized = false;

export function proxyIndicatorState(policy, proxy) {
  if (policy.mode === 2) return {label:'Blocked', tooltip:'Network access is blocked for this container.'};
  let endpoint, authenticated = false;
  if (policy.mode === 1) {
    try {
      const url = new URL(policy.proxyURL);
      endpoint = `${url.protocol}//${url.host}`;
    } catch { return {label:'Proxy unavailable',tooltip:'This container’s proxy configuration is invalid.'}; }
  } else if (proxy && ['http','https','socks','socks4'].includes(proxy.type) && proxy.host && proxy.port) {
    endpoint = `${proxy.type}://${proxy.host.includes(':')?'['+proxy.host+']':proxy.host}:${proxy.port}`;
    authenticated = !!(proxy.proxyAuthorizationHeader || proxy.username);
  } else return null;
  return {label:'Proxy', tooltip:`Proxy configured for this container: ${endpoint}\n${authenticated?'Authentication configured.\n':''}Connection status has not been verified.`};
}

// Separate from the add-on's own text badge, so its notifications remain intact.
const PROXY_BADGE = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><circle cx="8" cy="8" r="7.4" fill="#087f8c" stroke="white" stroke-width="1.2"/><path d="M4 6h7l-2-2m3 6H5l2 2" fill="none" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>');
function renderToolbarBadge(win, state) {
  const button = win.document.getElementById('_testpilot-containers-browser-action');
  const stack = button?.querySelector('.toolbarbutton-badge-stack');
  if (!stack) return;
  let badge = stack.querySelector('#cloakfox-mac-proxy-badge');
  if (!badge) {
    badge = win.document.createXULElement('image');
    badge.id = 'cloakfox-mac-proxy-badge';
    badge.setAttribute('src', PROXY_BADGE);
    badge.setAttribute('role', 'img');
    badge.style.cssText = 'position:absolute;width:14px;height:14px;inset-inline-end:0;bottom:0;';
    stack.append(badge);
  }
  badge.hidden = state?.label !== 'Proxy';
  if (!badge.hidden) {
    badge.setAttribute('tooltiptext', state.tooltip);
    badge.setAttribute('aria-label', 'Container proxy configured');
  }
}

export function initProxyIndicator() {
  if (initialized) return;
  initialized = true;
  const {ExtensionStorageIDB} = ChromeUtils.importESModule('resource://gre/modules/ExtensionStorageIDB.sys.mjs');
  const {ExtensionParent} = ChromeUtils.importESModule('resource://gre/modules/ExtensionParent.sys.mjs');
  const {AddonManager} = ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
  const network = ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkPolicy.sys.mjs');
  const watched = new Map();
  async function macProxy(id) {
    const extension = ExtensionParent.GlobalManager.getExtension(MAC_ID);
    if (!extension || extension.hasShutdown || !extension.hasPermission('proxy')) return null;
    const backend = await ExtensionStorageIDB.selectBackend({extension});
    if (!backend.backendEnabled) return null;
    const db = await ExtensionStorageIDB.open(ExtensionStorageIDB.getStoragePrincipal(extension));
    const data = await db.get('proxifiedContainersKey');
    return data.proxifiedContainersKey?.find(row=>row.cookieStoreId===`firefox-container-${id}`)?.proxy || null;
  }
  function watch(win) {
    if (!win.gBrowser || watched.has(win)) return;
    const box = win.document.getElementById('userContext-icons');
    if (!box) return;
    const label = win.document.createXULElement('label');
    label.id = 'cloakfox-container-proxy-indicator';
    label.hidden = true;
    label.style.cssText = 'margin-inline:8px;font-size:.85em;font-weight:600;';
    box.append(label);
    let serial = 0, lastContainer = null, currentState = null;
    const update = async () => {
      const revision = ++serial;
      const id = Number(win.gBrowser.selectedTab?.getAttribute('usercontextid') || 0);
      if (id !== lastContainer) {label.hidden = true;lastContainer = id;currentState = null;renderToolbarBadge(win, null);}
      if (id === 0) box.after(label);else if (label.parentNode !== box) box.append(label);
      try {
        const policy = network.getContainerNetwork(id);
        const proxy = policy.mode === 0 ? await macProxy(id) : null;
        if (revision !== serial || win.closed) return;
        const state = proxyIndicatorState(policy, proxy);
        currentState = state;
        renderToolbarBadge(win, state);
        if (!state) {label.hidden = true;return;}
        label.setAttribute('value', state.label);
        label.setAttribute('tooltiptext', state.tooltip);
        label.setAttribute('aria-label', state.tooltip);
        label.hidden = false;
      } catch (error) { Cu.reportError(error); }
    };
    const onAttr = event => {if(event.target===win.gBrowser.selectedTab)void update();};
    win.gBrowser.tabContainer.addEventListener('TabSelect', update);
    win.gBrowser.tabContainer.addEventListener('TabAttrModified', onAttr);
    const toolbarObserver = new win.MutationObserver(()=>renderToolbarBadge(win,currentState));
    const toolbox = win.document.getElementById('navigator-toolbox');
    if (toolbox) toolbarObserver.observe(toolbox,{childList:true,subtree:true});
    watched.set(win, update);
    win.addEventListener('unload',()=>{++serial;toolbarObserver.disconnect();watched.delete(win);},{once:true});
    void update();
  }
  const refresh = () => {for (const update of watched.values()) void update();};
  ExtensionStorageIDB.addOnChangedListener(MAC_ID, changes=>{
    if ('proxifiedContainersKey' in changes) refresh();
  });
  Services.prefs.addObserver('cloakfox.container.', refresh);
  AddonManager.addAddonListener({
    onEnabled:addon=>{if(addon.id===MAC_ID)refresh();},
    onDisabled:addon=>{if(addon.id===MAC_ID)refresh();},
    onUninstalled:addon=>{if(addon.id===MAC_ID)refresh();},
  });
  for (const win of Services.wm.getEnumerator('navigator:browser')) watch(win);
  Services.obs.addObserver(win=>win.addEventListener('load',()=>watch(win),{once:true}), 'domwindowopened');
}
