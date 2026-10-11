/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox settings page.
 *
 * Renders every spoofed signal grouped by category. Live values come
 * from the per-container cloak_cfg JSON (Services.prefs.getStringPref
 * "cloakfox.s.cloak_cfg_<ucid>") plus a few per-container prefs
 * (math_seed, persona_index, timezone) and the 10 cloakfox.opt.* flags.
 *
 * The cloak_cfg JSON is the same blob the C++ MaskConfig patches
 * consume — what you see here is exactly what websites see.
 */

/* global Services, ChromeUtils */

import { getPersonaHardwareFamilies, personaOS as sampledOS, personaHardware as sampledHardware } from "resource:///modules/CloakfoxBayesianNetwork.sys.mjs";

import { PRESETS, browserValues, screenValues, languageValues, gpuValues } from "./settings-presets.mjs";

const { ContextualIdentityService } = ChromeUtils.importESModule(
  "resource://gre/modules/ContextualIdentityService.sys.mjs"
);

const { fillPersonaKeys, writeHttpProfilePrefs } = ChromeUtils.importESModule(
  "resource:///modules/CloakfoxPersonas.sys.mjs"
);

// Write a container's cloak_cfg and keep its H2/H3 wire profile coherent
// with the persona in one step. Used by every cloak_cfg (re)write below.
function persistCloakCfg(ucid, seed) {
  const cfg = buildCloakCfg(seed, ucid);
  Services.prefs.setStringPref(cloakCfgPref(ucid), cfg);
  let ua = "";
  try { ua = JSON.parse(cfg)["navigator.userAgent"] || ""; } catch (_e) {}
  writeHttpProfilePrefs(ucid, ua);
}
const { KEY_TYPES, readOverrides, applyOverrides, setOverride, clearOverride, clearAllOverrides } =
  ChromeUtils.importESModule("resource:///modules/CloakfoxOverrides.sys.mjs");

const PREF_ENABLED = "cloakfox.enabled";

async function initAppearanceControls() {
  const { getAppearance, restartAppearance, revealAppearance } = ChromeUtils.importESModule(
    "resource:///modules/CloakfoxAppearance.sys.mjs"
  );
  const toggle = document.getElementById("cfx-firefox-appearance");
  const button = document.getElementById("cfx-appearance-restart");
  const status = document.getElementById("cfx-appearance-status");
  const reveal = document.getElementById("cfx-appearance-reveal");
  const pref = toggle.dataset.pref;
  const appearance = await getAppearance();
  if (!appearance.supported) {
    toggle.disabled = true;
    status.textContent = "Application appearance switching is available on macOS.";
    return;
  }
  const name = appearance.active ? "Firefox" : "Cloakfox";
  reveal.hidden = false;
  document.getElementById("cfx-appearance-permissions").hidden = false;
  reveal.addEventListener("click", async () => {
    try { await revealAppearance(); }
    catch (error) { status.textContent = `Could not show the application: ${error.message}`; }
  });
  document.title = name;
  document.querySelector(".brand-name").textContent = name;
  if (appearance.active) {
    const icon = document.createElement("img");
    icon.src = "resource:///appearance/icon32.png";
    icon.alt = "";
    icon.width = icon.height = 28;
    document.querySelector(".brand-mark").replaceChildren(icon);
  }
  const render = () => {
    const pending = Services.prefs.getBoolPref(pref, false) !== appearance.active;
    status.textContent = `Active: ${name}${pending ? " · Restart to apply your choice." : ""}`;
    button.hidden = !pending;
  };
  toggle.addEventListener("change", render);
  button.addEventListener("click", async () => {
    button.disabled = toggle.disabled = true;
    status.textContent = toggle.checked ? "Preparing Firefox appearance…" : "Restoring Cloakfox appearance…";
    try {
      const result = await restartAppearance();
      if (result.cancelled) {
        status.textContent = `Active: ${name} · Restart canceled. Your choice is saved.`;
      }
    } catch (error) {
      status.textContent = `Could not switch appearance: ${error.message}`;
    } finally {
      button.disabled = toggle.disabled = false;
    }
  });
  render();
}

const masterSeedPref   = (ucid) => `cloakfox.container.${ucid}.math_seed`;
const cloakCfgPref     = (ucid) => `cloakfox.s.cloak_cfg_${ucid}`;
const tzPref           = (ucid) => `cloakfox.container.${ucid}.timezone`;
const personaIndexPref = (ucid) => `cloakfox.container.${ucid}.persona_index`;
const keyboardSeedPref = (ucid) => `cloakfox.container.${ucid}.keyboard_seed`;
const timingSeedPref   = (ucid) => `cloakfox.container.${ucid}.timing_seed`;

// ── seed / config helpers ───────────────────────────────────────────

function randomSeedB64() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes));
}

function u32(seedB64, i) {
  const bin = atob(seedB64);
  const bytes = Uint8Array.from(bin, c => c.charCodeAt(0));
  return new DataView(bytes.buffer).getUint32(i * 4);
}

