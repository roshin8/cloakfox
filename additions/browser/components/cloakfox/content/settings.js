import { getPersonaHardwareFamilies } from "resource:///modules/CloakfoxBayesianNetwork.sys.mjs";
import { PRESETS, browserValues, screenValues, languageValues, gpuValues } from "./settings-presets.mjs";
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
 * The cloak_cfg JSON is intended configuration. Use the consistency inspector
 * to measure actual website window and worker values.
 */

/* global Services, ChromeUtils */

const { fillPersonaKeys, writeHttpProfilePrefs, personaOSMode, listPersonas } = ChromeUtils.importESModule(
  "resource:///modules/CloakfoxPersonas.sys.mjs"
);

// Write a container's cloak_cfg and keep its H2/H3 wire profile coherent
// with the persona in one step. Used by every cloak_cfg (re)write below.
function persistCloakCfg(ucid, seed, clearOverrides = false) {
  const cfg = buildCloakCfg(seed, ucid, clearOverrides);
  // Build successfully before discarding saved fields; keep region/privacy policy.
  if (clearOverrides) clearAllOverrides(ucid);
  Services.prefs.setStringPref(cloakCfgPref(ucid), cfg);
  let ua = "";
  try { ua = JSON.parse(cfg)["navigator.userAgent"] || ""; } catch (_e) {}
  writeHttpProfilePrefs(ucid, ua);
}
const { KEY_TYPES, readOverrides, setOverride, clearOverride, clearAllOverrides, applyOverrides } =
  ChromeUtils.importESModule("resource:///modules/CloakfoxOverrides.sys.mjs");

const { ContextualIdentityService } = ChromeUtils.importESModule(
  "moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs");
const { forgetContainerData } = ChromeUtils.importESModule(
  "resource:///modules/CloakfoxIdentityActions.sys.mjs");

