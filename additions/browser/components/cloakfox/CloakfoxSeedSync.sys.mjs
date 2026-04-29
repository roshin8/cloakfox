/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

import { fillPersonaKeys } from "resource:///modules/CloakfoxPersonas.sys.mjs";

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
const PREF_BRANCHES = ["cloakfox.container.", "cloakfox."];

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
// flags. Pulled from CloakfoxPersonas.fillPersonaKeys, picked
// deterministically from math_seed and locked to the host OS family
// (macOS host → macOS personas, etc.) so cross-OS UA mismatches
// don't fingerprint us.
//
// Both layers share the same math_seed so a given container's JS-side
// Math perturbations, C++ canvas/audio/font noise, and persona pick
// are all derived from one source — coherent per-container identity.
function buildCloakCfg(seedB64, ucid = null) {
  return JSON.stringify({
    "canvas:seed": u32(seedB64, 0),
    "audio:seed": u32(seedB64, 1),
    "font:seed": u32(seedB64, 2),
    "font:spacing_seed": u32(seedB64, 3),
    // math:trig_seed drives Math.sin/cos/exp/log noise in worker scope
    // (the Math JSWindowActor only fires on windows; worker realms have
    // their own Math intrinsic). The C++ worker-spoofer injection in
    // WorkerPrivate::GetOrCreateGlobalScope reads this via MaskConfig
    // and embeds it in a per-realm JS spoofer at worker init time.
    "math:trig_seed": u32(seedB64, 4),
    ...fillPersonaKeys(seedB64, ucid),
  });
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
    if (!curCfg) {
      const masterSeed = Services.prefs.getStringPref(
        `cloakfox.container.${ucid}.math_seed`, ""
      );
      if (masterSeed) {
        Services.prefs.setStringPref(cfgPref, buildCloakCfg(masterSeed, ucid));
      }
    }
  } catch (_e) { /* ignore */ }
}

function ensureSeedsForAllContainers() {
  // Default container ucid=0 always.
  ensureContainerSeeds(0);
  // Plus every user-defined container.
  try {
    const ids = Services.contextualIdentityService.getPublicIdentities();
    for (const id of ids) {
      ensureContainerSeeds(id.userContextId);
    }
  } catch (_e) { /* CIS may not be ready yet */ }
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
}