// MUST match SeedSync.buildCloakCfg shape — see CloakfoxSeedSync.sys.mjs.
function buildCloakCfg(seedB64, ucid = null, constraints = null, clearOverrides = false) {
  const base = {
    "canvas:seed": u32(seedB64, 0),
    "audio:seed": u32(seedB64, 1),
    "font:seed": u32(seedB64, 2),
    // C++ FontSpacingSeedManager reads "fonts:spacing_seed" (plural); the
    // singular key silently no-ops the per-container font-spacing noise.
    "fonts:spacing_seed": u32(seedB64, 3),
    "math:trig_seed": u32(seedB64, 4),
    ...fillPersonaKeys(seedB64, ucid, constraints),
  };
  // Match SeedSync: saved field overrides win over the sampled persona.
  return JSON.stringify(ucid !== null && !clearOverrides ? applyOverrides(ucid, base) : base);
}

// ── container enumeration ──────────────────────────────────────────

function getContainers() {
  const list = [{ ucid: 0, name: "Default (no container)" }];
  try {
    for (const id of ContextualIdentityService.getPublicIdentities()) {
      list.push({ ucid: id.userContextId, name: id.name || `Container ${id.userContextId}` });
    }
  } catch (_e) { /* CIS may be unavailable */ }
  return list;
}

// ── cloak_cfg parsing ──────────────────────────────────────────────

function getCloakCfg(ucid) {
  const raw = Services.prefs.getStringPref(cloakCfgPref(ucid), "");
  if (!raw) return null;
  try { return JSON.parse(raw); } catch (_e) { return null; }
}

// Truncate a long string to display length for readability — full
// value still stored in the title attribute via row creation.
function trunc(s, n = 64) {
  if (typeof s !== "string") return String(s);
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

function fmtSeed(b64) {
  if (!b64) return "(not set)";
  return b64.slice(0, 12) + "…" + b64.slice(-4);
}

// ── grid population ────────────────────────────────────────────────

// Each group is a list of [label, cloak_cfg_key]. Type comes from
// KEY_TYPES (CloakfoxOverrides). Missing keys render as "(not spoofed)"
// so the user can distinguish "not yet generated" from "intentionally
// bypassed". Every key here is editable in-place via the row's edit
// affordance — the input widget is selected by KEY_TYPES[key].
const GROUPS = {
  "grp-navigator": [
    ["navigator.platform",            "navigator.platform"],
    ["navigator.userAgent",           "navigator.userAgent"],
    ["navigator.appVersion",          "navigator.appVersion"],
    ["navigator.oscpu",               "navigator.oscpu"],
    ["navigator.hardwareConcurrency", "navigator.hardwareConcurrency"],
    ["navigator:maxTouchPoints",      "navigator:maxTouchPoints"],
    ["navigator.language",            "navigator.language"],
    ["Accept-Language header",        "headers.Accept-Language"],
    ["Accept-Encoding header",        "headers.Accept-Encoding"],
    ["User-Agent header",             "headers.User-Agent"],
  ],
  "grp-screen": [
    ["screen.width",            "screen.width"],
    ["screen.height",           "screen.height"],
    ["screen.availWidth",       "screen.availWidth"],
    ["screen.availHeight",      "screen.availHeight"],
    ["screen.availLeft",        "screen.availLeft"],
    ["screen.availTop",         "screen.availTop"],
    ["window.outerWidth",       "window.outerWidth"],
    ["window.outerHeight",      "window.outerHeight"],
    ["window.innerWidth",       "window.innerWidth"],
    ["window.innerHeight",      "window.innerHeight"],
    ["window.devicePixelRatio", "window.devicePixelRatio"],
    ["window.screenX",          "window.screenX"],
    ["window.screenY",          "window.screenY"],
    ["screen.orientation.type", "screen:orientation:type"],
  ],
  "grp-graphics": [
    ["webGl.vendor",   "webGl:vendor"],
    ["webGl.renderer", "webGl:renderer"],
  ],
  "grp-audio": [
    ["AudioContext.sampleRate",      "AudioContext:sampleRate"],
    ["AudioContext.maxChannelCount", "AudioContext:maxChannelCount"],
    ["AudioContext.outputLatency",   "AudioContext:outputLatency"],
  ],
  "grp-fonts": [],   // populated below from seeds (no overrides — derived)
  "grp-locale": [
    ["locale.language", "locale:language"],
    ["locale.region",   "locale:region"],
    ["locale.script",   "locale:script"],
  ],
  "grp-geo": [
    ["latitude",  "geolocation:latitude"],
    ["longitude", "geolocation:longitude"],
    ["accuracy",  "geolocation:accuracy"],
  ],
  "grp-network": [   // public IPs sourced from parent sharedData; the
                     // override fields below let the user pin custom ones.
    ["WebRTC IPv4 override", "webrtc:ipv4"],
    ["WebRTC IPv6 override", "webrtc:ipv6"],
  ],
  "grp-media": [
    ["codecs:spoof",                              "codecs:spoof"],
    ["mediaCapabilities:spoof",                   "mediaCapabilities:spoof"],
    ["mediaFeature:resolution",                   "mediaFeature:resolution"],
    ["mediaFeature:invertedColors",               "mediaFeature:invertedColors"],
    ["mediaFeature:prefersReducedMotion",         "mediaFeature:prefersReducedMotion"],
    ["mediaFeature:prefersReducedTransparency",   "mediaFeature:prefersReducedTransparency"],
  ],
  "grp-voices": [
    ["voices:blockIfNotDefined",             "voices:blockIfNotDefined"],
    ["voices:fakeCompletion",                "voices:fakeCompletion"],
    ["voices:fakeCompletion:charsPerSecond", "voices:fakeCompletion:charsPerSecond"],
  ],
  "grp-hidden": [
    ["permissions:spoof",            "permissions:spoof"],
    ["indexedDB:databases:hidden",   "indexedDB:databases:hidden"],
    ["document:lastModified:hidden", "document:lastModified:hidden"],
    ["navigator:vibrate:disabled",   "navigator:vibrate:disabled"],
    ["navigator:webgpu:disabled",    "navigator:webgpu:disabled"],
  ],
};

// Restore the old pickers through the native per-container override store.
const PRESET_GROUPS = {
  "grp-navigator": {id: "browser", label: "Browser / OS preset", items: PRESETS.browsers, values: browserValues},
  "grp-screen": {id: "screen", label: "Display preset", items: PRESETS.screens, values: screenValues},
  "grp-graphics": {id: "gpu", label: "GPU preset", items: PRESETS.gpus.map(p => ({...p, name: p.renderer})), values: gpuValues},
  "grp-locale": {id: "language", label: "Language preset", items: PRESETS.languages, values: languageValues},
};
const FIELD_OPTIONS = {
  "navigator.hardwareConcurrency": PRESETS.cores,
  "navigator:maxTouchPoints": [0, 1, 5, 10],
  "navigator.platform": ["Win32", "MacIntel", "Linux x86_64", "Linux armv8l", "iPhone", "iPad"],
  "window.devicePixelRatio": [1, 1.25, 1.5, 2, 3],
  "screen:orientation:type": ["landscape-primary", "portrait-primary", "landscape-secondary", "portrait-secondary"],
  "AudioContext:sampleRate": [44100, 48000, 96000],
  "AudioContext:maxChannelCount": [1, 2, 6, 8],
};

function makePresetRow(definition, cfg, ucid, overrides, onChange) {
  const row = document.createElement("div");
  row.className = "spoof-row dyn picker-row";
  const label = document.createElement("label");
  label.className = "k";
  label.textContent = definition.label;
  const select = document.createElement("select");
  select.id = `cfx-${definition.id}-preset`;
  select.className = "v preset-select";
  label.htmlFor = select.id;
  const ownedKeys = Object.keys(definition.values(definition.items[0], cfg || {}));
  const automatic = document.createElement("option");
  automatic.value = "auto";
  automatic.textContent = "Automatic — from persona";
  select.appendChild(automatic);
  const custom = document.createElement("option");
  custom.value = "custom";
  custom.textContent = "Custom / current values — edit fields below";
  select.appendChild(custom);
  const presetPref = `cloakfox.container.${ucid}.settings_preset.${definition.id}`;
  const preferred = Services.prefs.getStringPref(presetPref, "");
  let match = null;
  for (const item of definition.items) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.name;
    select.appendChild(option);
    const values = definition.values(item, cfg || {});
    if (Object.entries(values).every(([key, value]) => cfg?.[key] === value)
        && (!match || item.id === preferred)) match = item.id;
  }
  select.value = ownedKeys.some(key => key in overrides) ? (match || "custom") : "auto";
  select.addEventListener("change", () => {
    if (select.value === "custom") return;
    if (select.value === "auto") {
      ownedKeys.forEach(key => clearOverride(ucid, key));
      Services.prefs.clearUserPref(presetPref);
    }
    else {
      Services.prefs.setStringPref(presetPref, select.value);
      const item = definition.items.find(p => p.id === select.value);
      for (const [key, value] of Object.entries(definition.values(item, cfg || {}))) setOverride(ucid, key, value);
    }
    onChange();
  });
  row.append(label, select, document.createElement("span"));
  return row;
}

