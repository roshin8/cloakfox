/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: per-container, per-field override layer.
 *
 * The persona system (CloakfoxPersonas.sys.mjs) emits ~40 cloak_cfg
 * keys in a coherent bundle. This module lets a user pin individual
 * keys to specific values that override whatever the persona picks —
 * so you can keep the persona's UA but force hardwareConcurrency=16,
 * or keep the persona's screen but pin the timezone to Berlin.
 *
 * Storage: overrides live in `cloakfox.container.<ucid>.override.<key>`
 * prefs. Pref TYPE is determined by KEY_TYPES below — this is the
 * canonical type table for cloak_cfg keys, used by both the override
 * read/write paths and the about:cloakfox UI to render the right
 * input widget.
 *
 * Application: SeedSync.buildCloakCfg calls applyOverrides(ucid, base)
 * AFTER fillPersonaKeys + the 5 hash seeds, so user overrides win.
 * Clearing an override falls back to the persona's value; clearing all
 * overrides for a container restores its full persona behavior.
 */

// Canonical type table for every cloak_cfg key the C++ MaskConfig
// patches and the persona generator produce. Keep this in sync with
// CloakfoxPersonaData generation + SeedSync.buildCloakCfg.
//   "string" → text input + Services.prefs.setStringPref
//   "int"    → number input (integer) + setIntPref
//   "float"  → number input (float, stored as string) + setStringPref
//             (Firefox has no native float pref; we serialize)
//   "bool"   → checkbox; cloak_cfg encodes presence-as-true
export const KEY_TYPES = {
  // ── per-vector hash seeds ──
  "canvas:seed":        "int",
  "audio:seed":         "int",
  "font:seed":          "int",
  "font:spacing_seed":  "int",
  "math:trig_seed":     "int",

  // ── navigator / UA ──
  "navigator.platform":             "string",
  "navigator.userAgent":            "string",
  "navigator.appVersion":           "string",
  "navigator.oscpu":                "string",
  "navigator.language":             "string",
  "navigator.hardwareConcurrency":  "int",
  "navigator:maxTouchPoints":       "int",

  // ── HTTP request headers ──
  "headers.User-Agent":      "string",
  "headers.Accept-Language": "string",
  "headers.Accept-Encoding": "string",

  // ── screen / window ──
  "screen.width":             "int",
  "screen.height":            "int",
  "screen.availWidth":        "int",
  "screen.availHeight":       "int",
  "screen.availLeft":         "int",
  "screen.availTop":          "int",
  "screen.pageXOffset":       "int",
  "screen.pageYOffset":       "int",
  "screen:orientation:type":  "string",
  "window.innerWidth":        "int",
  "window.innerHeight":       "int",
  "window.outerWidth":        "int",
  "window.outerHeight":       "int",
  "window.devicePixelRatio":  "float",
  "window.screenX":           "int",
  "window.screenY":           "int",
  "window.scrollMinX":        "int",
  "window.scrollMinY":        "int",

  // ── graphics ──
  "webGl:vendor":   "string",
  "webGl:renderer": "string",

  // ── audio ──
  "AudioContext:sampleRate":      "int",
  "AudioContext:maxChannelCount": "int",
  "AudioContext:outputLatency":   "float",

  // ── locale ──
  "locale:language": "string",
  "locale:region":   "string",
  "locale:script":   "string",

  // ── geolocation ──
  "geolocation:latitude":  "float",
  "geolocation:longitude": "float",
  "geolocation:accuracy":  "float",

  // ── webrtc IP overrides (manual) ──
  "webrtc:ipv4": "string",
  "webrtc:ipv6": "string",

  // ── media ──
  "codecs:spoof":                              "bool",
  "mediaCapabilities:spoof":                   "bool",
  "mediaFeature:resolution":                   "int",
  "mediaFeature:invertedColors":               "bool",
  "mediaFeature:prefersReducedMotion":         "bool",
  "mediaFeature:prefersReducedTransparency":   "bool",

  // ── speech synthesis ──
  "voices:blockIfNotDefined":             "bool",
  "voices:fakeCompletion":                "bool",
  "voices:fakeCompletion:charsPerSecond": "int",

  // ── hidden surfaces ──
  "permissions:spoof":              "bool",
  "indexedDB:databases:hidden":     "bool",
  "document:lastModified:hidden":   "bool",
  "navigator:vibrate:disabled":     "bool",
  "navigator:webgpu:disabled":      "bool",
};

const overrideBranch = (ucid) => `cloakfox.container.${ucid}.override.`;

/**
 * Read all overrides for a container as a plain object keyed by
 * cloak_cfg key. Type-aware via KEY_TYPES; unknown keys are read as
 * strings so they survive round-trip even if the schema evolves.
 */
export function readOverrides(ucid) {
  const out = {};
  const branch = Services.prefs.getBranch(overrideBranch(ucid));
  for (const child of branch.getChildList("")) {
    const fullName = overrideBranch(ucid) + child;
    const type = KEY_TYPES[child] || "string";
    try {
      if (type === "int") {
        out[child] = Services.prefs.getIntPref(fullName);
      } else if (type === "bool") {
        out[child] = Services.prefs.getBoolPref(fullName);
      } else if (type === "float") {
        // Floats serialize as strings; parse back.
        const s = Services.prefs.getStringPref(fullName, "");
        const f = parseFloat(s);
        if (!Number.isNaN(f)) out[child] = f;
      } else {
        out[child] = Services.prefs.getStringPref(fullName, "");
      }
    } catch (_e) { /* skip malformed */ }
  }
  return out;
}

/**
 * Apply user overrides on top of a base cloak_cfg object. Override
 * values are spread last so they win. Returns a new object.
 */
export function applyOverrides(ucid, baseObj) {
  return { ...baseObj, ...readOverrides(ucid) };
}

/**
 * Set a single override. Throws if the key isn't in KEY_TYPES (helps
 * catch typos in the UI). Pass undefined / null / "" to clear.
 */
export function setOverride(ucid, key, value) {
  if (!(key in KEY_TYPES)) {
    throw new Error(`Unknown cloak_cfg key: ${key}`);
  }
  const fullName = overrideBranch(ucid) + key;
  if (value === undefined || value === null || value === "") {
    Services.prefs.clearUserPref(fullName);
    return;
  }
  const type = KEY_TYPES[key];
  if (type === "int") {
    Services.prefs.setIntPref(fullName, parseInt(value, 10));
  } else if (type === "bool") {
    Services.prefs.setBoolPref(fullName, Boolean(value));
  } else if (type === "float") {
    // Stored as string so the float roundtrips precisely.
    Services.prefs.setStringPref(fullName, String(value));
  } else {
    Services.prefs.setStringPref(fullName, String(value));
  }
}

/** Clear one override (revert to persona value). */
export function clearOverride(ucid, key) {
  Services.prefs.clearUserPref(overrideBranch(ucid) + key);
}

/** Clear ALL overrides for a container. */
export function clearAllOverrides(ucid) {
  const branch = Services.prefs.getBranch(overrideBranch(ucid));
  for (const child of branch.getChildList("")) {
    Services.prefs.clearUserPref(overrideBranch(ucid) + child);
  }
}