const PREF_ENABLED = "cloakfox.enabled";
const { resolveNetworkProfile, writeNetworkProfile } = ChromeUtils.importESModule(
  "resource:///modules/CloakfoxNetworkProfiles.sys.mjs"
);

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
const personaModePref = (ucid) => `cloakfox.container.${ucid}.persona_os_mode`;
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
function buildCloakCfg(seedB64, ucid = null, clearOverrides = false) {
  const base = {
    "fingerprint:secret": seedB64,
    "canvas:seed": u32(seedB64, 0),
    "audio:seed": u32(seedB64, 1),
    "font:seed": u32(seedB64, 2),
    // C++ FontSpacingSeedManager reads "fonts:spacing_seed" (plural); the
    // singular key silently no-ops the per-container font-spacing noise.
    "fonts:spacing_seed": u32(seedB64, 3),
    "math:trig_seed": u32(seedB64, 4),
    ...fillPersonaKeys(seedB64, ucid),
  };
  return JSON.stringify(ucid === null ? base : applyOverrides(
    ucid, base, clearOverrides ? {} : readOverrides(ucid)));
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
    ["Expose media devices with generic labels", "mediaDevices:enabled"],
    ["Maximum exposed microphones", "mediaDevices:micros"],
    ["Maximum exposed cameras", "mediaDevices:webcams"],
    ["Maximum exposed speakers", "mediaDevices:speakers"],
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

const PRESET_GROUPS = {
  "grp-navigator": {id: "browser", label: "Browser / OS preset", items: PRESETS.browsers, values: browserValues},
  "grp-screen": {id: "screen", label: "Display preset", items: PRESETS.screens, values: screenValues},
  "grp-graphics": {id: "gpu", label: "GPU preset", items: PRESETS.gpus.map(p => ({...p, name: p.renderer})), values: gpuValues},
  "grp-locale": {id: "language", label: "Language preset", items: PRESETS.languages, values: languageValues},
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

const FIELD_CHOICES = {
  "navigator.platform": ["Win32", "MacIntel", "Linux x86_64"],
  "navigator.hardwareConcurrency": [2, 4, 8, 10, 12, 16, 24, 32],
  "navigator:maxTouchPoints": [0, 1, 5, 10],
  "screen.width": [1280, 1366, 1440, 1536, 1920, 2560, 3840],
  "screen.height": [720, 768, 900, 1080, 1440, 2160],
  "window.devicePixelRatio": [1, 1.25, 1.5, 2, 3],
  "screen:orientation:type": ["landscape-primary", "portrait-primary", "landscape-secondary", "portrait-secondary"],
  "AudioContext:sampleRate": [44100, 48000, 96000],
  "AudioContext:maxChannelCount": [2, 6, 8],
};
const FIELD_LABELS = {
  "navigator.platform": "Platform", "navigator.hardwareConcurrency": "CPU cores",
  "navigator:maxTouchPoints": "Touch points", "screen.width": "Screen width",
  "screen.height": "Screen height", "window.devicePixelRatio": "Pixel density",
  "screen:orientation:type": "Screen orientation", "AudioContext:sampleRate": "Audio sample rate",
  "AudioContext:maxChannelCount": "Audio channels",
};

// Boolean cloak_cfg keys render presence-as-on. Absence = no spoof.
function fmtValue(key, v) {
  if (v === undefined || v === null || v === "") return "Not overridden";
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
  k.textContent = FIELD_LABELS[key] || label;
  k.title = key;

  const rawVal = cfg ? cfg[key] : undefined;
  const isBool = KEY_TYPES[key] === "bool";

  const v = document.createElement("button");
  v.className = "v";
  v.type = "button";
  const sval = fmtValue(key, rawVal);
  v.textContent = trunc(sval, 80);
  v.title = String(rawVal ?? sval);
  if (sval === "Not overridden") v.classList.add("v-empty");
  if (key in overrides) v.classList.add("v-overridden");

  const managedRegion = key.startsWith("geolocation:") || key.startsWith("locale:") ||
    key === "navigator.language" || key === "headers.Accept-Language";
  if (managedRegion) {
    v.title += " — Configure this value in the Region section.";
    const regionLink = document.createElement("a");
    regionLink.href = "#cfx-region-settings";
    regionLink.className = "region-link";
    regionLink.textContent = `${sval} — Edit in Region`;
    row.append(k, regionLink);
    return row;
  }

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

  const choices = isBool ? [true, false] : FIELD_CHOICES[key];
  if (choices) {
    const picker = document.createElement("select");
    picker.setAttribute("aria-label", FIELD_LABELS[key] || label);
    picker.dataset.key = key;
    picker.add(new Option(key in overrides ? "Automatic (from identity)" : `Automatic (${fmtValue(key, rawVal)})`, "auto"));
    for (const value of choices) picker.add(new Option(isBool ? (value ? "On" : "Off") : String(value), String(value)));
    if (!isBool) picker.add(new Option("Custom…", "custom"));
    picker.value = key in overrides ? String(overrides[key]) : "auto";
    if (!picker.value) {
      picker.add(new Option(`Custom: ${overrides[key]}`, String(overrides[key])));
      picker.value = String(overrides[key]);
    }
    picker.addEventListener("change", () => {
      if (picker.value === "custom") { picker.replaceWith(v); openEditMode(); return; }
      if (picker.value === "auto") clearOverride(ucid, key);
      else setOverride(ucid, key, isBool ? picker.value === "true" : picker.value);
      onChange();
    });
    row.append(k, picker, actions);
    return row;
  }
  v.addEventListener("click", openEditMode);

  function openEditMode() {
    const existing = (key in overrides) ? overrides[key] : (rawVal ?? "");
    const initialValue = String(existing);
    const isLong = initialValue.length > 50
      || /^(headers\.|navigator\.user(Agent|Version)|navigator\.oscpu|webGl:renderer)/.test(key);
    const input = document.createElement(isLong ? "textarea" : "input");
    if (input.tagName === "INPUT") {
      input.type = (KEY_TYPES[key] === "int" || KEY_TYPES[key] === "float") ? "number" : "text";
      if (KEY_TYPES[key] === "float") input.step = "any";
      if (["mediaDevices:micros", "mediaDevices:webcams", "mediaDevices:speakers"].includes(key)) {
        input.min = "0"; input.max = "64"; input.step = "1";
      }
    } else {
      input.rows = Math.min(6, Math.max(2, Math.ceil(initialValue.length / 60)));
    }
    input.value = initialValue;
    input.className = "row-input";
    v.replaceWith(input);

    let committed = false;
    function commit() {
      if (committed) return;
      if (["mediaDevices:micros", "mediaDevices:webcams", "mediaDevices:speakers"].includes(key) && !input.checkValidity()) {
        input.reportValidity();
        return;
      }
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
  if (PRESET_GROUPS[id]) grid.appendChild(makePresetRow(PRESET_GROUPS[id], cfg, ucid, overrides, onChange));
  const wasOpen = grid.querySelector(".advanced-fields")?.open;
  grid.querySelector(".advanced-fields")?.remove();
  const advanced = document.createElement("details"); advanced.className = "advanced-fields"; advanced.open = wasOpen ?? !Services.prefs.getBoolPref("cloakfox.ui.collapse_advanced", false);
  const summary = document.createElement("summary"); summary.textContent = "Advanced field overrides"; advanced.append(summary);
  for (const [label, key] of rows) {
    const row = makeRow(label, key, cfg, ucid, overrides, onChange);
    (["grp-graphics", "grp-locale", "grp-geo", "grp-network"].includes(id) || FIELD_CHOICES[key] || KEY_TYPES[key] === "bool" ? grid : advanced).appendChild(row);
  }
  if (advanced.children.length > 1) grid.append(advanced);
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
  if (el) el.textContent = Services.prefs.getBoolPref("cloakfox.webrtc.ip_lookup.enabled", false)
    ? `Public address lookup — IPv4: ${v4} · IPv6: ${v6}`
    : "Public address lookup is off. You can enable it in Container connections below.";
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
  const platform = ({Win32:"Windows",MacIntel:"macOS","Linux x86_64":"Linux"})[cfg["navigator.platform"]] || cfg["navigator.platform"] || "Unknown platform";
  const w = cfg["screen.width"] ?? "?";
  const h = cfg["screen.height"] ?? "?";
  const density = cfg["window.devicePixelRatio"];
  const dpr = typeof density === "number" ? Number(density.toFixed(2)) : "?";
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
  function updateNetworkProfile() {
    const ucid = Number(document.getElementById("cfx-container-select").value) || 0;
    const pref = `cloakfox.container.${ucid}.network_follow_identity`;
    const checkbox = document.getElementById("cfx-network-follow-identity");
    checkbox.checked = Services.prefs.getBoolPref(pref, false);
    const selected = resolveNetworkProfile(ucid);
    const status = document.getElementById("cfx-network-profile-status");
    if (!Services.prefs.getBoolPref(PREF_ENABLED, false)) {
      status.textContent = "Native Firefox networking: Cloakfox protection is disabled. Your network choice is saved.";
    } else if (selected.unsupported) {
      status.textContent = "Native Firefox networking: " + (selected.reason || "this identity has no supported transport adapter") + ".";
    } else if (selected.experimental) {
      status.textContent = "Experimental Chrome profile for HTTP/2, TLS and QUIC/HTTP/3, using Chrome 155 as the reference. Full Chrome equivalence is pending: "
        + selected.gaps.join(", ") + ". Applies to new connections; active transfers keep their original profile.";
    } else {
      status.textContent = "Native Firefox HTTP/2, TLS and QUIC/HTTP/3. Applies to new connections.";
    }
  }
  document.getElementById("cfx-network-follow-identity").addEventListener("change", event => {
    const ucid = Number(document.getElementById("cfx-container-select").value) || 0;
    Services.prefs.setBoolPref(`cloakfox.container.${ucid}.network_follow_identity`, event.target.checked);
    writeNetworkProfile(ucid);
    updateNetworkProfile();
  });
  const networkObserver = {observe(_subject, _topic, pref) {
    if (pref === PREF_ENABLED || /\.network_follow_identity$/.test(pref) || /^cloakfox\.s\.cloak_cfg_\d+$/.test(pref)) {
      updateNetworkProfile();
    }
  }};
  for (const pref of [PREF_ENABLED, "cloakfox.container.", "cloakfox.s."]) {
    Services.prefs.addObserver(pref, networkObserver);
  }
  window.addEventListener("unload", () => {
    for (const pref of [PREF_ENABLED, "cloakfox.container.", "cloakfox.s."]) {
      Services.prefs.removeObserver(pref, networkObserver);
    }
  }, {once: true});
  function updateChromiumCompatibility() {
    const ucid = parseInt(document.getElementById("cfx-container-select").value, 10) || 0;
    const ua = getCloakCfg(ucid)?.["navigator.userAgent"] || "";
    // Match the native desktop Chromium eligibility gate, including custom UAs.
    const chromium = /(?:Chrome|Chromium)\/\d/.test(ua)
      && !/(?:Firefox\/|iPhone|iPad|Android|Mobile)/.test(ua);
    document.getElementById("sec-screen-management").hidden = !chromium;

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
  selectEl.replaceChildren();
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
    const cfg = getCloakCfg(ucid);
    const overrides = readOverrides(ucid);
    const seedB64 = Services.prefs.getStringPref(masterSeedPref(ucid), "");
    const onEdit = () => { rebuildCloakCfg(ucid); refreshContainer(); };

    const mode = personaOSMode(ucid);
    const osLabels = { windows:"Windows", macos:"macOS", linux:"Linux", legacy:"all" };
    const hostLabel = { Darwin:"macOS", WINNT:"Windows", Linux:"Linux" }[Services.appinfo.OS];
    document.getElementById("cfx-persona-filter").value = mode === "host" ? hostLabel : osLabels[mode];
    document.getElementById("cfx-persona-os-current").textContent =
      `Saved generation mode: ${mode === "host" ? "this computer’s OS" : osLabels[mode] === "all" ? "all operating systems" : osLabels[mode]}. Custom overrides may differ.`;
    document.getElementById("cfx-persona-choice").value = "-1";
    loadIdentityChoices();
    updateChromiumCompatibility();
    updateNetworkProfile();
    updateHardwareChoices(Services.prefs.getStringPref(`cloakfox.container.${ucid}.persona_hardware`, "auto"));
    updateHeadline(cfg, seedB64);
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
    const manualRegion = ChromeUtils.importESModule("resource:///modules/CloakfoxRegions.sys.mjs").getRegion(ucid);
    tzSelectEl.disabled = !!manualRegion;
    tzSelectEl.title = manualRegion ? "Managed by the Region section" : "Reload pages after changing timezone";

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
  document.addEventListener("cfx-region-changed", refreshContainer);
  refreshContainer();

  // Sync all container-scoped cards after resolving the initial deep link.
  selectEl.dispatchEvent(new Event("change"));

  // Timezone picker.
  tzSelectEl.addEventListener("change", () => {
    const ucid = parseInt(selectEl.value, 10) || 0;
    if (tzSelectEl.value === "") {
      Services.prefs.clearUserPref(tzPref(ucid));
    } else {
      Services.prefs.setStringPref(tzPref(ucid), tzSelectEl.value);
    }
    ChromeUtils.importESModule("resource:///modules/CloakfoxSeedSync.sys.mjs").refreshContainerConfig(ucid);
    Services.prefs.savePrefFile(null);
    refreshContainer();
  });

  const identityChoice = document.getElementById("cfx-persona-choice");
  const generateNew = document.getElementById("cfx-generate-new");
  generateNew.addEventListener("click", () => {
    if (generateNew.disabled) return;
    applyIdentity(-1);
  });
  function updateHardwareChoices(selected = "auto") {
    const select = document.getElementById("cfx-persona-hardware");
    const os = selectedOSMode() === "legacy" ? "auto" : selectedOSMode();
    select.replaceChildren(new Option("Any graphics family", "auto"));
    for (const family of getPersonaHardwareFamilies(os)) select.append(new Option(family, family));
    select.value = [...select.options].some(option => option.value === selected) ? selected : "auto";
  }
  function selectedOSMode() {
    return { all:"legacy", Windows:"windows", macOS:"macos", Linux:"linux" }[document.getElementById("cfx-persona-filter").value];
  }
  function loadIdentityChoices() {
    const choice = document.getElementById("cfx-persona-choice");
    const filter = document.getElementById("cfx-persona-filter");
    const mode = selectedOSMode();
    const label = filter.value === "all" ? "any OS" : filter.value;
    choice.replaceChildren(new Option(`Choose a profile (${label})`, "-1"));
    const items = listPersonas(Services.appinfo.OS, mode);
    for (const os of ["Windows", "macOS", "Linux"]) {
      if (filter.value !== "all" && filter.value !== os) continue;
      const group = document.createElement("optgroup"); group.label = os;
      for (const item of items.filter(item => item.label.startsWith(os))) {
        group.append(new Option(item.label.replace(`${os} · `, ""), String(item.index)));
      }
      if (group.children.length) choice.append(group);
    }
    regenBtn.disabled = true;
    document.getElementById("cfx-generate-new").textContent = filter.value === "all" ? "Generate new identity" : `Generate ${filter.value} identity`;
    document.getElementById("cfx-persona-help").textContent =
      `${choice.options.length - 1} BrowserForge previews. Both fresh generation and previews use the operating system above. Selecting an OS or preview does not apply it. Custom overrides are kept unless cleared during fresh generation.`;
  }
  document.getElementById("cfx-persona-filter").addEventListener("change", () => { loadIdentityChoices(); updateHardwareChoices(); });

  identityChoice.addEventListener("change", () => { regenBtn.disabled = Number(identityChoice.value) < 0; });

  // Regenerate persona — same path as SeedSync; ucid forwarded so any
  // per-container override prefs are honored. Flash the headline on
  // update so the user has visible confirmation. Errors surface via
  // Cu.reportError so a silent build failure doesn't look like the
  // button does nothing.
  regenBtn.addEventListener("click", () => {
    const index = Number(identityChoice.value);
    if (index >= 0) applyIdentity(index);
  });
  let identityBusy = false;
  async function applyIdentity(index) {
    if (identityBusy) return;
    const ucid = parseInt(selectEl.value, 10) || 0;
    const mode = selectedOSMode();
    const button = index === -1 ? generateNew : regenBtn;
    const previousLabel = button.textContent;
    const status = document.getElementById("cfx-identity-status");
    identityBusy = true;
    const controls = [...document.querySelectorAll(".hero button, .hero select, .hero input"), selectEl];
    const previousDisabled = controls.map(control => control.disabled);
    controls.forEach(control => { control.disabled = true; });
    button.classList.add("identity-working");
    button.setAttribute("aria-busy", "true");
    button.textContent = index === -1 ? "Generating…" : "Applying…";
    status.textContent = button.textContent;
    status.className = "identity-status";
    // Paint the working state before synchronous BrowserForge sampling begins.
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    let succeeded = false;
    try {
      if (!["legacy", "windows", "macos", "linux"].includes(mode)) throw new Error("Invalid persona OS mode");
      Services.prefs.setStringPref(personaModePref(ucid), mode);
      if (!Number.isInteger(index) || index < -1 || index >= 30) throw new Error("Select a BrowserForge identity");
      if (index === -1) Services.prefs.clearUserPref(personaIndexPref(ucid));
      else Services.prefs.setIntPref(personaIndexPref(ucid), index);
      const hardware = document.getElementById("cfx-persona-hardware").value;
      const prefix = `cloakfox.container.${ucid}.`;
      // A selected preview retains its 155 pin; fresh sampling may use hardware filters.
      if (index === -1 && hardware !== "auto") {
        Services.prefs.setStringPref(prefix + "persona_os", mode === "legacy" ? "auto" : mode);
        Services.prefs.setStringPref(prefix + "persona_hardware", hardware);
      } else {
        Services.prefs.clearUserPref(prefix + "persona_os");
        Services.prefs.clearUserPref(prefix + "persona_hardware");
      }
      const seed = randomSeedB64();
      const clearOverrides = index === -1 &&
        document.getElementById("cfx-generation-clear-overrides").checked;
      Services.prefs.setStringPref(masterSeedPref(ucid), seed);
      persistCloakCfg(ucid, seed, clearOverrides);
      Services.prefs.savePrefFile(null);
      refreshContainer();
      succeeded = true;
      status.textContent = `${index === -1 ? "Generated and applied" : "Applied selected profile"} · ${shortSeedTag(seed)}.${clearOverrides ? " Field overrides cleared." : ""} Reload website tabs to use it.`;
      status.className = "identity-status identity-success";
      const hero = document.querySelector(".current-persona-strip");
      if (hero) {
        hero.classList.remove("hero-flash");
        void hero.offsetWidth;
        hero.classList.add("hero-flash");
      }
    } catch (e) {
      Cu.reportError("Cloakfox regenerate failed: " + e.message + "\n" + e.stack);
      status.textContent = "Identity change failed: " + e.message;
      status.className = "identity-status identity-error";
    } finally {
      identityBusy = false;
      controls.forEach((control, i) => { control.disabled = previousDisabled[i]; });
      regenBtn.disabled = Number(identityChoice.value) < 0;
      button.classList.remove("identity-working");
      button.removeAttribute("aria-busy");
      if (index !== -1 || !succeeded) button.textContent = previousLabel;
    }
  }

  const forgetBtn = document.getElementById("cfx-forget-data");
  const forgetStatus = document.getElementById("cfx-forget-status");
  forgetBtn.addEventListener("click", async () => {
    const idText = selectEl.value;
    if (!/^(0|[1-9][0-9]*)$/.test(idText)) return;
    const ucid = Number(idText);
    const name = selectEl.selectedOptions[0]?.textContent || `Container ${ucid}`;
    const confirmed = Services.prompt.confirm(window, "Forget container data?",
      `Forget data for ${name}?\n\nThis closes its website tabs in every window and removes its saved tab-restore records, cookies, site storage and active website logins. Shared site permissions are kept; only permissions provably isolated to a named container can be removed. It changes the generated appearance after clearing succeeds.\n\nOther containers, shared browsing history, saved passwords and bookmarks are kept. The container name and connection settings are kept. This cannot be undone.`);
    if (!confirmed) return;
    forgetBtn.disabled = true;
    selectEl.disabled = true;
    regenBtn.disabled = true;
    generateNew.disabled = true;
    clearBtn.disabled = true;
    forgetStatus.textContent = "Closing website tabs and clearing container data…";
    try {
      await forgetContainerData(ucid, { confirmed: true });
      forgetStatus.textContent = "Container site data and tab-restore records cleared. Appearance changed. Shared history, saved passwords and bookmarks were kept.";
      refreshContainer();
    } catch (error) {
      forgetStatus.textContent = "Could not finish forgetting container data. " + error.message;
      Cu.reportError(error);
    } finally {
      forgetBtn.disabled = false;
      selectEl.disabled = false;
      regenBtn.disabled = Number(identityChoice.value) < 0;
      generateNew.disabled = false;
      clearBtn.disabled = false;
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

// Settings shell: move existing controls without duplicating state or handlers.
// Category changes only affect visibility; all form drafts remain in the DOM.
document.addEventListener("DOMContentLoaded", () => {
  const main = document.querySelector("main");
  const hero = document.querySelector(".hero");
  hero.id = "cfx-persona-panel";
  const details = [...main.querySelectorAll(":scope > details")];
  details.forEach((node, index) => { node.id ||= `cfx-reference-${index}`; });
  const categories = [
    {id:"identity",label:"Persona & identity",description:"Choose a BrowserForge persona for this container, then customize its identity fields.",panels:["cfx-persona-panel","sec-identity","sec-screen-management"]},
    {id:"display",label:"Display & graphics",description:"Customize screen geometry, pixel density and the graphics identity.",panels:["sec-display","sec-graphics","sec-appearance"]},
    {id:"region",label:"Language & region",description:"Coordinate language, timezone and optional location for this container.",panels:["cfx-region-settings","sec-locale","sec-geo"]},
    {id:"media",label:"Audio & media",description:"Control audio characteristics, media capabilities and exposed device surfaces.",panels:["sec-audio","sec-media"]},
    {id:"connections",label:"Connections & proxies",description:"Choose this container’s connection policy and manage saved proxy routes.",panels:["sec-network-policy","cfx-proxy-manager","cfx-ip-conflict-panel"]},
    {id:"privacy",label:"Privacy & permissions",description:"Choose protection presets, compatibility exceptions and permission expiry.",panels:["cfx-privacy-settings","cfx-permission-settings","sec-hardening"]},
    {id:"templates",label:"Persona templates",description:"Reuse a persona configuration to create containers with independent identity secrets.",panels:["cfx-template-settings"]},
    {id:"containers",label:"Containers & backups",description:"Manage site assignments, temporary containers and encrypted identity backups.",panels:["cfx-container-workflows"]},
    {id:"network",label:"DNS & tracking",description:"Browser-wide DNS and tracking protection settings apply across containers.",panels:["cfx-dns-settings","cfx-tracking-settings"]},
    {id:"workspaces",label:"Workspaces",description:"Open separate browser profiles with independent history, passwords and extensions.",panels:["cfx-workspace-settings"]},
    {id:"diagnostics",label:"Diagnostics & build",description:"Inspect fingerprint consistency, derived seeds and build readiness.",panels:["cfx-consistency-inspector","sec-seeds","cfx-release-status",...details.map(node=>node.id)]},
  ];
  document.querySelector(".section-nav")?.remove();
  const sidebar = document.createElement("aside"); sidebar.className = "settings-sidebar";
  sidebar.setAttribute("aria-label", "Settings navigation");
  const context = document.createElement("div"); context.className = "sidebar-context";
  const containerLabel = document.createElement("label"); containerLabel.htmlFor = "cfx-container-select";
  containerLabel.textContent = "Editing container";
  const container = document.getElementById("cfx-container-select");
  const oldColumn = container.closest(".hero-col");
  context.append(containerLabel, container); oldColumn.remove();
  const current = document.createElement("p"); current.className = "sidebar-identity"; context.append(current);
  const headline = document.getElementById("cfx-headline-text");
  const syncIdentity = () => { current.textContent = headline.textContent; };
  new MutationObserver(syncIdentity).observe(headline, {childList:true,characterData:true,subtree:true}); syncIdentity();
  const searchLabel = document.createElement("label"); searchLabel.htmlFor = "cfx-settings-search";
  searchLabel.textContent = "Find a setting";
  const search = document.createElement("input"); search.type = "search"; search.id = "cfx-settings-search";
  search.placeholder = "Search settings…";
  const nav = document.createElement("nav"); nav.setAttribute("aria-label", "Settings categories");
  sidebar.append(context, searchLabel, search, nav);
  main.before(sidebar); document.body.classList.add("has-settings-sidebar");
  const header = document.createElement("header"); header.className = "category-header";
  const title = document.createElement("h1"); title.id = "cfx-category-title"; title.tabIndex = -1;
  const description = document.createElement("p");
  header.append(title, description); main.prepend(header);
  const empty = document.createElement("p"); empty.className = "settings-empty"; empty.hidden = true;
  empty.textContent = "No settings match. Try a category name, such as proxy, screen or language."; main.append(empty);
  const appearance = document.createElement("div"); appearance.className = "settings-appearance";
  function appearanceSelect(id, label, choices, pref, fallback) {
    const field = document.createElement("label"); field.textContent = label;
    const select = document.createElement("select"); select.id = id;
    for (const [value, text] of choices) select.append(new Option(text, value));
    const saved = Services.prefs.getStringPref(pref, fallback);
    select.value = choices.some(([value]) => value === saved) ? saved : fallback;
    select.addEventListener("change", () => {
      Services.prefs.setStringPref(pref, select.value);
      Services.prefs.savePrefFile(null);
      render();
    });
    field.append(select); field.hidden = true; appearance.append(field);
    const segment = document.createElement("div");
    segment.className = "appearance-segment";
    segment.setAttribute("role", "group"); segment.setAttribute("aria-label", label);
    const buttons = [];
    for (const [value, text] of choices) {
      const button = document.createElement("button"); button.type = "button";
      button.textContent = ({console:"Console", grouped:"Grouped", light:"Light", dark:"Dark"})[value] || text;
      button.title = text; button.dataset.value = value;
      button.addEventListener("click", () => { select.value = value; select.dispatchEvent(new Event("change")); });
      segment.append(button); buttons.push(button);
    }
    const sync = () => buttons.forEach(button => button.setAttribute("aria-pressed", String(button.dataset.value === select.value)));
    select.addEventListener("change", sync); sync();
    appearance.append(segment); return select;
  }
  const layout = appearanceSelect("cfx-layout", "Layout", [["console", "Extension console"], ["grouped", "Grouped controls"]], "cloakfox.ui.layout", "console");
  const theme = appearanceSelect("cfx-theme", "Colors", [["light", "Slate blue · Light"], ["dark", "Graphite & teal · Dark"]], "cloakfox.ui.theme", matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const advancedPreference = document.createElement("label");
  advancedPreference.className = "advanced-preference";
  const collapseAdvanced = document.createElement("input");
  collapseAdvanced.type = "checkbox"; collapseAdvanced.id = "cfx-collapse-advanced";
  collapseAdvanced.checked = Services.prefs.getBoolPref("cloakfox.ui.collapse_advanced", false);
  collapseAdvanced.addEventListener("change", () => {
    Services.prefs.setBoolPref("cloakfox.ui.collapse_advanced", collapseAdvanced.checked);
    Services.prefs.savePrefFile(null);
    for (const section of document.querySelectorAll(".advanced-fields")) section.open = !collapseAdvanced.checked;
  });
  advancedPreference.append(collapseAdvanced, document.createTextNode("Always collapse advanced overrides"));
  advancedPreference.title = "Start advanced overrides collapsed when opening settings. You can still expand individual sections.";
  appearance.append(advancedPreference);
  document.querySelector(".topbar-right").prepend(appearance);
  const tabs = document.createElement("div"); tabs.className = "settings-tabs";
  tabs.setAttribute("role", "tablist"); tabs.setAttribute("aria-label", "Settings sections");
  const identitySummary = hero.querySelector(".hero-row");
  identitySummary.classList.add("current-persona-strip");
  header.after(identitySummary, tabs);
  // Match the fixed navigation offset to the toolbar even when controls wrap.
  const topbar = document.querySelector(".topbar");
  new ResizeObserver(() => document.body.style.setProperty("--settings-topbar-height", `${topbar.offsetHeight}px`)).observe(topbar);
  const groups = new Map();
  const selectedPanels = new Map();
  function ensureGroups() {
    for (const category of categories) for (const id of category.panels) {
      const panel = document.getElementById(id);
      if (!panel || groups.has(id)) continue;
      const group = document.createElement("details"); group.className = "settings-group"; group.open = true;
      const summary = document.createElement("summary");
      summary.textContent = id === "cfx-persona-panel" ? "BrowserForge profile" : (panel.querySelector("h2, h3, summary")?.textContent.trim() || category.label);
      panel.before(group); group.append(summary, panel); groups.set(id, group);
    }
  }
  let active = "identity";
  const links = new Map();
  const categoryIcons = ["<circle cx=\"12\" cy=\"8\" r=\"3\"/><path d=\"M5 21v-3a7 7 0 0 1 14 0v3\"/>", "<rect x=\"3\" y=\"4\" width=\"18\" height=\"13\" rx=\"2\"/><path d=\"M8 21h8m-4-4v4\"/>", "<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M3 12h18M12 3a18 18 0 0 1 0 18 18 18 0 0 1 0-18\"/>", "<path d=\"m11 4-6 5H2v6h3l6 5ZM15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14\"/>", "<path d=\"M8 8h8v8H8ZM12 3v5m0 8v5M3 12h5m8 0h5\"/>", "<path d=\"m12 3-8 3v6c0 4 4 7 8 9 4-2 8-5 8-9V6Z\"/>", "<rect x=\"4\" y=\"3\" width=\"16\" height=\"18\" rx=\"2\"/><path d=\"M8 8h8M8 12h8M8 16h4\"/>", "<path d=\"m3 7 9-4 9 4-9 4ZM3 7v10l9 4 9-4V7M12 11v10\"/>"];
  categories.forEach((category,index) => {
    if (index === 0 || index === 6 || index === 8) {
      const group = document.createElement("p"); group.className = "sidebar-group";
      group.textContent = index === 0 ? "Container settings" : index === 6 ? "Organization" : "Browser settings";
      nav.append(group);
    }
    const link = document.createElement("a"); link.href = `#category-${category.id}`;
    link.textContent = category.label; link.dataset.category = category.id;
    const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("viewBox", "0 0 24 24"); icon.setAttribute("aria-hidden", "true");
    // Parse only fixed, locally authored SVG geometry.
    const parsed = new DOMParser().parseFromString('<svg xmlns="http://www.w3.org/2000/svg">' + categoryIcons[index % categoryIcons.length] + '</svg>', "image/svg+xml");
    for (const child of [...parsed.documentElement.children]) icon.append(document.importNode(child, true));
    link.prepend(icon);
    link.addEventListener("click", event => {
      event.preventDefault(); search.value = ""; active = category.id;
      history.pushState(null,"",`#category-${active}`); render(); title.focus({preventScroll:true}); window.scrollTo(0,0);
    });
    nav.append(link); links.set(category.id,link);
  });
  function render() {
    ensureGroups();
    document.documentElement.dataset.theme = theme.value;
    document.body.dataset.layout = layout.value;
    const query = search.value.trim().toLocaleLowerCase();
    const currentCategory = categories.find(item => item.id === active);
    const available = currentCategory.panels.filter(id => groups.has(id));
    const selected = selectedPanels.get(active);
    const selectedId = available.includes(selected) ? selected : available[0];
    tabs.hidden = layout.value !== "console" || !!query || available.length < 2;
    // Keep tab nodes stable while editing fields; rebuilding them steals focus.
    const tabKey = `${active}:${available.join(",")}`;
    if (tabs.dataset.key !== tabKey) {
      tabs.dataset.key = tabKey; tabs.replaceChildren();
      for (const id of available) {
        const button = document.createElement("button"); button.type = "button";
        button.id = `tab-${id}`; button.dataset.panel = id; button.setAttribute("role", "tab");
        button.setAttribute("aria-controls", id);
        button.textContent = groups.get(id).firstElementChild.textContent;
        button.addEventListener("click", () => { selectedPanels.set(active, id); render(); });
        button.addEventListener("keydown", event => {
          if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
          event.preventDefault();
          const index = available.indexOf(id);
          const next = event.key === "Home" ? 0 : event.key === "End" ? available.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + available.length) % available.length;
          selectedPanels.set(active, available[next]); render(); tabs.children[next].focus();
        });
        tabs.append(button);
      }
    }
    for (const button of tabs.children) {
      const chosen = button.dataset.panel === selectedId;
      button.setAttribute("aria-selected", String(chosen)); button.tabIndex = chosen ? 0 : -1;
    }
    let count = 0;
    for (const category of categories) {
      let matches = 0;
      for (const id of category.panels) {
        const panel = document.getElementById(id); if (!panel) continue;
        const match = query ? `${category.label} ${panel.textContent}`.toLocaleLowerCase().includes(query) : category.id === active;
        const visible = match && (query || layout.value === "grouped" || id === selectedId);
        panel.hidden = !visible;
        const group = groups.get(id); group.hidden = !visible;
        if (layout.value === "console" || query) group.open = true;
        if (query && match) for (const disclosure of panel.querySelectorAll("details")) {
          if (disclosure.textContent.toLocaleLowerCase().includes(query)) disclosure.open = true;
        }
        if (layout.value === "console" && !query && category.id === active && available.length > 1) {
          panel.setAttribute("role", "tabpanel"); panel.setAttribute("aria-labelledby", `tab-${id}`);
        } else { panel.removeAttribute("role"); panel.removeAttribute("aria-labelledby"); }
        if (match) { matches++; count++; }
      }
      const link = links.get(category.id);
      if (!query && category.id === active) link.setAttribute("aria-current","page");
      else link.removeAttribute("aria-current");
      link.classList.toggle("search-match", !!query && matches > 0);
    }
    const category = categories.find(item=>item.id===active);
    title.textContent = query ? "Search settings" : category.label;
    description.textContent = query ? `${count} sections match “${search.value.trim()}”. Clear search to return to your category.` : category.description;
    empty.hidden = count > 0;
  }
  function followHash() {
    const hash = location.hash.slice(1);
    const category = categories.find(item=>`category-${item.id}` === hash || item.panels.includes(hash) || item.panels.some(id=>document.getElementById(id)?.contains(document.getElementById(hash))));
    if (category) {
      active = category.id;
      const panelId = category.panels.find(id => id === hash || document.getElementById(id)?.contains(document.getElementById(hash)));
      if (panelId) { selectedPanels.set(active, panelId); if (groups.has(panelId)) groups.get(panelId).open = true; }
    }
    search.value = ""; render();
    const target = document.getElementById(hash);
    for (let node = target; node && node !== main; node = node.parentElement) {
      if (node.tagName === "DETAILS") node.open = true;
    }
  }
  search.addEventListener("input",render);
  window.addEventListener("hashchange",followHash);
  window.addEventListener("popstate",followHash);
  // Container workflows mount asynchronously. Classify newly mounted panels too.
  new MutationObserver(render).observe(main,{childList:true});
  followHash();
});