// Boolean cloak_cfg keys render presence-as-on. Absence = no spoof.
function fmtValue(key, v) {
  if (v === undefined || v === null || v === "") return "(not spoofed)";
  if (KEY_TYPES[key] === "bool") return v ? "spoofed (on)" : "off";
  return String(v);
}

// Build an editable row. UX:
//   • Click the VALUE to edit — no separate edit button.
//   • Text/number inputs auto-save on blur (no save button to click).
//   • Booleans are inline cycle buttons: click → cycles between
//     "spoofed (on)" / "off" / "auto (from persona)" with no popup.
//   • Overridden rows show a small × at the end to reset to persona.
function makeRow(label, key, cfg, ucid, overrides, onChange) {
  const row = document.createElement("div");
  row.className = "spoof-row dyn";

  const k = document.createElement("span");
  k.className = "k";
  k.textContent = label;
  k.title = key;

  const rawVal = cfg ? cfg[key] : undefined;
  const isBool = KEY_TYPES[key] === "bool";

  const v = document.createElement(isBool ? "button" : "span");
  v.className = "v";
  if (isBool) v.type = "button";
  const sval = fmtValue(key, rawVal);
  v.textContent = trunc(sval, 80);
  v.title = String(rawVal ?? sval);
  if (sval === "(not spoofed)") v.classList.add("v-empty");
  if (key in overrides) v.classList.add("v-overridden");

  const actions = document.createElement("span");
  actions.className = "row-actions";

  if (key in overrides) {
    const resetBtn = document.createElement("button");
    resetBtn.type = "button";
    resetBtn.className = "row-reset-x";
    resetBtn.textContent = "×";
    resetBtn.title = "Reset to persona value";
    resetBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      clearOverride(ucid, key);
      onChange();
    });
    actions.appendChild(resetBtn);
  }

  if (isBool) {
    // Click cycles: spoofed(true) → off(false) → auto(unset) → spoofed
    v.addEventListener("click", () => {
      const cur = (key in overrides) ? overrides[key] : (rawVal ? true : (rawVal === false ? false : null));
      let next;
      if (cur === true) next = false;
      else if (cur === false) next = null;
      else next = true;
      if (next === null) clearOverride(ucid, key);
      else setOverride(ucid, key, next);
      onChange();
    });
  } else {
    v.addEventListener("click", openEditMode);
    if (FIELD_OPTIONS[key]) {
      const picker = document.createElement("select");
      picker.className = "field-preset";
      picker.setAttribute("aria-label", `${label} preset`);
      const custom = document.createElement("option");
      custom.value = "custom"; custom.textContent = "Custom…";
      picker.appendChild(custom);
      for (const value of FIELD_OPTIONS[key]) {
        const option = document.createElement("option");
        option.value = String(value); option.textContent = String(value);
        picker.appendChild(option);
      }
      picker.value = FIELD_OPTIONS[key].some(value => value === rawVal) ? String(rawVal) : "custom";
      picker.addEventListener("change", () => {
        if (picker.value === "custom") openEditMode();
        else { setOverride(ucid, key, picker.value); onChange(); }
      });
      actions.prepend(picker);
    }
  }

  function openEditMode() {
    const existing = (key in overrides) ? overrides[key] : (rawVal ?? "");
    const initialValue = String(existing);
    const isLong = initialValue.length > 50
      || /^(headers\.|navigator\.user(Agent|Version)|navigator\.oscpu|webGl:renderer)/.test(key);
    const input = document.createElement(isLong ? "textarea" : "input");
    if (input.tagName === "INPUT") {
      input.type = (KEY_TYPES[key] === "int" || KEY_TYPES[key] === "float") ? "number" : "text";
      if (KEY_TYPES[key] === "float") input.step = "any";
    } else {
      input.rows = Math.min(6, Math.max(2, Math.ceil(initialValue.length / 60)));
    }
    input.value = initialValue;
    input.className = "row-input";
    v.replaceWith(input);

    let committed = false;
    function commit() {
      if (committed) return;
      committed = true;
      if (input.value !== initialValue) {
        setOverride(ucid, key, input.value);
        onChange();
      } else {
        onChange();   // re-render to swap input back to value pill
      }
    }
    function cancel() {
      if (committed) return;
      committed = true;
      onChange();
    }

    input.focus();
    if (input.tagName === "INPUT") input.select();
    input.addEventListener("blur", commit);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && input.tagName !== "TEXTAREA") {
        e.preventDefault(); commit();
      } else if (e.key === "Escape") {
        e.preventDefault(); cancel();
      }
    });
  }

  row.appendChild(k);
  row.appendChild(v);
  row.appendChild(actions);
  return row;
}

