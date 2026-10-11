/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// Container channel routing. This does not claim to route unrelated browser
// background services or other applications. Native PeerConnection policy
// blocks WebRTC for proxied/blocked containers, independently of spoofing.
const PREFIX = 'cloakfox.container.';
let registered = false;

function validateContainer(ucid) {
  if (!Number.isInteger(ucid) || ucid < 0 || ucid > 0x7fffffff) {
    throw new Error('Invalid container ID');
  }
}

export function normalizeProxyURL(input) {
  const url = new URL(String(input).trim());
  if (!['http:', 'https:', 'socks5:'].includes(url.protocol) ||
      !url.hostname || url.username || url.password ||
      (url.pathname && url.pathname !== '/') || url.search || url.hash) {
    throw new Error('Use an HTTP, HTTPS or SOCKS5 proxy address without credentials or a path.');
  }
  const port = Number(url.port || ({'http:':80,'https:':443}[url.protocol] ?? 0));
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('Proxy port must be between 1 and 65535.');
  }
  return `${url.protocol}//${url.hostname}:${port}`;
}

export function getContainerNetwork(ucid) {
  validateContainer(ucid);
  const prefix = `${PREFIX}${ucid}.`;
  const readMode = suffix => {
    const name = prefix + suffix;
    const type = Services.prefs.getPrefType(name);
    // Gecko's getter fallback also masks wrong-type values; only genuine
    // absence inherits normal mode. A configured invalid type fails closed.
    if (type === Services.prefs.PREF_INVALID) return 0;
    return type === Services.prefs.PREF_INT ? Services.prefs.getIntPref(name) : 2;
  };
  return {
    mode: readMode('network_mode'),
    proxyURL: Services.prefs.getStringPref(prefix + 'proxy_url', ''),
    webrtcMode: readMode('webrtc_mode'),
  };
}

export function setContainerNetwork(ucid, {mode, proxyURL = '', webrtcMode = 0}) {
  validateContainer(ucid);
  if (![0,1,2].includes(mode) || ![0,1,2].includes(webrtcMode)) {
    throw new Error('Invalid network mode');
  }
  const normalized = mode === 1 ? normalizeProxyURL(proxyURL) : '';
  const prefix = `${PREFIX}${ucid}.`;
  // Block new requests during a multi-pref route change. A failed write must
  // leave a blocked policy rather than expose traffic through a default route.
  Services.prefs.setIntPref(prefix + 'network_mode', 2);
  Services.prefs.setStringPref(prefix + 'proxy_ref', '');
  Services.prefs.setStringPref(prefix + 'proxy_url', normalized);
  Services.prefs.setIntPref(prefix + 'webrtc_mode', webrtcMode);
  Services.prefs.setIntPref(prefix + 'network_mode', mode);
}

// Dynamic string prefs are sanitized before reaching content processes. Publish
// only a numeric policy and change epoch; never expose proxy addresses to pages.
function publishNativePolicy(ucid) {
  const policy = getContainerNetwork(ucid);
  const effective = policy.mode !== 0 || ![0,1].includes(policy.webrtcMode)
    ? 2 : policy.webrtcMode;
  const prefix = `${PREFIX}${ucid}.`;
  Services.prefs.setIntPref(prefix + 'effective_webrtc_mode', effective);
  const epoch = Services.prefs.getIntPref(prefix + 'network_epoch', 0);
  Services.prefs.setIntPref(prefix + 'network_epoch', (epoch + 1) % 0x7fffffff);
}
const policyObserver = {
  observe(_subject, topic, name) {
    if (topic !== 'nsPref:changed') return;
    const match = /^cloakfox\.container\.(\d+)\.(?:network_mode|webrtc_mode|proxy_url)$/.exec(name);
    if (match) publishNativePolicy(Number(match[1]));
  },
};

