/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: parent-side public-IP detection for WebRTC spoofing.
 *
 * The leak: WebRTC's ICE candidate gathering deliberately probes every
 * network interface to find the best peer-connection path. Even with
 * media.peerconnection.ice.default_address_only=true (which we set),
 * edge cases leak the real IP — IPv6 alongside IPv4, split-tunnel
 * VPN configs, brief windows during VPN reconnect, OS resume from
 * sleep before VPN reattaches, and so on.
 *
 * The fix: detect the user's *current* public IPv4 (the one HTTP
 * traffic actually shows the world) and call window.setWebRTCIPv4
 * with that exact value. WebRTC's reported IP then matches HTTP's
 * IP at all times — no divergence to fingerprint, and no real IP
 * leak even if ICE goes through a non-VPN interface.
 *
 *   Surfshark on  →  HTTP shows Surfshark IP →  WebRTC reports same
 *   Surfshark off →  HTTP shows real IP      →  WebRTC reports same
 *   Surfshark dropping →  both flip together — no transient anomaly
 *
 * Mechanism:
 *   1. At BrowserGlue startup, fetch from a public IP-echo endpoint
 *      (api.ipify.org primary, icanhazip.com fallback). Both return
 *      plain-text "<ipv4>". Parsed and validated.
 *   2. Result published to Services.ppmm.sharedData under
 *      "cloakfox-public-ipv4". CloakfoxWebRTC child actor reads the
 *      value and calls pageWin.setWebRTCIPv4 on every page load.
 *   3. nsIObserver subscribes to "network:link-status-changed"; when
 *      the link bounces (Surfshark connect/disconnect, network change,
 *      sleep/wake), re-fetch and re-publish.
 *
 * Privacy note: fetching from api.ipify.org is itself an HTTP request
 * that already exposes our IP — same info every other request leaks.
 * It's not a new disclosure surface. The endpoint is one of the most
 * widely-used IP-echo services and is privacy-respecting (no logging
 * advertised).
 */

// setTimeout/clearTimeout aren't auto-globals in chrome JS modules —
// they're page-window functions. Import explicitly from Timer.sys.mjs
// so AbortController-style fetch timeouts work. Without this the fetch
// throws "setTimeout is not defined" and falls through to no-spoof.
const { setTimeout, clearTimeout } = ChromeUtils.importESModule(
  "resource://gre/modules/Timer.sys.mjs"
);

const SHARED_KEY = "cloakfox-public-ipv4";
const IP_SERVICES = [
  "https://api.ipify.org",
  "https://icanhazip.com",
];
const FETCH_TIMEOUT_MS = 4000;

// Strict IPv4 dotted-quad with octet bounds. Filters HTML pages
// (when an IP-echo URL accidentally serves a homepage), error
// messages, and obvious garbage.
const IPV4_RE = /^(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$/;

async function fetchPublicIPv4() {
  for (const url of IP_SERVICES) {
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
      const r = await fetch(url, { signal: ctrl.signal, cache: "no-store" });
      clearTimeout(timer);
      if (!r.ok) continue;
      const txt = (await r.text()).trim();
      if (IPV4_RE.test(txt)) return txt;
    } catch (_e) { /* try next service */ }
  }
  return null;
}

function publish(ip) {
  try {
    if (ip) {
      Services.ppmm.sharedData.set(SHARED_KEY, ip);
    } else {
      Services.ppmm.sharedData.delete(SHARED_KEY);
    }
    Services.ppmm.sharedData.flush();
  } catch (_e) { /* sharedData may not be available pre-init */ }
}

async function refreshPublicIP() {
  const ip = await fetchPublicIPv4();
  publish(ip);
}

const linkObserver = {
  observe(_subject, topic, _data) {
    if (topic === "network:link-status-changed" ||
        topic === "network:offline-status-changed") {
      // Network bounced — re-detect. Don't await; we don't want to
      // block the observer chain on an HTTP request.
      refreshPublicIP();
    }
  },
};

export function initCloakfoxWebRTCSync() {
  // Kick off initial detection asynchronously. The first page load
  // after launch may race ahead of this fetch and miss the spoof —
  // acceptable, since the second load and onward see the cached
  // value. If we ever need stricter coverage we can synchronously
  // block startup on the fetch, but that delays UI start by network
  // RTT.
  refreshPublicIP();
  Services.obs.addObserver(linkObserver, "network:link-status-changed");
  Services.obs.addObserver(linkObserver, "network:offline-status-changed");
}