function populateGrid(id, cfg, rows, ucid, overrides, onChange) {
  const grid = document.getElementById(id);
  if (!grid) return;
  // Clear existing children EXCEPT static elements declared in HTML
  // (e.g. timezone group has a <select>; we never wipe that).
  Array.from(grid.querySelectorAll(".spoof-row.dyn")).forEach(n => n.remove());
  if (PRESET_GROUPS[id] && id !== "grp-navigator") grid.appendChild(makePresetRow(PRESET_GROUPS[id], cfg, ucid, overrides, onChange));
  for (const [label, key] of rows) {
    grid.appendChild(makeRow(label, key, cfg, ucid, overrides, onChange));
  }
}

function populateFonts(cfg, ucid) {
  const seedB64 = Services.prefs.getStringPref(masterSeedPref(ucid), "");
  const rows = [
    ["font:seed (ordering)", cfg ? cfg["font:seed"] : null],
    ["fonts:spacing_seed",   cfg ? cfg["fonts:spacing_seed"] : null],
    ["master seed (drives both)", fmtSeed(seedB64)],
  ];
  const grid = document.getElementById("grp-fonts");
  Array.from(grid.querySelectorAll(".spoof-row.dyn")).forEach(n => n.remove());
  for (const [label, value] of rows) {
    const row = makeRow(label, value);
    row.classList.add("dyn");
    grid.appendChild(row);
  }
}

