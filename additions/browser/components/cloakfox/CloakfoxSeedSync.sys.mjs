/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

import {
  fillPersonaKeys,
  genericFontListUnion,
} from "resource:///modules/CloakfoxPersonas.sys.mjs";
import { applyOverrides } from "resource:///modules/CloakfoxOverrides.sys.mjs";
// ContextualIdentityService must be imported explicitly: there is no
// Services.contextualIdentityService getter. Reading it yields undefined, so
// calling through it throws a TypeError — see ensureSeedsForAllContainers.
import { ContextualIdentityService } from "resource://gre/modules/ContextualIdentityService.sys.mjs";

/* Cloakfox: parent-side seed sync for content-process JSWindowActors.
 *
 * Why this exists: Firefox doesn't sync user-set prefs in unknown
 * namespaces (e.g. cloakfox.container.<ucid>.math_seed) to content
 * processes. Bool prefs like cloakfox.enabled DO propagate, but
 * string prefs in our custom container namespace don't. Verified
 * empirically: in content scope,
 *   Services.prefs.getStringPref("cloakfox.container.0.math_seed")
 * returns "" even when the parent's Services.prefs has it set.
 *
 * Workaround: at parent startup, snapshot every cloakfox.container.*
 * + cloakfox.enabled pref into Services.ppmm.sharedData under the
 * key "cloakfox-seeds". Content processes read it synchronously via
 * Services.cpmm.sharedData.get("cloakfox-seeds"). A pref observer
 * keeps the sharedData snapshot live for runtime regen from
 * about:cloakfox.
 *
 * Imported from BrowserGlue alongside CloakfoxPrefMigration. Order
 * matters: migration runs first (so any roverfox.s.* legacy values
 * land in cloakfox.s.* and cloakfox.container.* before we snapshot).
 */

const SHARED_KEY = "cloakfox-seeds";
// Single broad branch. "cloakfox." already matches every
// cloakfox.container.* pref (and cloakfox.s.*, cloakfox.enabled, etc.),
// so listing a narrower "cloakfox.container." branch alongside it would
// only double-register the observer and double-snapshot the same prefs —
// causing observe()/snapshot()/flush() to run twice per container-pref
// change. One branch covers everything exactly once.
const PREF_BRANCHES = ["cloakfox."];

// Per-signal seed pref names. Math/Keyboard/Timing/TabHistory all need
// a seed; without one the actor early-returns. Auto-generate at parent
// startup so out-of-box installs get full protection in the default
// container without user intervention.
const SEED_PREF_NAMES = [
  "math_seed",
  "keyboard_seed",
  "timing_seed",
];

function randomSeedB64() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  // btoa needs a binary-string form
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s);
}

// Derive a uint32 from the seed at offset i*4. Mirrors content/settings.js
// — keeping the derivation identical means the about:cloakfox UI's
// "regenerate" button and our auto-generation produce the same shape of
// cloak_cfg blob, so nothing downstream cares which path created it.
function u32(seedB64, i) {
  const bin = atob(seedB64);
  const view = new DataView(new ArrayBuffer(4));
  for (let j = 0; j < 4; j++) view.setUint8(j, bin.charCodeAt(i * 4 + j));
  return view.getUint32(0);
}