export function initCloakfoxNetworkPolicy() {
  if (registered) return;
  const service = Cc['@mozilla.org/network/protocol-proxy-service;1']
    .getService(Ci.nsIProtocolProxyService);
  const filter = {
    QueryInterface: ChromeUtils.generateQI(['nsIProtocolProxyChannelFilter']),
    applyFilter(channel, inherited, callback) {
      let result = inherited;
      try {
        const info = channel.loadInfo;
        const ucid = info?.originAttributes?.userContextId;
        // System-initiated browser services have default origin attributes too.
        // Keep their browser route, but never exempt a content-triggered load
        // merely because privileged code provided its loading principal.
        const background = info?.loadingPrincipal?.isSystemPrincipal === true &&
          (!info.triggeringPrincipal || info.triggeringPrincipal.isSystemPrincipal === true);
        if (ucid !== undefined && !background) {
          const policy = getContainerNetwork(ucid);
          if (policy.mode !== 0) {
            if (policy.mode !== 1) throw new Error('Container networking blocked');
            const reference = Services.prefs.getStringPref(`${PREFIX}${ucid}.proxy_ref`, '');
            if (reference) {
              const {resolveContainerProxy} = ChromeUtils.importESModule(
                'resource:///modules/CloakfoxProxyManager.sys.mjs');
              // LoginManager is asynchronous. Keep callback outside the error
              // handler so callback failures never cause a second invocation.
              resolveContainerProxy(ucid).then(entry => {
                let proxyInfo = null;
                try {
                  const url = new URL(normalizeProxyURL(entry.url));
                  const type = url.protocol === 'socks5:' ? 'socks' : url.protocol.slice(0,-1);
                  const host = url.hostname.replace(/^\[|\]$/g, '');
                  const port = Number(url.port || (type === 'https' ? 443 : 80));
                  const flags = Ci.nsIProxyInfo.TRANSPARENT_PROXY_RESOLVES_HOST |
                    Ci.nsIProxyInfo.ALWAYS_TUNNEL_VIA_PROXY;
                  const key = `cloakfox-managed:${ucid}:${entry.id}:${entry.revision}`;
                  if (type === 'socks') {
                    proxyInfo = service.newProxyInfoWithAuth(type,host,port,
                      entry.username,entry.password,'',key,flags,0,null);
                  } else {
                    const bytes = new TextEncoder().encode(`${entry.username}:${entry.password}`);
                    const header = entry.hasCredentials
                      ? 'Basic ' + btoa(String.fromCharCode(...bytes)) : '';
                    proxyInfo = service.newProxyInfo(type,host,port,header,key,flags,0,null);
                  }
                } catch (_) { channel.cancel(Cr.NS_ERROR_PROXY_CONNECTION_REFUSED); }
                callback.onProxyFilterResult(proxyInfo);
              }, () => {
                channel.cancel(Cr.NS_ERROR_PROXY_CONNECTION_REFUSED);
                callback.onProxyFilterResult(null);
              });
              return;
            }
            const url = new URL(normalizeProxyURL(policy.proxyURL));
            const type = url.protocol === 'socks5:' ? 'socks' : url.protocol.slice(0,-1);
            const port = Number(url.port || (type === 'https' ? 443 : 80));
            const host = url.hostname.replace(/^\[|\]$/g, '');
            result = service.newProxyInfo(type, host, port, '',
              `cloakfox-container:${ucid}`,
              Ci.nsIProxyInfo.TRANSPARENT_PROXY_RESOLVES_HOST |
                Ci.nsIProxyInfo.ALWAYS_TUNNEL_VIA_PROXY,
              0, null);
          }
        }
      } catch (error) {
        // A null proxy means direct: cancel first, then notify exactly once.
        channel.cancel(Cr.NS_ERROR_PROXY_CONNECTION_REFUSED);
        result = null;
      }
      // Do not catch callback exceptions and mistakenly invoke it a second time.
      callback.onProxyFilterResult(result);
    },
  };
  service.registerChannelFilter(filter, 0x7fffffff);
  Services.prefs.addObserver(PREFIX, policyObserver);
  const ids = new Set(Services.prefs.getChildList(PREFIX).map(name =>
    /^cloakfox\.container\.(\d+)\.(?:network_mode|webrtc_mode|proxy_url)$/.exec(name)?.[1]).filter(Boolean));
  for (const id of ids) publishNativePolicy(Number(id));
  registered = true;
  ChromeUtils.importESModule('resource:///modules/CloakfoxIPConflicts.sys.mjs').initIPConflicts();
}