// Seeds are derived from the master seed (regenerating rolls them all
// together) so the rows are read-only — render manually instead of
// going through makeRow's editable path.
function populateSeeds(cfg, ucid) {
  const seedB64 = Services.prefs.getStringPref(masterSeedPref(ucid), "");
  const kbd = Services.prefs.getStringPref(keyboardSeedPref(ucid), "");
  const tim = Services.prefs.getStringPref(timingSeedPref(ucid), "");
  const rows = [
    ["master seed (32 bytes)",  fmtSeed(seedB64)],
    ["canvas:seed (u32)",       cfg ? cfg["canvas:seed"] : null],
    ["audio:seed (u32)",        cfg ? cfg["audio:seed"] : null],
    ["font:seed (u32)",         cfg ? cfg["font:seed"] : null],
    ["fonts:spacing_seed (u32)", cfg ? cfg["fonts:spacing_seed"] : null],
    ["math:trig_seed (u32)",    cfg ? cfg["math:trig_seed"] : null],
    ["keyboard timing seed",    fmtSeed(kbd)],
    ["setTimeout jitter seed",  fmtSeed(tim)],
  ];
  const grid = document.getElementById("grp-seeds");
  if (!grid) return;
  Array.from(grid.querySelectorAll(".spoof-row.dyn")).forEach(n => n.remove());
  for (const [label, value] of rows) {
    const row = document.createElement("div");
    row.className = "spoof-row dyn";
    const k = document.createElement("span"); k.className = "k"; k.textContent = label;
    const v = document.createElement("span"); v.className = "v";
    const sval = (value === null || value === undefined || value === "") ? "(not set)" : String(value);
    v.textContent = sval;
    if (sval === "(not set)") v.classList.add("v-empty");
    const actions = document.createElement("span"); actions.className = "row-actions";
    row.appendChild(k); row.appendChild(v); row.appendChild(actions);
    grid.appendChild(row);
  }
}

// Auto-detected public IPs from CloakfoxWebRTCSync (parent process,
// via Services.ppmm.sharedData). These show what the host actually
// leaks through WebRTC ICE candidates by default; the override fields
// in grp-network let the user pin different values.
function updateAutoDetectedIPs() {
  const v4 = Services.ppmm.sharedData.get("cloakfox-public-ipv4") || "(not yet detected)";
  const v6 = Services.ppmm.sharedData.get("cloakfox-public-ipv6") || "(not yet detected)";
  const el = document.getElementById("cfx-network-detected");
  if (el) el.textContent = `Auto-detected — IPv4: ${v4} · IPv6: ${v6}`;
}

// ── headline summary ───────────────────────────────────────────────

// 6-char hex tag derived from the master seed's first 3 bytes. Lets
// the user tell two visually-similar personas apart at a glance —
// regenerating always changes the seed, so the tag always changes too,
// even when BF happens to sample a similar persona.
function shortSeedTag(seedB64) {
  if (!seedB64) return "";
  try {
    const bin = atob(seedB64);
    const hex = [0, 1, 2]
      .map(i => bin.charCodeAt(i).toString(16).padStart(2, "0"))
      .join("");
    return "#" + hex;
  } catch (_e) { return ""; }
}

function updateHeadline(cfg, seedB64) {
  const el = document.getElementById("cfx-headline-text");
  if (!cfg) { el.textContent = "(not yet generated — click Regenerate)"; return; }
  const platform = cfg["navigator.platform"] || "?";
  const w = cfg["screen.width"] ?? "?";
  const h = cfg["screen.height"] ?? "?";
  const rawDpr = cfg["window.devicePixelRatio"];
  const dpr = typeof rawDpr === "number" ? Number(rawDpr.toFixed(2)) : "?";
  const hwc = cfg["navigator.hardwareConcurrency"] ?? "?";
  const renderer = (cfg["webGl:renderer"] || "?").slice(0, 50);
  const tag = shortSeedTag(seedB64);
  el.textContent = `${platform} · ${w}×${h}@${dpr}x · ${hwc}-core · ${renderer}${tag ? "  " + tag : ""}`;
}

// ── timezone list ───────────────────────────────────────────────────

const TIMEZONES = [
  "UTC",
  "America/Los_Angeles", "America/Denver", "America/Chicago", "America/New_York",
  "America/Toronto", "America/Sao_Paulo", "America/Mexico_City",
  "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Moscow",
  "Asia/Tokyo", "Asia/Shanghai", "Asia/Singapore", "Asia/Kolkata", "Asia/Dubai",
  "Australia/Sydney", "Pacific/Auckland",
];