// Persona-driven cloak_cfg.
//
// Layer 1: the 4 hash-based MaskConfig keys (canvas / audio / font /
// font-spacing) — drive the per-container noise on canvas pixel data,
// audio buffer values, font list ordering, and font glyph spacing.
//
// Layer 2: persona keys — drive the navigator UA / platform / oscpu /
// language, screen dimensions, WebGL renderer, AudioContext latency,
// codec / media-capability spoof flags, and "disable leaky surface"
// flags. Pulled from CloakfoxPersonas.fillPersonaKeys, sampled
// deterministically from math_seed. The OS is sampled FROM THE SEED
// (not locked to the host), so a container's persona may be any OS;
// every key in the bundle is kept internally coherent with that
// sampled OS so there's no cross-OS mismatch within a persona.
//
// Both layers share the same math_seed so a given container's JS-side
// Math perturbations, C++ canvas/audio/font noise, and persona pick
// are all derived from one source — coherent per-container identity.
function buildCloakCfg(seedB64, ucid = null) {
  // Layer order matters: hash seeds → persona → user overrides. User
  // overrides win because they're applied last. This lets a user pin
  // individual fields (hwc=16, timezone=Berlin) without losing the
  // rest of the persona's coherent identity.
  const base = {
    "canvas:seed": u32(seedB64, 0),
    "audio:seed": u32(seedB64, 1),
    "font:seed": u32(seedB64, 2),
    // C++ FontSpacingSeedManager reads "fonts:spacing_seed" (plural); the
    // singular key silently no-ops the per-container font-spacing noise.
    "fonts:spacing_seed": u32(seedB64, 3),
    // math:trig_seed drives Math.sin/cos/exp/log noise in worker scope
    // (the Math JSWindowActor only fires on windows; worker realms have
    // their own Math intrinsic). The C++ worker-spoofer injection in
    // WorkerPrivate::GetOrCreateGlobalScope reads this via MaskConfig
    // and embeds it in a per-realm JS spoofer at worker init time.
    "math:trig_seed": u32(seedB64, 4),
    ...fillPersonaKeys(seedB64, ucid),
  };
  return JSON.stringify(ucid !== null ? applyOverrides(ucid, base) : base);
}

// Decide whether a container's cloak_cfg must be (re)generated. Pure so it can
// be unit-tested. Rebuild when: absent, corrupt, or produced by a build that
// predates the font keys (missing "fonts" or "fonts:spacing_seed"). buildCloakCfg
// is deterministic in the master seed, so a rebuild reproduces the same persona
// plus the new keys — a safe idempotent upgrade.
export function needsCfgRebuild(curCfg) {
  if (!curCfg) return true;
  let parsed;
  try {
    parsed = JSON.parse(curCfg);
  } catch (_e) {
    return true; // corrupt JSON → rebuild from seed
  }
  // JSON.parse succeeds for "null", "123", "true", '"x"' etc. Guard the `in`
  // checks: `"fonts" in null` throws, which would escape this function and
  // leave the container permanently un-rebuilt. Any non-object is bad data →
  // rebuild.
  if (typeof parsed !== "object" || parsed === null) return true;
  return !("fonts" in parsed) || !("fonts:spacing_seed" in parsed);
}

function ensureContainerSeeds(ucid) {
  // First, the per-actor seeds (math/keyboard/timing) used by JSWindow
  // Actors. Each is independent so a missing one doesn't gate the others.
  for (const name of SEED_PREF_NAMES) {
    const pref = `cloakfox.container.${ucid}.${name}`;
    try {
      const cur = Services.prefs.getStringPref(pref, "");
      if (!cur) {
        Services.prefs.setStringPref(pref, randomSeedB64());
      }
    } catch (_e) { /* ignore */ }
  }

  // Then the cloak_cfg JSON blob used by the C++ canvas / audio / font
  // managers via MaskConfig. Derived from math_seed (already generated
  // above if it was missing) so the per-container fingerprint stays
  // coherent across both layers — same seed drives both the JS Math
  // perturbations and the C++ canvas/audio/font noise.
  const cfgPref = `cloakfox.s.cloak_cfg_${ucid}`;
  try {
    const curCfg = Services.prefs.getStringPref(cfgPref, "");
    // See needsCfgRebuild: regenerate when absent, corrupt, or missing the font
    // keys (a profile upgraded from a pre-fonts build), so per-container fonts
    // actually activate for existing containers.
    if (needsCfgRebuild(curCfg)) {
      const masterSeed = Services.prefs.getStringPref(
        `cloakfox.container.${ucid}.math_seed`, ""
      );
      if (masterSeed) {
        // MERGE rather than replace. A cfg that is present and well-formed but
        // simply missing the font keys is an OLD cfg, not a bad one — every
        // other key in it was set deliberately, whether by a previous build, an
        // administrator, or a test fixture. Overwriting it wholesale silently
        // discarded all of them.
        //
        // That is not theoretical: it broke six fingerprint probes. Two failed
        // outright and were blamed on the WebSocket and IndexedDB C++ patches,
        // which turned out to be correct all along; three more kept PASSING
        // while testing nothing, because they assert that two runs differ and
        // two randomly-regenerated personas do differ. Any user-provided
        // cloak_cfg was subject to exactly the same silent replacement.
        //
        // Generated keys fill the gaps; existing keys win.
        const generated = JSON.parse(buildCloakCfg(masterSeed, ucid));
        let existing = null;
        try {
          const parsed = JSON.parse(curCfg);
          if (parsed && typeof parsed === "object") {
            existing = parsed;
          }
        } catch (_e) { /* corrupt → generated alone, as before */ }
        Services.prefs.setStringPref(
          cfgPref, JSON.stringify(existing ? { ...generated, ...existing } : generated));
      }
    }
  } catch (_e) { /* ignore */ }
}

