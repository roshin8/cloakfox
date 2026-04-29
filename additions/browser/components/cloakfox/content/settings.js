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

const { fillPersonaKeys, pickPersona, listPersonas } = ChromeUtils.importESModule(
  "resource:///modules/CloakfoxPersonas.sys.mjs"
);

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

// Each group is a list of [label, getter(cfg) → string]. Missing keys
// render as "(not spoofed)" so the user can distinguish "not yet
// generated" from "intentionally bypassed".
const GROUPS = {
  "grp-navigator": [
    ["navigator.platform",            (c) => c["navigator.platform"]],
    ["navigator.userAgent",           (c) => c["navigator.userAgent"]],
    ["navigator.appVersion",          (c) => c["navigator.appVersion"]],
    ["navigator.oscpu",               (c) => c["navigator.oscpu"]],
    ["navigator.hardwareConcurrency", (c) => c["navigator.hardwareConcurrency"]],
    ["navigator:maxTouchPoints",      (c) => c["navigator:maxTouchPoints"]],
    ["navigator.language",            (c) => c["navigator.language"]],
    ["Accept-Language header",        (c) => c["headers.Accept-Language"]],
    ["Accept-Encoding header",        (c) => c["headers.Accept-Encoding"]],
    ["User-Agent header",             (c) => c["headers.User-Agent"]],
  ],
  "grp-screen": [
    ["screen.width",            (c) => c["screen.width"]],
    ["screen.height",           (c) => c["screen.height"]],
    ["screen.availWidth",       (c) => c["screen.availWidth"]],
    ["screen.availHeight",      (c) => c["screen.availHeight"]],
    ["screen.availLeft / availTop", (c) => `${c["screen.availLeft"]} / ${c["screen.availTop"]}`],
    ["window.outerWidth",       (c) => c["window.outerWidth"]],
    ["window.outerHeight",      (c) => c["window.outerHeight"]],
    ["window.innerWidth",       (c) => c["window.innerWidth"]],
    ["window.innerHeight",      (c) => c["window.innerHeight"]],
    ["window.devicePixelRatio", (c) => c["window.devicePixelRatio"]],
    ["window.screenX / screenY",(c) => `${c["window.screenX"]} / ${c["window.screenY"]}`],
    ["screen.orientation.type", (c) => c["screen:orientation:type"]],
  ],
  "grp-graphics": [
    ["webGl.vendor",            (c) => c["webGl:vendor"]],
    ["webGl.renderer",          (c) => c["webGl:renderer"]],
  ],
  "grp-audio": [
    ["AudioContext.sampleRate",      (c) => c["AudioContext:sampleRate"]],
    ["AudioContext.maxChannelCount", (c) => c["AudioContext:maxChannelCount"]],
    ["AudioContext.outputLatency",   (c) => c["AudioContext:outputLatency"]],
  ],
  "grp-fonts": [],   // populated from seeds; see populateFonts
  "grp-locale": [
    ["locale.language",  (c) => c["locale:language"]],
    ["locale.region",    (c) => c["locale:region"]],
    ["locale.script",    (c) => c["locale:script"]],
  ],
  "grp-geo": [
    ["latitude",  (c) => c["geolocation:latitude"]],
    ["longitude", (c) => c["geolocation:longitude"]],
    ["accuracy",  (c) => c["geolocation:accuracy"]],
  ],
  "grp-network": [],   // populated below; sources parent sharedData
  "grp-media": [
    ["codecs:spoof",                        (c) => boolish(c["codecs:spoof"])],
    ["mediaCapabilities:spoof",             (c) => boolish(c["mediaCapabilities:spoof"])],
    ["mediaFeature:resolution",             (c) => c["mediaFeature:resolution"]],
    ["mediaFeature:invertedColors",         (c) => boolish(c["mediaFeature:invertedColors"])],
    ["mediaFeature:prefersReducedMotion",   (c) => boolish(c["mediaFeature:prefersReducedMotion"])],
    ["mediaFeature:prefersReducedTransparency", (c) => boolish(c["mediaFeature:prefersReducedTransparency"])],
  ],
  "grp-voices": [
    ["voices:blockIfNotDefined",         (c) => boolish(c["voices:blockIfNotDefined"])],
    ["voices:fakeCompletion",            (c) => boolish(c["voices:fakeCompletion"])],
    ["voices:fakeCompletion:charsPerSecond", (c) => c["voices:fakeCompletion:charsPerSecond"]],
  ],
  "grp-hidden": [
    ["permissions:spoof",          (c) => boolish(c["permissions:spoof"])],
    ["indexedDB:databases:hidden", (c) => boolish(c["indexedDB:databases:hidden"])],
    ["document:lastModified:hidden", (c) => boolish(c["document:lastModified:hidden"])],
    ["navigator:vibrate:disabled", (c) => boolish(c["navigator:vibrate:disabled"])],
    ["navigator:webgpu:disabled",  (c) => boolish(c["navigator:webgpu:disabled"])],
  ],
};