// ── wire up UI ──────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  function updateChromiumCompatibility() {
    const ucid = parseInt(document.getElementById("cfx-container-select").value, 10) || 0;
    const ua = getCloakCfg(ucid)?.["navigator.userAgent"] || "";
    // Match the native desktop Chromium eligibility gate, including custom UAs.
    const chromium = /(?:Chrome|Chromium)\/\d/.test(ua)
      && !/(?:Firefox\/|iPhone|iPad|Android|Mobile)/.test(ua);
    document.getElementById("sec-screen-management").hidden = !chromium;
    document.querySelector('a[href="#sec-screen-management"]').hidden = !chromium;
    const status = document.getElementById("cfx-chromium-status");
    if (!chromium) {
      status.textContent = "Choose a desktop Chrome or Edge identity to configure Chromium compatibility. Saved settings are retained.";
    } else if (!Services.prefs.getBoolPref(PREF_ENABLED, false)) {
      status.textContent = "Unavailable: enable Cloakfox to activate Chromium compatibility.";
    } else if (!Services.prefs.getBoolPref("cloakfox.compat.screen_management", false)) {
      status.textContent = "Unavailable: turn on the Screen API toggle below.";
    } else {
      try {
        const origins = JSON.parse(Services.prefs.getStringPref("cloakfox.compat.screen_management.origins", "[]"));
        if (!Array.isArray(origins)) throw new Error("Invalid origins");
        const count = new Set(origins.filter(value => {
          if (typeof value !== "string") return false;
          const url = new URL(value);
          return url.protocol === "https:" && url.origin === value && !url.hostname.includes("*");
        })).size;
        status.textContent = count ? `Enabled for ${count} allowed site${count === 1 ? "" : "s"} in this container. Reload affected pages to apply changes.`
          : "Unavailable: add an HTTPS site to the allowlist below.";
      } catch {
        status.textContent = "Unavailable: correct and save the site allowlist below.";
      }
    }
  }

  // Section links reveal the destination before the browser scrolls to it.
  function revealSection() {
    const section = document.getElementById(location.hash.slice(1));
    const group = section?.closest("details.settings-group");
    if (group) group.open = true;
  }
  document.querySelector(".section-nav").addEventListener("click", event => {
    const link = event.target.closest("a");
    const section = link && document.getElementById(link.hash.slice(1));
    const group = section?.closest("details.settings-group");
    if (group) group.open = true;
  });
  window.addEventListener("hashchange", revealSection);
  revealSection();

  const enabledEl    = document.getElementById("cfx-enabled");
  const statusLabel  = document.getElementById("cfx-status-label");
  const selectEl     = document.getElementById("cfx-container-select");
  const tzSelectEl   = document.getElementById("cfx-tz-select");
  const tzCurrentEl  = document.getElementById("cfx-tz-current");
  const regenBtn     = document.getElementById("cfx-regenerate");
  const clearBtn     = document.getElementById("cfx-clear");

  // Master enable.
  function syncStatus() {
    const on = Services.prefs.getBoolPref(PREF_ENABLED, false);
    enabledEl.checked = on;
    if (statusLabel) statusLabel.textContent = on ? "Enabled" : "Disabled";
    updateChromiumCompatibility();
  }
  syncStatus();
  enabledEl.addEventListener("change", () => {
    Services.prefs.setBoolPref(PREF_ENABLED, enabledEl.checked);
    syncStatus();
  });

  const personaOS = document.getElementById("cfx-persona-os");
  const personaHardware = document.getElementById("cfx-persona-hardware");
  const generationStatus = document.getElementById("cfx-generation-status");
  const hardwareLabels = {apple: "Apple graphics", intel: "Intel graphics", nvidia: "NVIDIA", amd: "AMD / Radeon", software: "Software rendering", other: "Other graphics"};
  let draftContainer = null;
  function updateHardwareChoices(selected = "auto") {
    personaHardware.replaceChildren();
    const automatic = document.createElement("option");
    automatic.value = "auto";
    automatic.textContent = "Automatic — any supported family";
    personaHardware.appendChild(automatic);
    for (const family of getPersonaHardwareFamilies(personaOS.value)) {
      const option = document.createElement("option");
      option.value = family; option.textContent = hardwareLabels[family];
      personaHardware.appendChild(option);
    }
    personaHardware.value = Array.from(personaHardware.options).some(o => o.value === selected) ? selected : "auto";
  }
  personaOS.addEventListener("change", () => {
    updateHardwareChoices(personaHardware.value);
    generationStatus.textContent = "Selection ready. Click Generate new persona to apply it.";
  });
  personaHardware.addEventListener("change", () => {
    generationStatus.textContent = "Selection ready. Click Generate new persona to apply it.";
  });

  // Container dropdown.
  for (const c of getContainers()) {
    const opt = document.createElement("option");
    opt.value = String(c.ucid);
    opt.textContent = c.name;
    selectEl.appendChild(opt);
  }
  if (selectEl.options.length > 1 && selectEl.options[0].value === "0" &&
      selectEl.options[1].value === "0") {
    selectEl.options[0].remove();
  }
  // ?ucid=N deep-link from the popup.
  try {
    const requested = new URLSearchParams(window.location.search).get("ucid");
    if (requested !== null) {
      const target = String(parseInt(requested, 10) || 0);
      if (Array.from(selectEl.options).some(o => o.value === target)) {
        selectEl.value = target;
      }
    }
  } catch (_e) { /* deep-link is best-effort */ }

  // Timezone dropdown.
  for (const tz of TIMEZONES) {
    const opt = document.createElement("option");
    opt.value = tz;
    opt.textContent = tz;
    tzSelectEl.appendChild(opt);
  }

  // Editing a field rewrites cloak_cfg so the change takes effect for
  // new tabs immediately, then refreshes the UI to show the new state.
  function rebuildCloakCfg(ucid) {
    const seed = Services.prefs.getStringPref(masterSeedPref(ucid), "");
    if (seed) {
      persistCloakCfg(ucid, seed);
    }
  }

  function refreshContainer() {
    const ucid = parseInt(selectEl.value, 10) || 0;
    if (draftContainer !== ucid) {
      draftContainer = ucid;
      const savedOS = Services.prefs.getStringPref(`cloakfox.container.${ucid}.persona_os`, "auto");
      personaOS.value = ["auto", "windows", "macos", "linux"].includes(savedOS) ? savedOS : "auto";
      updateHardwareChoices(Services.prefs.getStringPref(`cloakfox.container.${ucid}.persona_hardware`, "auto"));
      generationStatus.textContent = "";
    }
    const cfg = getCloakCfg(ucid);
    const overrides = readOverrides(ucid);
    const seedB64 = Services.prefs.getStringPref(masterSeedPref(ucid), "");
    const onEdit = () => { rebuildCloakCfg(ucid); refreshContainer(); };

    updateHeadline(cfg, seedB64);
    const browserPresets = document.getElementById("grp-browser-presets");
    browserPresets.replaceChildren(makePresetRow(PRESET_GROUPS["grp-navigator"], cfg, ucid, overrides, onEdit));
    updateChromiumCompatibility();
    populateGrid("grp-navigator", cfg, GROUPS["grp-navigator"], ucid, overrides, onEdit);
    populateGrid("grp-screen",    cfg, GROUPS["grp-screen"],    ucid, overrides, onEdit);
    populateGrid("grp-graphics",  cfg, GROUPS["grp-graphics"],  ucid, overrides, onEdit);
    populateGrid("grp-audio",     cfg, GROUPS["grp-audio"],     ucid, overrides, onEdit);
    populateGrid("grp-locale",    cfg, GROUPS["grp-locale"],    ucid, overrides, onEdit);
    populateGrid("grp-geo",       cfg, GROUPS["grp-geo"],       ucid, overrides, onEdit);
    populateGrid("grp-network",   cfg, GROUPS["grp-network"],   ucid, overrides, onEdit);
    populateGrid("grp-media",     cfg, GROUPS["grp-media"],     ucid, overrides, onEdit);
    populateGrid("grp-voices",    cfg, GROUPS["grp-voices"],    ucid, overrides, onEdit);
    populateGrid("grp-hidden",    cfg, GROUPS["grp-hidden"],    ucid, overrides, onEdit);
    updateAutoDetectedIPs();
    populateSeeds(cfg, ucid);

    tzCurrentEl.textContent = Services.prefs.getStringPref(tzPref(ucid), "") || "UTC (default)";
    tzSelectEl.value = Services.prefs.getStringPref(tzPref(ucid), "");

    // Show "N overrides active" indicator + clear-all button.
    const overrideCount = Object.keys(overrides).length;
    const indicator = document.getElementById("cfx-override-count");
    const clearOvBtn = document.getElementById("cfx-clear-overrides");
    if (indicator) {
      indicator.textContent = overrideCount === 0
        ? "No field overrides — every value comes from the persona."
        : `${overrideCount} field override${overrideCount === 1 ? "" : "s"} active.`;
      indicator.dataset.count = String(overrideCount);
    }
    if (clearOvBtn) clearOvBtn.hidden = overrideCount === 0;
  }
  selectEl.addEventListener("change", refreshContainer);
  refreshContainer();

  // Timezone picker.
  tzSelectEl.addEventListener("change", () => {
    const ucid = parseInt(selectEl.value, 10) || 0;
    if (tzSelectEl.value === "") {
      Services.prefs.clearUserPref(tzPref(ucid));
    } else {
      Services.prefs.setStringPref(tzPref(ucid), tzSelectEl.value);
    }
    refreshContainer();
  });

  // Regenerate persona — same path as SeedSync; ucid forwarded so any
  // per-container override prefs are honored. Flash the headline on
  // update so the user has visible confirmation. Errors surface via
  // Cu.reportError so a silent build failure doesn't look like the
  // button does nothing.
  regenBtn.addEventListener("click", () => {
    try {
      const ucid = parseInt(selectEl.value, 10) || 0;
      const seed = randomSeedB64();
      const filters = {os: personaOS.value, hardware: personaHardware.value};
      const clearFields = document.getElementById("cfx-generation-clear-overrides").checked;
      // Validate and sample before touching any saved configuration.
      const generated = JSON.parse(buildCloakCfg(seed, ucid, filters, true));
      if ((filters.os !== "auto" && sampledOS(generated["navigator.userAgent"]) !== filters.os)
          || (filters.hardware !== "auto" && sampledHardware(generated["webGl:renderer"]) !== filters.hardware)) {
        throw new Error("The generator returned a different OS or hardware family. No changes saved; the browser needs to load its updated generator.");
      }
      const cfg = JSON.stringify(clearFields ? generated : applyOverrides(ucid, generated));
      if (clearFields) clearAllOverrides(ucid);
      Services.prefs.clearUserPref(personaIndexPref(ucid));
      Services.prefs.setStringPref(`cloakfox.container.${ucid}.persona_os`, filters.os);
      Services.prefs.setStringPref(`cloakfox.container.${ucid}.persona_hardware`, filters.hardware);
      Services.prefs.setStringPref(masterSeedPref(ucid), seed);
      Services.prefs.setStringPref(cloakCfgPref(ucid), cfg);
      writeHttpProfilePrefs(ucid, JSON.parse(cfg)["navigator.userAgent"] || "");
      refreshContainer();
      generationStatus.textContent = clearFields
        ? "New persona saved. Field overrides cleared. Reload affected websites to apply it."
        : "New persona saved. Existing field overrides kept; they can replace generated values. Reload affected websites to apply it.";
      const hero = document.querySelector(".hero");
      if (hero) {
        hero.classList.remove("hero-flash");
        void hero.offsetWidth;
        hero.classList.add("hero-flash");
      }
    } catch (e) {
      generationStatus.textContent = "Generation failed: " + e.message;
      Cu.reportError("Cloakfox regenerate failed: " + e.message + "\n" + e.stack);
      const note = document.createElement("p");
      note.className = "card-note";
      note.style.color = "var(--danger)";
      note.textContent = "Generation failed: " + e.message + " (see Browser Console)";
      regenBtn.parentElement.appendChild(note);
    }
  });

  // Clear — strips seeds, cloak_cfg, timezone, persona override, AND
  // every per-field override so the container falls back to host's
  // real values.
  clearBtn.addEventListener("click", () => {
    const ucid = parseInt(selectEl.value, 10) || 0;
    Services.prefs.clearUserPref(masterSeedPref(ucid));
    Services.prefs.clearUserPref(cloakCfgPref(ucid));
    Services.prefs.clearUserPref(tzPref(ucid));
    Services.prefs.clearUserPref(personaIndexPref(ucid));
    Services.prefs.clearUserPref(`cloakfox.container.${ucid}.persona_os`);
    Services.prefs.clearUserPref(`cloakfox.container.${ucid}.persona_hardware`);
    draftContainer = null;
    clearAllOverrides(ucid);
    refreshContainer();
  });

  // Clear-all-overrides button — keeps the persona/seed but drops
  // every field-level pin. Useful after experimenting with overrides.
  const clearOverridesBtn = document.getElementById("cfx-clear-overrides");
  if (clearOverridesBtn) {
    clearOverridesBtn.addEventListener("click", () => {
      const ucid = parseInt(selectEl.value, 10) || 0;
      clearAllOverrides(ucid);
      const seed = Services.prefs.getStringPref(masterSeedPref(ucid), "");
      if (seed) {
        persistCloakCfg(ucid, seed);
      }
      refreshContainer();
    });
  }

  const screenCountPref = "cloakfox.compat.screen_management.screen_count";
  const screenOriginsPref = "cloakfox.compat.screen_management.origins";
  const countSelect = document.getElementById("cfx-screen-count");
  const savedCount = Services.prefs.getIntPref(screenCountPref, 1);
  countSelect.value = String(savedCount >= 1 && savedCount <= 8 ? savedCount : 1);
  countSelect.addEventListener("change", () => {
    Services.prefs.setIntPref(screenCountPref, Number(countSelect.value));
  });
  const originsEditor = document.getElementById("cfx-screen-origins");
  const originsStatus = document.getElementById("cfx-screen-origins-status");
  try {
    if (Services.prefs.getPrefType(screenOriginsPref) !== Services.prefs.PREF_STRING) {
      throw new Error("Expected saved origins to be a string.");
    }
    const saved = JSON.parse(Services.prefs.getStringPref(screenOriginsPref, "[]"));
    if (!Array.isArray(saved) || saved.some(value => typeof value !== "string")) {
      throw new Error("Expected a JSON array of origins.");
    }
    originsEditor.value = saved.join("\n");
  } catch (error) {
    originsStatus.textContent = `Could not read saved origins: ${error.message}`;
  }
  document.getElementById("cfx-screen-origins-save").addEventListener("click", () => {
    try {
      const origins = [];
      for (const [index, line] of originsEditor.value.split(/\r?\n/).entries()) {
        const value = line.trim();
        if (!value) continue;
        let url;
        try { url = new URL(value); }
        catch { throw new Error(`Line ${index + 1}: enter a complete HTTPS origin.`); }
        if (url.protocol !== "https:" || url.username || url.password ||
            url.pathname !== "/" || url.search || url.hash ||
            !url.hostname || url.hostname.includes("*")) {
          throw new Error(`Line ${index + 1}: use an exact HTTPS origin without a path or wildcard.`);
        }
        if (!origins.includes(url.origin)) origins.push(url.origin);
      }
      Services.prefs.setStringPref(screenOriginsPref, JSON.stringify(origins));
      originsEditor.value = origins.join("\n");
      originsStatus.textContent = "Saved. Reload affected pages to update API availability.";
      updateChromiumCompatibility();
    } catch (error) {
      originsStatus.textContent = error.message;
    }
  });
  document.getElementById("cfx-screen-origins-reset").addEventListener("click", () => {
    Services.prefs.setStringPref(screenOriginsPref, '["https://app.testdome.com"]');
    originsEditor.value = "https://app.testdome.com";
    originsStatus.textContent = "Origins reset. Reload affected pages to update API availability.";
    updateChromiumCompatibility();
  });

  // Opt-in flag toggles auto-bind via data-pref.
  for (const el of document.querySelectorAll("input[data-pref]")) {
    const pref = el.dataset.pref;
    el.checked = Services.prefs.getBoolPref(pref, false);
    el.addEventListener("change", () => {
      Services.prefs.setBoolPref(pref, el.checked);
      if (pref === "cloakfox.compat.screen_management") updateChromiumCompatibility();
    });
  }
  initAppearanceControls().catch(error => {
    document.getElementById("cfx-appearance-status").textContent = `Could not read application appearance: ${error.message}`;
  });
});