// Map the CSS generics (serif/sans-serif/monospace) so they don't collapse to
// last-resort when the real host's default generic fonts are hidden by a persona
// whitelist. These are PROCESS-GLOBAL prefs (per-langgroup): one value for every
// container. We set the UNION of all OSes' generics (genericFontListUnion) as a
// comma-separated fallback list; Gecko resolves each container to the first
// entry its own per-container FontListManager filter admits. The union is
// ordered so every container gets its OWN persona generic (see the ordering note
// on genericFontListUnion).
//
// This is the JS half of review finding #7's fix; the C++ half is in
// font-hijacker.patch, which keeps every union family in the process-global
// whitelist so gfxPlatformFontList::ApplyWhitelist() doesn't delete cross-OS
// families before the per-container filter can select among them. Verified safe:
// Firefox ships no Local Font Access API, and every content font-presence path
// (text rendering, matchMedia, document.fonts, local()) is per-container
// filtered or fails closed, so the union never leaks a family to a container
// outside its persona. Cleared when disabled so the real host generics return.
function applyGenericFontPrefs() {
  const prefs = {
    "font.name-list.serif.x-western": "serif",
    "font.name-list.sans-serif.x-western": "sans",
    "font.name-list.monospace.x-western": "mono",
  };
  try {
    if (!Services.prefs.getBoolPref("cloakfox.enabled", true)) {
      for (const pref of Object.keys(prefs)) {
        try { Services.prefs.clearUserPref(pref); } catch (_e) { /* ignore */ }
      }
      return;
    }
    const union = genericFontListUnion();
    for (const [pref, slot] of Object.entries(prefs)) {
      const val = union[slot];
      if (typeof val === "string" && val) {
        Services.prefs.setStringPref(pref, val);
      }
    }
  } catch (_e) { /* ignore */ }
}

function ensureSeedsForAllContainers() {
  // Default container ucid=0 always.
  ensureContainerSeeds(0);
  applyGenericFontPrefs();
  // Plus every user-defined container.
  //
  // This used to call Services.contextualIdentityService, which does NOT
  // exist — there is no such Services getter, so it evaluated to undefined
  // and the property access threw a TypeError on every single call. The
  // catch below swallowed it as "CIS may not be ready yet", so the failure
  // was permanent AND silent: only the default container ever got seeds.
  //
  // Measured before the fix, on a container the user created in the UI:
  //     cloak_cfg prefs present : cloakfox.s.cloak_cfg_0   (only)
  //     container seed prefs    : ucid 0 only
  //     real container ucid=6   : userAgent, platform AND oscpu all reported
  //                               the REAL host, with no spoofing at all
  //
  // i.e. per-container isolation — the reason containers exist here — was
  // inert for every container but the default one.
  //
  // Keep the try/catch (container seeding must never break startup) but scope
  // it per container, so one bad container can't stop the rest from seeding.
  let ids = [];
  try {
    ids = ContextualIdentityService.getPublicIdentities();
  } catch (e) {
    console.error("Cloakfox: could not enumerate containers to seed", e);
  }
  for (const id of ids) {
    try {
      ensureContainerSeeds(id.userContextId);
    } catch (e) {
      console.error(
        `Cloakfox: failed to seed container ${id.userContextId}`, e);
    }
  }
}

