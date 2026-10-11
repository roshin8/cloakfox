/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// Intent is engine-independent. Profile IDs and implementation capabilities
// belong to the adapter; future Chromium integration must provide its own
// descriptor, not reuse Gecko/NSS/neqo knobs or assume a UA switches engines.
const NETWORK_ADAPTERS = Object.freeze({
  gecko: {
    commit: writeGeckoNetworkProfile,
    nativeFamily: "firefox",
    profiles: {
      firefox: {profileId: 0, experimental: false, referenceMajor: null, gaps: [],
        protocols: {h2: "firefox", tls: 0, quic: 0, h3: 0}},
      chrome: {profileId: 1, experimental: true, referenceMajor: 155,
        gaps: ["ALPS", "trust-anchor IDs", "full GREASE shape",
          "other TLS extensions and signatures", "QUIC extensions and packet behavior",
          "WebTransport retains native networking"],
        protocols: {h2: "chrome", tls: 1, quic: 1, h3: 1}},
    },
  },
});

export function selectNetworkProfile({engine = "gecko", ua = "", followIdentity = false, enabled = true} = {}) {
  const adapter = Object.hasOwn(NETWORK_ADAPTERS, engine) ? NETWORK_ADAPTERS[engine] : null;
  if (!adapter) return {profileId: 0, family: null, backend: null, available: false,
    experimental: false, unsupported: true, referenceMajor: null, gaps: [], protocols: null};
  // All protocol metadata comes from the chosen engine adapter. A Chromium
  // adapter can use its native profile ID/stack without inheriting NSS IDs.
  const describe = family => {
    const profile = adapter.profiles[family];
    return {...profile, family, backend: engine, available: true, unsupported: false,
      gaps: [...profile.gaps], protocols: {...profile.protocols}};
  };
  const native = describe(adapter.nativeFamily);
  if (!enabled || !followIdentity) return native;
  let family;
  if (typeof ua === "string" && /Firefox\/\d/.test(ua)) family = "firefox";
  else if (typeof ua === "string" && /(?:Chrome|Chromium)\/\d/.test(ua)
      && !/(?:iPhone|iPad|Android|Mobile|Edg\/|OPR\/|Vivaldi\/|YaBrowser\/|SamsungBrowser\/)/.test(ua)) family = "chrome";
  if (!family || !Object.hasOwn(adapter.profiles, family)) return {...native, unsupported: true};
  const profile = adapter.profiles[family];
  if (profile.referenceMajor !== null) {
    const major = Number(/(?:Chrome|Chromium)\/(\d+)/.exec(ua)?.[1]);
    if (major !== profile.referenceMajor) return {...native, unsupported: true};
  }
  return describe(family);
}

export function resolveNetworkProfile(ucid, ua) {
  if (!Number.isSafeInteger(ucid) || ucid < 0) throw new TypeError("Invalid container ID");
  if (ua === undefined) {
    try { ua = JSON.parse(Services.prefs.getStringPref(`cloakfox.s.cloak_cfg_${ucid}`, "{}"))["navigator.userAgent"] || ""; }
    catch { ua = ""; }
  }
  if (Services.prefs.getIntPref(`cloakfox.container.${ucid}.network_state`, 0) < 0) {
    return {...selectNetworkProfile({enabled: false}), unsupported: true,
      reason: "Network generation exhausted; use a fresh browser profile"};
  }
  return selectNetworkProfile({ua,
    enabled: Services.prefs.getBoolPref("cloakfox.enabled", false),
    followIdentity: Services.prefs.getBoolPref(`cloakfox.container.${ucid}.network_follow_identity`, false)});
}

export function writeNetworkProfile(ucid, ua, options = {}) {
  const selected = resolveNetworkProfile(ucid, ua);
  // Generation encoding and socket/cache metadata belong to the adapter,
  // just like protocol capabilities. Chromium supplies its own commit path.
  return NETWORK_ADAPTERS[selected.backend].commit(ucid, selected, options);
}

function writeGeckoNetworkProfile(ucid, selected, {advanceGeneration = false} = {}) {
  const statePref = `cloakfox.container.${ucid}.network_state`;
  const previous = Services.prefs.getIntPref(statePref, 0);
  if (previous < 0) return {...selected, generation: 0x3fffff};
  let generation = previous >>> 1;
  if (advanceGeneration || (previous & 1) !== selected.profileId) generation++;
  // Bits 8–29 of Gecko socket metadata carry this generation. Never wrap and
  // revive old connections/tickets. Exhaustion requires a fresh profile.
  if (generation >= 0x3fffff) {
    Services.prefs.setIntPref(statePref, -1);
    Services.prefs.setIntPref(`cloakfox.container.${ucid}.network_profile`, 0);
    Services.prefs.setCharPref(`cloakfox.container.${ucid}.h2_profile`, "firefox");
    Services.prefs.setIntPref(`cloakfox.container.${ucid}.h3_profile`, 0);
    return {...resolveNetworkProfile(ucid, undefined), generation: 0x3fffff};
  }
  // A single integer commits profile and generation to all native transports.
  // Compatibility pref names
  // remain for tools, but native adapters do not read a partially written set.
  Services.prefs.setCharPref(`cloakfox.container.${ucid}.h2_profile`, selected.protocols.h2);
  Services.prefs.setIntPref(`cloakfox.container.${ucid}.h3_profile`, selected.protocols.h3);
  const pref = `cloakfox.container.${ucid}.network_profile`;
  if (Services.prefs.getIntPref(pref, -1) !== selected.profileId) {
    Services.prefs.setIntPref(pref, selected.profileId);
  }
  const state = (generation * 2) + selected.profileId;
  if (previous !== state) Services.prefs.setIntPref(statePref, state);
  return {...selected, generation};
}

let networkProfilesInitialized = false;
function reconcileNetworkProfiles() {
  for (const suffix of Services.prefs.getBranch("cloakfox.s.cloak_cfg_").getChildList("")) {
    if (/^\d+$/.test(suffix) && Number.isSafeInteger(Number(suffix))) writeNetworkProfile(Number(suffix));
  }
}

export function initNetworkProfiles() {
  if (networkProfilesInitialized) return;
  networkProfilesInitialized = true;
  const observer = {observe(_subject, _topic, pref) {
    const match = /^(?:cloakfox\.s\.cloak_cfg_(\d+)|cloakfox\.container\.(\d+)\.network_follow_identity)$/.exec(pref);
    if (match) writeNetworkProfile(Number(match[1] ?? match[2]), undefined, {advanceGeneration: true});
    else if (pref === "cloakfox.enabled") {
      reconcileNetworkProfiles();
    }
  }};
  for (const branch of ["cloakfox.s.", "cloakfox.container.", "cloakfox.enabled"]) {
    Services.prefs.addObserver(branch, observer);
  }
  reconcileNetworkProfiles();
}