// MaskConfig keys are mostly "true if present, else absent". Render
// presence as the active state since absence means the spoof isn't
// applied to this container.
function boolish(v) {
  if (v === undefined || v === null) return undefined;
  return v ? "spoofed (on)" : "off";
}

function makeRow(label, value) {
  const row = document.createElement("div");
  row.className = "spoof-row";
  const k = document.createElement("span");
  k.className = "k";
  k.textContent = label;
  const v = document.createElement("span");
  v.className = "v";
  const sval = (value === undefined || value === null || value === "")
    ? "(not spoofed)"
    : String(value);
  v.textContent = trunc(sval, 80);
  v.title = sval;        // full value on hover
  if (sval === "(not spoofed)") v.classList.add("v-empty");
  row.appendChild(k);
  row.appendChild(v);
  return row;
}

function populateGrid(id, cfg, rows) {
  const grid = document.getElementById(id);
  if (!grid) return;
  // Clear existing children EXCEPT static elements declared in HTML
  // (e.g. timezone group has a <select>; we never wipe that).
  Array.from(grid.querySelectorAll(".spoof-row.dyn")).forEach(n => n.remove());
  for (const [label, getter] of rows) {
    const row = makeRow(label, getter(cfg || {}));
    row.classList.add("dyn");
    grid.appendChild(row);
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

function populateNetwork() {
  // Public IPs come from CloakfoxWebRTCSync (parent process), pushed
  // into Services.ppmm.sharedData. Read via sharedData since prefs
  // would race the parent fetch on first launch.
  const v4 = Services.ppmm.sharedData.get("cloakfox-public-ipv4") || "";
  const v6 = Services.ppmm.sharedData.get("cloakfox-public-ipv6") || "";
  const rows = [
    ["WebRTC public IPv4", v4 || "(not yet detected)"],
    ["WebRTC public IPv6", v6 || "(not yet detected)"],
  ];
  const grid = document.getElementById("grp-network");
  Array.from(grid.querySelectorAll(".spoof-row.dyn")).forEach(n => n.remove());
  for (const [label, value] of rows) {
    const row = makeRow(label, value);
    row.classList.add("dyn");
    grid.appendChild(row);
  }
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
  const enabledEl       = document.getElementById("cfx-enabled");
  const selectEl        = document.getElementById("cfx-container-select");
  const personaPickerEl = document.getElementById("cfx-persona-override-select");
  const tzSelectEl      = document.getElementById("cfx-tz-select");
  const tzCurrentEl     = document.getElementById("cfx-tz-current");
  const regenBtn        = document.getElementById("cfx-regenerate");
  const clearBtn        = document.getElementById("cfx-clear");

  // Master enable.
  enabledEl.checked = Services.prefs.getBoolPref(PREF_ENABLED, false);
  enabledEl.addEventListener("change", () => {
    Services.prefs.setBoolPref(PREF_ENABLED, enabledEl.checked);
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

  // Persona override dropdown.
  for (const p of listPersonas()) {
    const opt = document.createElement("option");
    opt.value = String(p.index);
    opt.textContent = `${p.index}: ${p.label}`;
    personaPickerEl.appendChild(opt);
  }

  function refreshContainer() {
    const ucid = parseInt(selectEl.value, 10) || 0;
    const cfg = getCloakCfg(ucid);
    updateHeadline(cfg);
    populateGrid("grp-navigator", cfg, GROUPS["grp-navigator"]);
    populateGrid("grp-screen",    cfg, GROUPS["grp-screen"]);
    populateGrid("grp-graphics",  cfg, GROUPS["grp-graphics"]);
    populateGrid("grp-audio",     cfg, GROUPS["grp-audio"]);
    populateFonts(cfg, ucid);
    populateGrid("grp-locale",    cfg, GROUPS["grp-locale"]);
    populateGrid("grp-geo",       cfg, GROUPS["grp-geo"]);
    populateGrid("grp-media",     cfg, GROUPS["grp-media"]);
    populateGrid("grp-voices",    cfg, GROUPS["grp-voices"]);
    populateGrid("grp-hidden",    cfg, GROUPS["grp-hidden"]);
    populateNetwork();
    populateSeeds(cfg, ucid);
    tzCurrentEl.textContent = Services.prefs.getStringPref(tzPref(ucid), "") || "UTC (default)";
    tzSelectEl.value = Services.prefs.getStringPref(tzPref(ucid), "");
    const idx = Services.prefs.getIntPref(personaIndexPref(ucid), -1);
    personaPickerEl.value = String(idx);
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

  // Persona override picker. Writes pref + rewrites cloak_cfg so the
  // new persona's keys take effect for new tabs immediately, not just
  // at next browser startup.
  personaPickerEl.addEventListener("change", () => {
    const ucid = parseInt(selectEl.value, 10) || 0;
    const idx = parseInt(personaPickerEl.value, 10);
    if (Number.isNaN(idx) || idx < 0) {
      Services.prefs.clearUserPref(personaIndexPref(ucid));
    } else {
      Services.prefs.setIntPref(personaIndexPref(ucid), idx);
    }
    const seed = Services.prefs.getStringPref(masterSeedPref(ucid), "");
    if (seed) {
      Services.prefs.setStringPref(cloakCfgPref(ucid), buildCloakCfg(seed, ucid));
    }
    refreshContainer();
  });

  // Regenerate persona — same path as SeedSync; ucid forwarded so any
  // persona_index override is honored.
  regenBtn.addEventListener("click", () => {
    const ucid = parseInt(selectEl.value, 10) || 0;
    const seed = randomSeedB64();
    Services.prefs.setStringPref(masterSeedPref(ucid), seed);
    Services.prefs.setStringPref(cloakCfgPref(ucid), buildCloakCfg(seed, ucid));
    refreshContainer();
  });

  // Clear — strips seeds, cloak_cfg, timezone, AND persona override so
  // the container falls back to host's real values.
  clearBtn.addEventListener("click", () => {
    const ucid = parseInt(selectEl.value, 10) || 0;
    Services.prefs.clearUserPref(masterSeedPref(ucid));
    Services.prefs.clearUserPref(cloakCfgPref(ucid));
    Services.prefs.clearUserPref(tzPref(ucid));
    Services.prefs.clearUserPref(personaIndexPref(ucid));
    refreshContainer();
  });

  // Opt-in flag toggles auto-bind via data-pref.
  for (const el of document.querySelectorAll("input[data-pref]")) {
    const pref = el.dataset.pref;
    el.checked = Services.prefs.getBoolPref(pref, false);
    el.addEventListener("change", () => {
      Services.prefs.setBoolPref(pref, el.checked);
    });
  }
});
