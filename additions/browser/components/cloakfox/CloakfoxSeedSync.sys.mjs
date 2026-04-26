/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

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

function ensureContainerSeeds(ucid) {
  for (const name of SEED_PREF_NAMES) {
    const pref = `cloakfox.container.${ucid}.${name}`;
    try {
      const cur = Services.prefs.getStringPref(pref, "");
      if (!cur) {
        Services.prefs.setStringPref(pref, randomSeedB64());
      }
    } catch (_e) { /* ignore */ }
  }
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

export function initCloakfoxSeedSync() {
  // First-launch seed generation: every container needs random math/
  // keyboard/timing seeds for the JSWindowActors to produce per-user
  // unique fingerprints. Without these, actors early-return and signals
  // leak. Generated once at first launch and persisted in cloakfox.
  // container.<ucid>.<seed_name> string prefs.
  ensureSeedsForAllContainers();
  // Initial snapshot.
  publish();
  // Live updates.
  for (const branchName of PREF_BRANCHES) {
    Services.prefs.addObserver(branchName, observer);
  }
}