function snapshot() {
  const out = {};
  for (const branchName of PREF_BRANCHES) {
    const branch = Services.prefs.getBranch(branchName);
    for (const key of branch.getChildList("")) {
      const fullName = branchName + key;
      try {
        const t = Services.prefs.getPrefType(fullName);
        if (t === Services.prefs.PREF_STRING) {
          out[fullName] = Services.prefs.getStringPref(fullName, "");
        } else if (t === Services.prefs.PREF_INT) {
          out[fullName] = Services.prefs.getIntPref(fullName, 0);
        } else if (t === Services.prefs.PREF_BOOL) {
          out[fullName] = Services.prefs.getBoolPref(fullName, false);
        }
      } catch (_e) { /* skip on error */ }
    }
  }
  return out;
}

function publish() {
  try {
    Services.ppmm.sharedData.set(SHARED_KEY, snapshot());
    Services.ppmm.sharedData.flush();
  } catch (_e) { /* sharedData may not be available pre-init */ }
}

const observer = {
  observe(_subject, topic, data) {
    if (topic !== "nsPref:changed") return;
    // Re-snapshot. Cheaper than diffing — pref count is small.
    publish();
  },
};

// Containers created AFTER startup used to get no persona at all.
// ensureSeedsForAllContainers() enumerates getPublicIdentities() once during
// init, so a container the user made later had no cloak_cfg until the next
// restart. For that whole session it fell through every MaskConfig lookup to
// the native value and reported the REAL host — measured: navigator.platform
// "MacIntel" and oscpu "Intel Mac OS X 10.15" while the userAgent said
// Windows. That is both a host-OS leak and a self-contradiction, in exactly
// the containers a user creates for isolation.
//
// ContextualIdentityService fires these when identities change, so seed the
// new container immediately and re-publish so content processes see it.
const CONTAINER_TOPICS = [
  "contextual-identity-created",
  "contextual-identity-updated",
];

const containerObserver = {
  observe(_subject, topic, _data) {
    if (!CONTAINER_TOPICS.includes(topic)) return;
    try {
      ensureSeedsForAllContainers();
      publish();
    } catch (_e) { /* never break container creation */ }
  },
};

// Bridge cloakfox.opt.timer_quantization_off → privacy.reduceTimerPrecision.
// Both prefs control the same Firefox engine setting, but the cloakfox.opt.*
// namespace is what about:cloakfox UI exposes and what cloakfox.cfg
// documents. When the user flips ours on, mirror to Firefox's. Done at
// startup only — for live-toggle support we'd add a pref observer, but
// performance.now precision is locked at process startup anyway, so the
// re-mirror would still need a relaunch to take effect.
function applyTimerQuantizationPref() {
  try {
    if (Services.prefs.getBoolPref("cloakfox.opt.timer_quantization_off", false)) {
      Services.prefs.setBoolPref("privacy.reduceTimerPrecision", false);
    }
  } catch (_e) { /* ignore */ }
}

export function initCloakfoxSeedSync() {
  // First-launch seed generation: every container needs random math/
  // keyboard/timing seeds for the JSWindowActors to produce per-user
  // unique fingerprints. Without these, actors early-return and signals
  // leak. Generated once at first launch and persisted in cloakfox.
  // container.<ucid>.<seed_name> string prefs.
  ensureSeedsForAllContainers();
  applyTimerQuantizationPref();
  // Initial snapshot.
  publish();
  // Live updates.
  for (const branchName of PREF_BRANCHES) {
    Services.prefs.addObserver(branchName, observer);
  }
  // Seed containers created after startup (see containerObserver above).
  for (const topic of CONTAINER_TOPICS) {
    try {
      Services.obs.addObserver(containerObserver, topic);
    } catch (_e) { /* topic unavailable — startup seeding still applies */ }
  }
}
