import { createGPUProfile } from "resource:///modules/CloakfoxGPUProfiles.sys.mjs";
import { applyRegion } from "resource:///modules/CloakfoxRegions.sys.mjs";
import { applyPrivacyPolicy } from "resource:///modules/CloakfoxPrivacyPolicy.sys.mjs";
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
  "fonts:spacing_seed": "int",
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
  "mediaDevices:enabled": "bool",
  "mediaDevices:micros": "int",
  "mediaDevices:webcams": "int",
  "mediaDevices:cameraDevice": "string",
  "mediaDevices:cameraDevices": "string",
  "mediaDevices:microphoneDevices": "string",
  "mediaDevices:speakers": "int",
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

// Graphics opt-ins are global policy, not per-field identity overrides. Apply
// last so stale imported override keys cannot enable or disable a mode.
// Missing or malformed preferences select the existing protected behavior.
export function applyGraphicsPolicy(config, owner = null, allowUnavailable = false) {
  const result = { ...config };
  for (const [name, key] of [
    ["cloakfox.opt.canvas_render_privacy", "canvas:render_privacy"],
    ["cloakfox.opt.gpu_backend_profiles", "webGl:backend_profile"],
    ["cloakfox.experimental.canvas_pipeline", "canvas:canonical_2d"],
    ["cloakfox.experimental.canvas_pipeline", "canvas:canonical_gpu"],
  ]) {
    let enabled = false;
    try {
      enabled = Services.prefs.getBoolPref(name, false) === true;
    } catch (_e) { /* invalid preference type keeps the opt-in disabled */ }
    result[key] = enabled;
  }
  // A CPU shader backend must not advertise the saved hardware profile.
  if (result["canvas:canonical_gpu"]) {
    result["webGl:backend_profile"] = true;
    result["webgl:typed_readback:disabled"] = true;
  }
  let containerProfiles = false;
  try { containerProfiles = Services.prefs.getBoolPref("cloakfox.opt.container_rendering_profiles", false); } catch (_) { /* malformed opt-in stays off */ }
  if (containerProfiles) {
    if (!result["canvas:canonical_gpu"]) throw new Error("Container GPU profiles require canonical software rendering");
    try {
      result["rendering:gpu_profile"] = createGPUProfile(result, owner);
      delete result["rendering:gpu_profile:error"];
    } catch (error) {
      if (!allowUnavailable) throw error;
      // A newly created unsupported persona still needs its navigator/font/
      // network masks. Refuse GPU creation via the absent owned descriptor.
      delete result["rendering:gpu_profile"];
      result["rendering:gpu_profile:error"] = error.message;
    }
  }
  return result;
}

export function setContainerGPUProfilesEnabled(enabled) {
  if (typeof enabled !== "boolean") throw new Error("GPU profile toggle requires a boolean");
  if (enabled) {
    if (!Services.prefs.getBoolPref("cloakfox.experimental.canvas_pipeline", false)) throw new Error("Enable canonical software rendering first");
    const prefs = Services.prefs.getChildList("cloakfox.s.cloak_cfg_").filter(p => /^cloakfox\.s\.cloak_cfg_(0|[1-9]\d*)$/.test(p));
    if (!prefs.length) throw new Error("No container personas are ready");
    for (const pref of prefs) {
      const owner = Number(pref.slice("cloakfox.s.cloak_cfg_".length));
      createGPUProfile(JSON.parse(Services.prefs.getStringPref(pref)), owner);
    }
  }
  Services.prefs.setBoolPref("cloakfox.opt.container_rendering_profiles", enabled === true);
}

/**
 * Apply user overrides on top of a base cloak_cfg object. Override
 * values win over persona fields; global graphics policy is applied last.
 * Returns a new object.
 */
export function applyOverrides(ucid, baseObj, overrides = readOverrides(ucid), allowUnavailable = false) {
  return applyGraphicsPolicy(applyPrivacyPolicy(ucid, applyRegion(ucid, { ...baseObj, ...overrides })), ucid, allowUnavailable);
}

