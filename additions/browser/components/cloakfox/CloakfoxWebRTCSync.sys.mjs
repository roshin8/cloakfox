/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Optional public-IP lookup for reported WebRTC address alignment.
 * This contacts third-party HTTP services and is off by default. It does
 * not route or block STUN/UDP, enforce a VPN, or guarantee that a reported
 * address matches a container-specific proxy. Explicit native WebRTC and
 * proxy policies must provide those network boundaries separately.
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

// Both master protection and a separate informed opt-in are required.
const ENABLED_PREF = "cloakfox.enabled";
const LOOKUP_PREF = "cloakfox.webrtc.ip_lookup.enabled";

// Monotonic generation counter for overlapping-refresh races. Each
// refresh captures the current value; only the latest in-flight refresh
// is allowed to publish, so a slow stale fetch can't clobber a fresher
// one. Plain incrementing integer — never Date.now().
let refreshGeneration = 0;
const activeFetches = new Set();

// Whether the link observers are currently registered / sync is active.
let syncStarted = false;

function isEnabled() {
  try {
    return Services.prefs.getBoolPref(ENABLED_PREF, false) &&
      Services.prefs.getBoolPref(LOOKUP_PREF, false);
  } catch (_e) {
    return false;
  }
}

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
  const ctrl = new AbortController();
  activeFetches.add(ctrl);
  const timer = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      signal: ctrl.signal, cache: "no-store", credentials: "omit",
      referrerPolicy: "no-referrer",
    });
    if (!response.ok) return null;
    const text = (await response.text()).trim();
    return validator.test(text) ? text : null;
  } catch (_e) {
    return null;
  } finally {
    clearTimeout(timer);
    activeFetches.delete(ctrl);
  }
}

async function fetchFromAny(services, validator, generation) {
  for (const url of services) {
    if (!isEnabled() || generation !== refreshGeneration) return null;
    const v = await fetchOne(url, validator);
    if (v) return v;
  }
  return null;
}

function publish(key, ip) {
  // Retain the previous reported address when a lookup fails. This is
  // cosmetic alignment only; it does not constrain actual network traffic.
  if (!ip) return;
  try {
    Services.ppmm.sharedData.set(key, ip);
    Services.ppmm.sharedData.flush();
  } catch (_e) { /* sharedData may not be available pre-init */ }
}

// Explicitly drop published keys when sync is turned off, so a disabled
// browser doesn't keep advertising a stale spoof IP to content.
function clearPublished() {
  try {
    Services.ppmm.sharedData.delete(SHARED_KEY_V4);
    Services.ppmm.sharedData.delete(SHARED_KEY_V6);
    Services.ppmm.sharedData.flush();
  } catch (_e) { /* sharedData may not be available pre-init */ }
}

async function refreshPublicIP() {
  // Never fetch while spoofing is disabled — the fetch itself is the
  // third-party IP beacon we're gating.
  if (!isEnabled()) return;

  // Capture our generation before awaiting. If another refresh starts
  // while this one is in flight, refreshGeneration moves past `gen` and
  // we drop this (now stale) result rather than let it clobber a fresher
  // publish.
  const gen = ++refreshGeneration;
  for (const ctrl of activeFetches) ctrl.abort();

  // Fetch both families in parallel — they're independent.
  const [v4, v6] = await Promise.all([
    fetchFromAny(IPV4_SERVICES, IPV4_RE, gen),
    fetchFromAny(IPV6_SERVICES, IPV6_RE, gen),
  ]);

  // A newer refresh superseded us — discard this result.
  if (gen !== refreshGeneration || !isEnabled()) return;

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

// React to the user toggling cloakfox.enabled at runtime: start sync
// when enabled, stop and clear published keys when disabled.
const enabledObserver = {
  observe(_subject, topic, data) {
    if (topic !== "nsPref:changed" ||
        (data !== ENABLED_PREF && data !== LOOKUP_PREF)) return;
    if (isEnabled()) {
      startSync();
    } else {
      stopSync();
    }
  },
};

function startSync() {
  if (syncStarted) return;
  syncStarted = true;
  // Lookups are asynchronous and optional, not a protection barrier.
  refreshPublicIP();
  Services.obs.addObserver(linkObserver, "network:link-status-changed");
  Services.obs.addObserver(linkObserver, "network:offline-status-changed");
}

function stopSync() {
  ++refreshGeneration; // Pending requests must never republish after opt-out.
  for (const ctrl of activeFetches) ctrl.abort();
  clearPublished();
  if (!syncStarted) return;
  syncStarted = false;
  Services.obs.removeObserver(linkObserver, "network:link-status-changed");
  Services.obs.removeObserver(linkObserver, "network:offline-status-changed");
  clearPublished();
}

export function initCloakfoxWebRTCSync() {
  ChromeUtils.importESModule('resource:///modules/CloakfoxNetworkPolicy.sys.mjs')
    .initCloakfoxNetworkPolicy();
  ChromeUtils.importESModule('resource:///modules/CloakfoxContainerWorkflows.sys.mjs')
    .initCloakfoxContainerWorkflows();
  // Observe the enable pref so a later toggle can start/stop sync.
  Services.prefs.addObserver(ENABLED_PREF, enabledObserver);
  Services.prefs.addObserver(LOOKUP_PREF, enabledObserver);
  // Do nothing more — no fetch, no link observers — while disabled.
  if (isEnabled()) {
    startSync();
  }
}
