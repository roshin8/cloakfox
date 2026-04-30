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

const { fillPersonaKeys } = ChromeUtils.importESModule(
  "resource:///modules/CloakfoxPersonas.sys.mjs"
);
const { KEY_TYPES, readOverrides, setOverride, clearOverride, clearAllOverrides } =
  ChromeUtils.importESModule("resource:///modules/CloakfoxOverrides.sys.mjs");

const PREF_ENABLED = "cloakfox.enabled";

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
function buildCloakCfg(seedB64, ucid = null) {
  return JSON.stringify({
    "canvas:seed": u32(seedB64, 0),
    "audio:seed": u32(seedB64, 1),
    "font:seed": u32(seedB64, 2),
    "font:spacing_seed": u32(seedB64, 3),
    "math:trig_seed": u32(seedB64, 4),
    ...fillPersonaKeys(seedB64, ucid),
  });
}

// ── container enumeration ──────────────────────────────────────────

function getContainers() {
  const list = [{ ucid: 0, name: "Default (no container)" }];
  try {
    for (const id of Services.contextualIdentityService.getPublicIdentities()) {
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

// Boolean cloak_cfg keys render presence-as-on. Absence = no spoof.
function fmtValue(key, v) {
  if (v === undefined || v === null || v === "") return "(not spoofed)";
  if (KEY_TYPES[key] === "bool") return v ? "spoofed (on)" : "off";
  return String(v);
}

// Build an editable row. Each row knows its cloak_cfg key so it can
// write overrides directly. If the key is in `overrides` (user-set),
// the row is marked .v-overridden and gets a "× reset" button. Click
// the value to edit; the input type is chosen by KEY_TYPES[key].
function makeRow(label, key, cfg, ucid, overrides, onChange) {
  const row = document.createElement("div");
  row.className = "spoof-row dyn";

  const k = document.createElement("span");
  k.className = "k";
  k.textContent = label;
  k.title = key;  // hover the label to see the canonical cloak_cfg key

  const v = document.createElement("span");
  v.className = "v";
  const rawVal = cfg ? cfg[key] : undefined;
  const sval = fmtValue(key, rawVal);
  v.textContent = trunc(sval, 80);
  v.title = String(rawVal ?? sval);
  if (sval === "(not spoofed)") v.classList.add("v-empty");
  if (key in overrides) v.classList.add("v-overridden");

  // Edit pencil — clicking either the value or the pencil opens edit.
  const editBtn = document.createElement("button");
  editBtn.type = "button";
  editBtn.className = "row-edit";
  editBtn.textContent = "edit";
  editBtn.title = "Override this value";

  const resetBtn = document.createElement("button");
  resetBtn.type = "button";
  resetBtn.className = "row-reset";
  resetBtn.textContent = "reset";
  resetBtn.title = "Clear override (revert to persona value)";
  resetBtn.style.display = (key in overrides) ? "" : "none";
  resetBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    clearOverride(ucid, key);
    onChange();
  });

  function openEdit() {
    const existing = (key in overrides) ? overrides[key]
                   : (rawVal ?? "");
    let input;
    if (KEY_TYPES[key] === "bool") {
      input = document.createElement("select");
      for (const opt of [["", "(not spoofed — clear override)"],
                         ["true", "spoofed (on)"], ["false", "off"]]) {
        const o = document.createElement("option");
        o.value = opt[0]; o.textContent = opt[1];
        input.appendChild(o);
      }
      input.value = (key in overrides) ? String(overrides[key]) : "";
    } else if (KEY_TYPES[key] === "int" || KEY_TYPES[key] === "float") {
      input = document.createElement("input");
      input.type = "number";
      if (KEY_TYPES[key] === "float") input.step = "any";
      input.value = String(existing);
    } else {
      input = document.createElement("input");
      input.type = "text";
      input.value = String(existing);
    }
    input.className = "row-input";
    v.replaceWith(input);
    editBtn.style.display = "none";
    resetBtn.style.display = "none";

    const save = document.createElement("button");
    save.type = "button"; save.className = "row-save"; save.textContent = "save";
    const cancel = document.createElement("button");
    cancel.type = "button"; cancel.className = "row-cancel"; cancel.textContent = "cancel";
    row.appendChild(save);
    row.appendChild(cancel);

    save.addEventListener("click", () => {
      let toSave = input.value;
      if (KEY_TYPES[key] === "bool") {
        // Empty string = clear; "true"/"false" = boolean
        if (toSave === "") { clearOverride(ucid, key); }
        else { setOverride(ucid, key, toSave === "true"); }
      } else {
        setOverride(ucid, key, toSave);
      }
      onChange();
    });
    cancel.addEventListener("click", () => { onChange(); });
    input.focus();
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") save.click();
      else if (e.key === "Escape") cancel.click();
    });
  }

  v.addEventListener("click", openEdit);
  editBtn.addEventListener("click", openEdit);

  row.appendChild(k);
  row.appendChild(v);
  row.appendChild(editBtn);
  row.appendChild(resetBtn);
  return row;
}