/**
 * Set a single override. Throws if the key isn't in KEY_TYPES (helps
 * catch typos in the UI). Pass undefined / null / "" to clear.
 */
export function setOverride(ucid, key, value) {
  return setOverrides(ucid, { [key]: value });
}

/** Validate a complete preset/reset before writing any of its fields. */
export function setOverrides(ucid, changes) {
  for (const [key, value] of Object.entries(changes)) {
    if (!(key in KEY_TYPES)) throw new Error(`Unknown cloak_cfg key: ${key}`);
    if (value === undefined || value === null || value === "") continue;
    if (["int", "float"].includes(KEY_TYPES[key]) && !Number.isFinite(Number(value))) throw new Error("Invalid numeric override");
    if (KEY_TYPES[key] === "int" && !Number.isInteger(Number(value))) throw new Error("Invalid integer override");
    if (["mediaDevices:micros", "mediaDevices:webcams", "mediaDevices:speakers"].includes(key) && (Number(value) < 0 || Number(value) > 64)) throw new Error("Media-device limits must be between 0 and 64");
  }
  let active = false;
  try { active = Services.prefs.getBoolPref("cloakfox.opt.container_rendering_profiles", false); } catch (_) {}
  if (active) {
    const current = JSON.parse(Services.prefs.getStringPref(`cloakfox.s.cloak_cfg_${ucid}`));
    const { fillPersonaKeys } = ChromeUtils.importESModule("resource:///modules/CloakfoxPersonas.sys.mjs");
    const seed = Services.prefs.getStringPref(`cloakfox.container.${ucid}.math_seed`);
    const overrides = readOverrides(ucid);
    for (const [key, value] of Object.entries(changes)) {
      if (value === undefined || value === null || value === "") delete overrides[key];
      else overrides[key] = ["int", "float"].includes(KEY_TYPES[key]) ? Number(value) : value;
    }
    applyOverrides(ucid, { ...current, ...fillPersonaKeys(seed, ucid) }, overrides);
  }
  for (const [key, value] of Object.entries(changes)) writeOverride(ucid, key, value);
}

function writeOverride(ucid, key, value) {
  const fullName = overrideBranch(ucid) + key;
  if (value === undefined || value === null || value === "") {
    Services.prefs.clearUserPref(fullName);
    return;
  }
  const type = KEY_TYPES[key];
  if (["mediaDevices:micros", "mediaDevices:webcams", "mediaDevices:speakers"].includes(key)) {
    const count = Number(value);
    if (!Number.isInteger(count) || count < 0 || count > 64) {
      throw new Error("Media-device limits must be between 0 and 64");
    }
    Services.prefs.setIntPref(fullName, count);
    return;
  }
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
  validateClearedOverrides(ucid, key);
  Services.prefs.clearUserPref(overrideBranch(ucid) + key);
}

/** Clear ALL overrides for a container. */
export function clearAllOverrides(ucid) {
  validateClearedOverrides(ucid);
  const branch = Services.prefs.getBranch(overrideBranch(ucid));
  for (const child of branch.getChildList("")) {
    Services.prefs.clearUserPref(overrideBranch(ucid) + child);
  }
}

function validateClearedOverrides(ucid, key = null) {
  let active = false;
  try { active = Services.prefs.getBoolPref("cloakfox.opt.container_rendering_profiles", false); } catch (_) {}
  if (!active) return;
  const current = JSON.parse(Services.prefs.getStringPref(`cloakfox.s.cloak_cfg_${ucid}`));
  const { fillPersonaKeys } = ChromeUtils.importESModule("resource:///modules/CloakfoxPersonas.sys.mjs");
  const seed = Services.prefs.getStringPref(`cloakfox.container.${ucid}.math_seed`);
  const overrides = key === null ? {} : readOverrides(ucid);
  if (key !== null) delete overrides[key];
  applyOverrides(ucid, { ...current, ...fillPersonaKeys(seed, ucid) }, overrides);
}
