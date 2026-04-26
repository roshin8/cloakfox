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

const SHARED_KEY_V4 = "cloakfox-public-ipv4";
const SHARED_KEY_V6 = "cloakfox-public-ipv6";

// Separate endpoints per family. api.ipify.org / icanhazip.com both
// auto-pick whichever family the request came over; api64.ipify.org
// and v6.ident.me are IPv6-preferring. We hit both to cover dual-
// stacked hosts where each endpoint may resolve to a different family.
const IPV4_SERVICES = [
  "https://api.ipify.org",
  "https://icanhazip.com",
];
const IPV6_SERVICES = [
  "https://api64.ipify.org",
  "https://v6.ident.me",
];
const FETCH_TIMEOUT_MS = 4000;

// Strict IPv4 dotted-quad with octet bounds.
const IPV4_RE = /^(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$/;
// Loose IPv6 — accepts compressed forms (::), embedded IPv4, etc.
// We just need "looks like an IPv6 the WebRTC setter would accept";
// strict validation isn't worth the regex complexity.
const IPV6_RE = /^[0-9a-fA-F:]+(?::\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})?$/;

async function fetchOne(url, validator) {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
    const r = await fetch(url, { signal: ctrl.signal, cache: "no-store" });
    clearTimeout(timer);
    if (!r.ok) return null;
    const txt = (await r.text()).trim();
    return validator.test(txt) ? txt : null;
  } catch (_e) { return null; }
}

async function fetchFromAny(services, validator) {
  for (const url of services) {
    const v = await fetchOne(url, validator);
    if (v) return v;
  }
  return null;
}

function publish(key, ip) {
  try {
    if (ip) {
      Services.ppmm.sharedData.set(key, ip);
    } else {
      Services.ppmm.sharedData.delete(key);
    }
    Services.ppmm.sharedData.flush();
  } catch (_e) { /* sharedData may not be available pre-init */ }
}

async function refreshPublicIP() {
  // Fetch both families in parallel — they're independent.
  const [v4, v6] = await Promise.all([
    fetchFromAny(IPV4_SERVICES, IPV4_RE),
    fetchFromAny(IPV6_SERVICES, IPV6_RE),
  ]);
  publish(SHARED_KEY_V4, v4);
  publish(SHARED_KEY_V6, v6);
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