function populateGrid(id, cfg, rows, ucid, overrides, onChange) {
  const grid = document.getElementById(id);
  if (!grid) return;
  // Clear existing children EXCEPT static elements declared in HTML
  // (e.g. timezone group has a <select>; we never wipe that).
  Array.from(grid.querySelectorAll(".spoof-row.dyn")).forEach(n => n.remove());
  for (const [label, key] of rows) {
    grid.appendChild(makeRow(label, key, cfg, ucid, overrides, onChange));
  }
}

function populateFonts(cfg, ucid) {
  const seedB64 = Services.prefs.getStringPref(masterSeedPref(ucid), "");
  const rows = [
    ["font:seed (ordering)", cfg ? cfg["font:seed"] : null],
    ["font:spacing_seed",    cfg ? cfg["font:spacing_seed"] : null],
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

function populateSeeds(cfg, ucid) {
  const seedB64 = Services.prefs.getStringPref(masterSeedPref(ucid), "");
  const kbd = Services.prefs.getStringPref(keyboardSeedPref(ucid), "");
  const tim = Services.prefs.getStringPref(timingSeedPref(ucid), "");
  const rows = [
    ["master seed (32 bytes)",     fmtSeed(seedB64)],
    ["canvas:seed (u32)",          cfg ? cfg["canvas:seed"] : null],
    ["audio:seed (u32)",           cfg ? cfg["audio:seed"] : null],
    ["font:seed (u32)",            cfg ? cfg["font:seed"] : null],
    ["font:spacing_seed (u32)",    cfg ? cfg["font:spacing_seed"] : null],
    ["math:trig_seed (u32)",       cfg ? cfg["math:trig_seed"] : null],
    ["keyboard timing seed",       fmtSeed(kbd)],
    ["setTimeout jitter seed",     fmtSeed(tim)],
  ];
  const grid = document.getElementById("grp-seeds");
  Array.from(grid.querySelectorAll(".spoof-row.dyn")).forEach(n => n.remove());
  for (const [label, value] of rows) {
    const row = makeRow(label, value);
    row.classList.add("dyn");
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

function updateHeadline(cfg) {
  const el = document.getElementById("cfx-headline-text");
  if (!cfg) { el.textContent = "(not yet generated — click Regenerate)"; return; }
  const platform = cfg["navigator.platform"] || "?";
  const w = cfg["screen.width"] ?? "?";
  const h = cfg["screen.height"] ?? "?";
  const dpr = cfg["window.devicePixelRatio"] ?? "?";
  const hwc = cfg["navigator.hardwareConcurrency"] ?? "?";
  const renderer = (cfg["webGl:renderer"] || "?").slice(0, 50);
  el.textContent = `${platform} · ${w}×${h}@${dpr}x · ${hwc}-core · ${renderer}`;
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
  }
  syncStatus();
  enabledEl.addEventListener("change", () => {
    Services.prefs.setBoolPref(PREF_ENABLED, enabledEl.checked);
    syncStatus();
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
      Services.prefs.setStringPref(cloakCfgPref(ucid), buildCloakCfg(seed, ucid));
    }
  }

  function refreshContainer() {
    const ucid = parseInt(selectEl.value, 10) || 0;
    const cfg = getCloakCfg(ucid);
    const overrides = readOverrides(ucid);
    const onEdit = () => { rebuildCloakCfg(ucid); refreshContainer(); };

    updateHeadline(cfg);
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
  // per-container override prefs are honored.
  regenBtn.addEventListener("click", () => {
    const ucid = parseInt(selectEl.value, 10) || 0;
    const seed = randomSeedB64();
    Services.prefs.setStringPref(masterSeedPref(ucid), seed);
    Services.prefs.setStringPref(cloakCfgPref(ucid), buildCloakCfg(seed, ucid));
    refreshContainer();
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
        Services.prefs.setStringPref(cloakCfgPref(ucid), buildCloakCfg(seed, ucid));
      }
      refreshContainer();
    });
  }

  // Opt-in flag toggles auto-bind via data-pref.
  for (const el of document.querySelectorAll("input[data-pref]")) {
    const pref = el.dataset.pref;
    el.checked = Services.prefs.getBoolPref(pref, false);
    el.addEventListener("change", () => {
      Services.prefs.setBoolPref(pref, el.checked);
    });
  }
});
