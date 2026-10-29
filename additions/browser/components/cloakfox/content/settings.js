import { initMediaWebsiteLabels, initCameraExposure, initMicrophoneExposure } from "./media-label-controls.mjs";
import { getPersonaHardwareFamilies } from "resource:///modules/CloakfoxBayesianNetwork.sys.mjs";
import { listBrowserFamilies, listBrowserVersions, normalizeBrowserSelection } from "resource:///modules/CloakfoxBrowserProfiles.sys.mjs";
import { PRESETS, browserValues, screenValues, languageValues, gpuValues } from "./settings-presets.mjs";
import { findSimilarPersonas, comparePersonaTraits } from "./persona-similarity.mjs";
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
const { AppConstants } = ChromeUtils.importESModule("resource://gre/modules/AppConstants.sys.mjs");
const browserCapabilities = () => Object.freeze({
  gecko: Object.freeze({ available: true, version: AppConstants.MOZ_APP_VERSION }),
  chromium: Object.freeze({ available: true, version: "154.0" }),
  webkit: Object.freeze({ available: true, version: "26.0" }),
});

// Write a container's cloak_cfg and keep its H2/H3 wire profile coherent
// with the persona in one step. Used by every cloak_cfg (re)write below.
function persistCloakCfg(ucid, seed, clearOverrides = false, allowUnavailable = false) {
  const cfg = buildCloakCfg(seed, ucid, clearOverrides, allowUnavailable);
  // Build successfully before discarding saved fields; keep region/privacy policy.
  if (clearOverrides) clearAllOverrides(ucid);
  Services.prefs.setStringPref(cloakCfgPref(ucid), cfg);
  let ua = "";
  try { ua = JSON.parse(cfg)["navigator.userAgent"] || ""; } catch (_e) {}
  writeHttpProfilePrefs(ucid, ua);
}
const { KEY_TYPES, readOverrides, setOverride, setOverrides, clearOverride, clearAllOverrides, applyOverrides, setContainerGPUProfilesEnabled, requireContainerRenderingModesDisabled } =
  ChromeUtils.importESModule("resource:///modules/CloakfoxOverrides.sys.mjs");

const { ContextualIdentityService } = ChromeUtils.importESModule(
  "moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs");
const { forgetContainerData } = ChromeUtils.importESModule(
  "resource:///modules/CloakfoxIdentityActions.sys.mjs");

const { getChromiumPresentation, setChromiumPresentation } = ChromeUtils.importESModule(
  "resource:///modules/CloakfoxEnginePreferences.sys.mjs"
);

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
function buildCloakCfg(seedB64, ucid = null, clearOverrides = false, allowUnavailable = false) {
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
    ucid, base, clearOverrides ? {} : readOverrides(ucid), allowUnavailable));
}

// ── container enumeration ──────────────────────────────────────────

function getContainers() {
  const list = [{ ucid: 0, name: "Default (no container)" }];
  try {
    for (const id of ContextualIdentityService.getPublicIdentities()) {
      list.push({ ucid: id.userContextId, name: ContextualIdentityService.getUserContextLabel(id.userContextId) || id.name || `Container ${id.userContextId}` });
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

function effectiveSimilarityConfig(ucid) {
  const seed = Services.prefs.getStringPref(masterSeedPref(ucid), "");
  if (seed) return JSON.parse(buildCloakCfg(seed, ucid));
  return getCloakCfg(ucid);
}

function renderPersonaSimilarity() {
  const summary = document.getElementById("cfx-similarity-summary");
  const results = document.getElementById("cfx-similarity-results");
  const ucid = Number(document.getElementById("cfx-container-select").value);
  const currentName = getContainers().find(container => Number(container.ucid) === ucid)?.name || "Current container";
  results.replaceChildren();
  let candidate;
  try { candidate = effectiveSimilarityConfig(ucid); }
  catch (error) { summary.textContent = "Could not read this identity: " + error.message; return; }
  if (!candidate) { summary.textContent = "This container has no applied identity. Generate or apply one first."; return; }
  let compared = 0, matches = 0, unavailable = 0;
  for (const container of getContainers()) {
    if (Number(container.ucid) === ucid) continue;
    const row = document.createElement("details"); row.className = "similarity-result similarity-bar-row";
    const barSummary = document.createElement("summary");
    const name = document.createElement("strong"); name.textContent = container.name;
    barSummary.append(name);
    const indicator = document.createElement("span"); indicator.className = "similarity-expand-label"; indicator.textContent = "View matching fields";
    const detail = document.createElement("div"); detail.className = "similarity-detail";
    try {
      const cfg = effectiveSimilarityConfig(container.ucid);
      const comparison = comparePersonaTraits(candidate, cfg);
      if (!cfg || comparison.compared < 90) {
        unavailable++;
        detail.textContent = cfg ? "Not enough comparable fields." : "No applied identity yet.";
      } else {
        compared++;
        if (comparison.tooClose) { matches++; row.classList.add("similarity-close"); }
        const score = document.createElement("span");
        score.className = "similarity-score";
        score.textContent = `${comparison.score}/100${comparison.tooClose ? " · Close match" : ""}`;
        barSummary.title = `${container.name}: ${comparison.score}/100 trait overlap. Click to view matching fields.`;
        const track = document.createElement("span"); track.className = "similarity-bar-track";
        track.setAttribute("aria-hidden", "true");
        const fill = document.createElement("span"); fill.className = "similarity-bar-fill";
        fill.style.width = `${comparison.score}%`; track.append(fill);
        barSummary.append(score, track);
        const fields = document.createElement("dl");
        fields.className = "similarity-shared-fields";
        for (const field of comparison.sharedFields) {
          const label = document.createElement("dt");
          label.textContent = FIELD_LABELS[field.key] || ({"webGl:vendor":"Graphics vendor","webGl:renderer":"Graphics renderer",fonts:"Fonts"})[field.key] || field.key;
          const technical = document.createElement("small"); technical.textContent = field.key; label.append(technical);
          const value = document.createElement("dd");
          value.textContent = Array.isArray(field.value) ? field.value.join(", ") : String(field.value);
          fields.append(label, value);
        }
        const sharedHeading = document.createElement("p");
        sharedHeading.textContent = comparison.sharedFields.length ? "Same values in both containers" : "No matching fields.";
        detail.append(sharedHeading, fields);
      }
    } catch (_error) { unavailable++; detail.textContent = "Identity could not be read; not compared."; }
    barSummary.append(indicator);
    row.append(barSummary, detail); results.append(row);
  }
  summary.textContent = `Checking: ${currentName}. ${matches ? `${matches} close match${matches === 1 ? "" : "es"} found` : compared ? "No close matches found" : "No other identities available to compare"}. Compared with ${compared} other container${compared === 1 ? "" : "s"}.${unavailable ? ` ${unavailable} unavailable or incomplete.` : ""}`;
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
    try {
      if (select.value === "auto") {
        setOverrides(ucid, Object.fromEntries(ownedKeys.map(key => [key, null])));
        Services.prefs.clearUserPref(presetPref);
      } else {
        const item = definition.items.find(p => p.id === select.value);
        setOverrides(ucid, definition.values(item, cfg || {}));
        Services.prefs.setStringPref(presetPref, select.value);
      }
    } catch (error) {
      select.value = ownedKeys.some(key => key in overrides) ? (match || "custom") : "auto";
      window.alert(error.message);
      return;
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
  "navigator.userAgent": "User-Agent",
  "navigator.appVersion": "App version",
  "navigator.oscpu": "Operating system / CPU",
  "headers.User-Agent": "User-Agent header",
  "navigator.language": "Browser language",
  "headers.Accept-Language": "Preferred languages header",
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
  if (["mediaDevices:micros", "mediaDevices:webcams", "mediaDevices:speakers"].includes(key)) row.classList.add("media-device-limit");

  const k = document.createElement("span");
  k.className = "k";
  k.textContent = FIELD_LABELS[key] || label;
  k.title = key;
  if (["navigator.userAgent", "navigator.appVersion", "navigator.oscpu", "headers.User-Agent", "navigator.language", "headers.Accept-Language"].includes(key)) {
    k.classList.add("identity-field-label");
    const technical = document.createElement("small");
    technical.textContent = key;
    k.append(technical);
  }

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
  const managedIdentity = ["navigator.userAgent", "navigator.appVersion", "navigator.oscpu", "headers.User-Agent"].includes(key);
  if (managedIdentity) {
    const field = document.createElement("div");
    field.className = "identity-managed-field";
    const value = document.createElement("span");
    value.className = "identity-field-value";
    value.textContent = sval;
    value.title = String(rawVal ?? sval);
    const tools = document.createElement("div");
    tools.className = "identity-field-tools";
    const link = document.createElement("a");
    link.href = "#cfx-persona-panel";
    link.textContent = "Edit in Identity generator →";
    const custom = document.createElement("button");
    custom.type = "button";
    custom.className = "identity-custom-override";
    custom.textContent = key in overrides ? "Edit custom override" : "Custom override";
    custom.setAttribute("aria-label", `${custom.textContent}: ${label}`);
    custom.addEventListener("click", () => {
      value.replaceWith(v);
      tools.hidden = true;
      openEditMode();
    });
    tools.append(link, custom);
    if (key in overrides) value.classList.add("v-overridden");
    field.append(value, tools);
    row.append(k, field, actions);
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

function mountMediaDeviceTabs(grid, advanced, panels) {
  const labels = { microphone: "Microphones", camera: "Cameras", speaker: "Speakers" };
  const kinds = Object.keys(labels), buttons = new Map();
  const tabs = document.createElement("div"); tabs.className = "media-device-tabs";
  tabs.setAttribute("role", "tablist"); tabs.setAttribute("aria-label", "Media device categories");
  function activate(kind, focus = false, persist = true) {
    if (!panels.has(kind)) return;
    grid.dataset.mediaDeviceTab = kind;
    for (const [name, panel] of panels) {
      const chosen = name === kind;
      panel.hidden = !chosen;
      buttons.get(name).setAttribute("aria-selected", String(chosen));
      buttons.get(name).tabIndex = chosen ? 0 : -1;
    }
    if (persist) {
      const url = new URL(location.href); url.hash = `cfx-${kind}-configuration`;
      history.replaceState({...history.state, mediaDeviceTab:kind}, "", url);
    }
    if (focus) buttons.get(kind).focus();
  }
  for (const kind of kinds) {
    const button = document.createElement("button"); button.type = "button";
    button.id = `cfx-device-tab-${kind}`; button.textContent = labels[kind];
    button.setAttribute("role", "tab"); button.setAttribute("aria-controls", panels.get(kind).id);
    button.addEventListener("click", () => activate(kind));
    button.addEventListener("keydown", event => {
      const i = kinds.indexOf(kind);
      const target = event.key === "ArrowRight" ? kinds[(i+1)%kinds.length]
        : event.key === "ArrowLeft" ? kinds[(i+kinds.length-1)%kinds.length]
        : event.key === "Home" ? kinds[0] : event.key === "End" ? kinds.at(-1) : null;
      if (target) { event.preventDefault(); activate(target,true); }
    });
    panels.get(kind).setAttribute("aria-labelledby",button.id);
    tabs.append(button); buttons.set(kind,button);
  }
  const hashKind = location.hash.match(/^#cfx-(camera|microphone|speaker)-/)?.[1];
  activate(grid.dataset.mediaDeviceTab || hashKind || history.state?.mediaDeviceTab || "camera",false,false);
  const group = document.createElement("div"); group.className = "media-device-group";
  panels.get(kinds[0]).before(group);
  group.append(tabs, ...panels.values());
  grid._selectMediaDeviceTab = activate;
}
window.addEventListener("hashchange", () => {
  const target = document.getElementById(location.hash.slice(1));
  const panel = target?.closest(".media-device-panel");
  if (panel) document.getElementById("grp-media")?._selectMediaDeviceTab?.(panel.dataset.device,false,false);
});

function populateGrid(id, cfg, rows, ucid, overrides, onChange) {
  const grid = document.getElementById(id);
  if (!grid) return;
  // Preserve live device controls while rebuilding their maximum rows.
  // Moving the same nodes keeps drafts, focus targets and event handlers.
  const deviceControls = id === "grp-media" ? new Map([
    ["mediaDevices:micros", document.getElementById("cfx-microphone-configuration")],
    ["mediaDevices:webcams", document.getElementById("cfx-camera-configuration")],
    ["mediaDevices:speakers", document.getElementById("cfx-speaker-configuration")],
  ]) : new Map();
  for (const controls of deviceControls.values()) controls?.remove();
  // Clear existing children EXCEPT static elements declared in HTML
  // (e.g. timezone group has a <select>; we never wipe that).
  Array.from(grid.querySelectorAll(".spoof-row.dyn")).forEach(n => n.remove());
  if (PRESET_GROUPS[id]) grid.appendChild(makePresetRow(PRESET_GROUPS[id], cfg, ucid, overrides, onChange));
  const wasOpen = grid.querySelector(".advanced-fields")?.open;
  grid.querySelector(".advanced-fields")?.remove();
  const advanced = document.createElement("details"); advanced.className = "advanced-fields"; advanced.open = wasOpen ?? !Services.prefs.getBoolPref("cloakfox.ui.collapse_advanced", false);
  const summary = document.createElement("summary"); summary.textContent = "Advanced field overrides"; advanced.append(summary);
  if (id === "grp-media") {
    const note = document.createElement("p"); note.className = "media-device-note";
    note.textContent = "Device limits and camera access apply to this container. Website-facing names apply across containers when generic media labels are enabled. Reload websites after changes; existing streams keep their current labels.";
    advanced.append(note);
  }
  const devicePanels = new Map();
  for (const [label, key] of rows) {
    const row = makeRow(label, key, cfg, ucid, overrides, onChange);
    (["grp-graphics", "grp-locale", "grp-geo", "grp-network"].includes(id) || FIELD_CHOICES[key] || KEY_TYPES[key] === "bool" ? grid : advanced).appendChild(row);
    const controls = deviceControls.get(key);
    if (controls) {
      const kind = key === "mediaDevices:micros" ? "microphone" : key === "mediaDevices:webcams" ? "camera" : "speaker";
      const panel = document.createElement("section"); panel.className = "media-device-panel";
      panel.id = `cfx-device-panel-${kind}`; panel.dataset.device = kind;
      panel.setAttribute("role", "tabpanel"); panel.tabIndex = 0;
      advanced.append(panel); panel.append(row,controls); devicePanels.set(kind,panel);
    }
  }
  if (devicePanels.size) mountMediaDeviceTabs(grid,advanced,devicePanels);
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
  const renderer = cfg["webGl:backend_profile"] === true
    ? "WebGL compatible profile"
    : (cfg["webGl:renderer"] || "?").slice(0, 50);
  const ua = String(cfg["navigator.userAgent"] || "");
  const browserMatch = ua.match(/(?:Edg|Chromium|Chrome|Firefox|Version)\/(\d+)/);
  const browser = ua.includes("Edg/") ? "Edge"
    : ua.includes("Chromium/") ? "Chromium"
    : ua.includes("Chrome/") ? "Chrome"
    : ua.includes("Firefox/") ? "Firefox"
    : ua.includes("Safari/") ? "Safari" : "Browser";
  const browserLabel = `${browser}${browserMatch ? ` ${browserMatch[1]}` : ""}`;
  const tag = shortSeedTag(seedB64);
  el.textContent = `${browserLabel} · ${platform} · ${w}×${h}@${dpr}x · ${hwc}-core · ${renderer}${tag ? "  " + tag : ""}`;
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
  document.getElementById("cfx-check-similarity").addEventListener("click", renderPersonaSimilarity);
  document.getElementById("cfx-container-select").addEventListener("change", () => {
    document.getElementById("cfx-similarity-results").replaceChildren();
    document.getElementById("cfx-similarity-summary").textContent = "Not checked for this container. Select Check similarity.";
  });
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
    const status = document.getElementById("cfx-chromium-status");
    if (!chromium) {
      status.textContent = "These settings are saved and editable now, but only apply after a desktop Chrome, Edge or Chromium identity is generated and applied.";
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

  const presentationEl = document.getElementById("cfx-chromium-presentation");
  presentationEl.addEventListener("change", () => {
    const status = document.getElementById("cfx-chromium-presentation-status");
    try {
      setChromiumPresentation(Number(selectEl.value), presentationEl.value);
      Services.prefs.savePrefFile(null);
      status.textContent = "Preference saved for this container. Chromium switching is not available in this build; existing tabs keep their current engine and window.";
    } catch (error) {
      status.textContent = `Could not save presentation: ${error.message}`;
    }
  });

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
    const requested = history.state?.editingContainer ?? new URLSearchParams(window.location.search).get("ucid");
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
  function rebuildCloakCfg(ucid, allowUnavailable = false) {
    const seed = Services.prefs.getStringPref(masterSeedPref(ucid), "");
    if (seed) {
      persistCloakCfg(ucid, seed, false, allowUnavailable);
    }
  }
  const generateNew = document.getElementById("cfx-generate-new");

  function selectedBrowser() {
    return document.querySelector(".browser-family-tile.is-selected")?.dataset.browser || "firefox";
  }

  function updateBrowserPreview() {
    document.getElementById("cfx-applied-identity-details")?.remove();
    document.querySelector(".profile-preview-label").textContent = "Generate a new identity";
    const browser = selectedBrowser();
    const versionSelect = document.getElementById("cfx-persona-version");
    const version = versionSelect.selectedOptions[0];
    const os = document.getElementById("cfx-persona-filter").selectedOptions[0]?.textContent || "All operating systems";
    const hardware = document.getElementById("cfx-persona-hardware").selectedOptions[0]?.textContent || "Any graphics family";
    const labels = {firefox:"Firefox",chrome:"Chrome",edge:"Microsoft Edge",chromium:"Chromium",safari:"Safari"};
    const label = labels[browser] || browser;
    const major = parseInt(versionSelect.value, 10) || parseInt(AppConstants.MOZ_APP_VERSION, 10);
    const osToken = os === "Windows" ? "Windows NT 10.0; Win64; x64" : os === "macOS" ? "Macintosh; Intel Mac OS X 10_15_7" : "X11; Linux x86_64";
    const chromeUA = `Mozilla/5.0 (${osToken}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${major}.0.0.0 Safari/537.36`;
    const ua = browser === "firefox" ? `Mozilla/5.0 (${osToken}; rv:${major}.0) Gecko/20100101 Firefox/${major}.0` :
      browser === "edge" ? `${chromeUA} Edg/${major}.0.0.0` :
      browser === "chromium" ? chromeUA.replace("Chrome/", "Chromium/") :
      browser === "safari" ? `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/${major}.0 Safari/605.1.15` : chromeUA;
    document.getElementById("cfx-profile-preview-text").textContent = `${label} ${version?.textContent || ""} · ${os}`;
    document.getElementById("cfx-profile-preview-ua").textContent = ua;
    const traits = document.getElementById("cfx-profile-preview-traits");
    traits.replaceChildren(...[
      os === "Windows" ? "Win32" : os === "macOS" ? "MacIntel" : os === "Linux" ? "Linux x86_64" : "BrowserForge OS",
      hardware, "Desktop", `${label} identity`, "Engine selected separately",
    ].map(text => { const span = document.createElement("span"); span.textContent = text; return span; }));
    const confidence = version?.dataset.confidence || "high";
    const badge = document.getElementById("cfx-profile-confidence");
    badge.dataset.confidence = confidence;
    badge.textContent = confidence === "lower" ? "Lower confidence" : "High confidence";
    const selection = normalizeBrowserSelection({ browser, version: versionSelect.value }, browserCapabilities());
    generateNew.disabled = !selection;
    generateNew.title = selection ? "" : "Choose a supported identity profile.";
  }

  function showAppliedIdentity(cfg) {
    if (!cfg) return;
    const ua = cfg["navigator.userAgent"] || "";
    const os = /Windows/.test(ua) ? "Windows" : /Macintosh|Mac OS/.test(ua) ? "macOS" : /Linux|X11/.test(ua) ? "Linux" : cfg["navigator.platform"] || "Unknown OS";
    const browser = ua.match(/(?:Firefox|Edg|Chromium|Chrome|Version)\/[\d.]+/g)?.at(-1)?.replace("/", " ") || "Applied identity";
    document.querySelector(".profile-preview-label").textContent = "Applied identity";
    document.getElementById("cfx-profile-preview-text").textContent = `${browser} · ${os}`;
    document.getElementById("cfx-profile-preview-ua").textContent = ua;
    const chips = [browser, os];
    if (cfg["screen.width"] && cfg["screen.height"]) chips.push(`${cfg["screen.width"]} × ${cfg["screen.height"]}`);
    if (cfg["window.devicePixelRatio"]) chips.push(`${Number(cfg["window.devicePixelRatio"]).toFixed(2).replace(/\.?0+$/, "")}× pixel density`);
    if (cfg["navigator.hardwareConcurrency"]) chips.push(`${cfg["navigator.hardwareConcurrency"]} CPU cores`);
    if (cfg["webGl:renderer"]) chips.push(cfg["webGl:renderer"]);
    const overrideCount = Object.keys(readOverrides(Number(selectEl.value))).length;
    chips.push(overrideCount ? `${overrideCount} manual override${overrideCount === 1 ? "" : "s"} active` : "No manual overrides");
    document.getElementById("cfx-profile-preview-traits").replaceChildren(...chips.map(text => {
      const chip = document.createElement("span"); chip.textContent = text.length > 48 ? text.slice(0, 45) + "…" : text; chip.title = text; return chip;
    }));
    document.getElementById("cfx-applied-identity-details")?.remove();
    const details = document.createElement("details"); details.id = "cfx-applied-identity-details";
    const summary = document.createElement("summary"); summary.textContent = "View identity details";
    const values = document.createElement("dl");
    const ucid = Number(selectEl.value);
    const entries = [
      ["Language", cfg["navigator.language"] || cfg["locale:language"]],
      ["Timezone", Services.prefs.getStringPref(tzPref(ucid), "UTC (default)")],
      ["Audio sample rate", cfg["AudioContext:sampleRate"] ? `${cfg["AudioContext:sampleRate"]} Hz` : null],
      ["Audio channels", cfg["AudioContext:maxChannelCount"]],
      ["Fonts", Array.isArray(cfg.fonts) ? `${cfg.fonts.length} configured fonts` : null],
    ];
    for (const [label, value] of entries) {
      if (value === undefined || value === null || value === "") continue;
      const term = document.createElement("dt"); term.textContent = label;
      const description = document.createElement("dd"); description.textContent = String(value);
      values.append(term, description);
    }
    const similarity = document.createElement("a"); similarity.href = "#cfx-persona-similarity"; similarity.textContent = "View persona similarity results →";
    details.append(summary, values, similarity);
    document.querySelector(".profile-preview-copy").append(details);
  }

  function renderBrowserPicker(ucid) {
    const capabilities = browserCapabilities();
    const saved = Services.prefs.getStringPref(`cloakfox.container.${ucid}.persona_browser`, "firefox");
    const active = listBrowserFamilies(capabilities).find(item => item.id === saved && item.available)?.id || "firefox";
    const grid = document.getElementById("cfx-browser-families");
    grid.replaceChildren();
    for (const family of listBrowserFamilies(capabilities)) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `browser-family-tile${family.id === active ? " is-selected" : ""}`;
      button.dataset.browser = family.id;
      button.disabled = !family.available;
      button.title = family.unavailableReason;
      button.setAttribute("aria-pressed", String(family.id === active));
      button.setAttribute("aria-label", family.available ? family.label : `${family.label}: ${family.unavailableReason}`);
      const initials = {firefox:"Fx",chrome:"Ch",edge:"Ed",chromium:"Cr",safari:"Sa",custom:"Cu"}[family.id];
      const engine = family.engine ? `Identity profile · engine separate` : "Advanced override";
      button.innerHTML = `<span class="browser-tile-top"><span class="browser-family-logo browser-logo-${family.id}">${initials}</span><span class="browser-ready-dot"></span></span><strong>${family.label}</strong><small>${family.available ? engine : family.unavailableReason}</small>`;
      button.addEventListener("click", () => {
        for (const tile of grid.children) { tile.classList.remove("is-selected"); tile.setAttribute("aria-pressed", "false"); }
        button.classList.add("is-selected"); button.setAttribute("aria-pressed", "true");
        populateBrowserVersions(ucid, family.id);
      });
      grid.append(button);
    }
    populateBrowserVersions(ucid, active);
  }

  function populateBrowserVersions(ucid, family) {
    const select = document.getElementById("cfx-persona-version");
    const saved = Services.prefs.getStringPref(`cloakfox.container.${ucid}.persona_version`, "");
    select.replaceChildren();
    for (const version of listBrowserVersions(family, browserCapabilities())) {
      const option = new Option(version.label, version.value);
      option.dataset.confidence = version.confidence;
      select.append(option);
    }
    select.value = [...select.options].some(option => option.value === saved) ? saved : select.options[0]?.value || "";
    updateBrowserPreview();
    if (document.documentElement.dataset.identityBrowser !== family) {
      document.documentElement.dataset.identityBrowser = family;
      window.dispatchEvent(new CustomEvent("cloakfox-browser-family-change", { detail: { family } }));
    }
  }

  let refreshCameraExposure = () => {};
  let refreshMicrophoneExposure = () => {};
  function refreshContainerRenderingOptions(ucid, cfg) {
    const enabled = Services.prefs.getBoolPref("cloakfox.experimental.canvas_pipeline", false);
    const gpuProfiles = Services.prefs.getBoolPref("cloakfox.opt.container_rendering_profiles", false);
    const requests = readOverrides(ucid);
    for (const control of document.querySelectorAll("input[data-container-rendering]")) {
      const key = control.dataset.containerRendering;
      const requested = requests[key] === true ||
        (key === "rendering:gpu_observed" && !Object.hasOwn(requests, key) && cfg?.[key] === true);
      control.checked = requested;
      // A saved request can always be turned off, including if its dependency
      // became unavailable after an import or external preference change.
      control.disabled = !requested && (!enabled || (key !== "geometry:canonical" && !gpuProfiles) ||
        (key === "rendering:gpu_observed" && requests["rendering:gpu_reference"] !== true));
      control.onchange = () => {
        const status = document.getElementById("cfx-container-rendering-status");
        try {
          const enable = control.checked;
          if (key === "rendering:gpu_reference" && !enable) {
            setOverrides(ucid, { "rendering:gpu_reference": false, "rendering:gpu_observed": false });
          } else {
            setOverride(ucid, key, enable);
          }
          rebuildCloakCfg(ucid, !enable);
          refreshContainer();
          status.textContent = "Saved for this container. Reload pages and restart workers to use the new rendering policy.";
        } catch (error) {
          refreshContainerRenderingOptions(ucid, getCloakCfg(ucid));
          status.textContent = error.message;
        }
      };
    }
    const reference = cfg?.["rendering:gpu_profile"];
    const errors = [cfg?.["rendering:gpu_profile:error"], cfg?.["rendering:geometry_profile:error"]].filter(Boolean);
    document.getElementById("cfx-container-rendering-status").textContent = errors.length ? errors.join(" · ")
      : reference?.mode === "observed-reference" ? "Observed GPU compatibility saved for this container. Reload pages and restart workers to apply its native policy."
      : reference?.mode === "reference" ? "Reference-based GPU profile saved for this container. Live contexts keep their captured policy until reload."
      : "Rendering requests and saved identity are separate for each container. Reload pages after changes.";
  }
  function refreshContainer() {
    const ucid = parseInt(selectEl.value, 10) || 0;
    presentationEl.value = getChromiumPresentation(ucid);
    document.getElementById("cfx-chromium-presentation-status").textContent =
      "Chromium switching is not available in this build. This preference is saved for a future release.";
    const cfg = getCloakCfg(ucid);
    const overrides = readOverrides(ucid);
    refreshContainerRenderingOptions(ucid, cfg);
    const seedB64 = Services.prefs.getStringPref(masterSeedPref(ucid), "");
    const onEdit = () => { rebuildCloakCfg(ucid); refreshContainer(); };

    const generatedFonts = seedB64 ? fillPersonaKeys(seedB64, ucid) : {};
    const fontUA = generatedFonts["navigator.userAgent"] || "";
    const fontOS = /Windows/.test(fontUA) ? "Windows" : /Macintosh|Mac OS/.test(fontUA) ? "macOS" : /Linux|X11/.test(fontUA) ? "Linux" : "Not generated";
    document.getElementById("cfx-font-source").textContent = `Persona source OS: ${fontOS} · ${"fonts" in overrides ? "Custom font override active" : "Using generated fonts"}`;
    for (const [id, fonts] of [["cfx-font-generated", generatedFonts.fonts], ["cfx-font-effective", cfg?.fonts]]) {
      const target = document.getElementById(id); target.replaceChildren();
      if (!Array.isArray(fonts)) { target.textContent = "No configured font list."; continue; }
      for (const font of fonts) { const chip = document.createElement("span"); chip.textContent = font; target.append(chip); }
    }
    document.getElementById("cfx-font-custom").value = (overrides.fonts || generatedFonts.fonts || []).join("\n");
    document.getElementById("cfx-font-save").onclick = () => {
      try {
        const fonts = [...new Set(document.getElementById("cfx-font-custom").value.split(/\n/).map(value => value.trim()).filter(Boolean))];
        setOverride(ucid, "fonts", fonts); rebuildCloakCfg(ucid); refreshContainer();
        document.getElementById("cfx-font-status").textContent = "Custom font list saved. Reload website tabs.";
      } catch (error) { document.getElementById("cfx-font-status").textContent = error.message; }
    };
    document.getElementById("cfx-font-reset").onclick = () => {
      try { clearOverride(ucid, "fonts"); rebuildCloakCfg(ucid); refreshContainer(); document.getElementById("cfx-font-status").textContent = "Generated fonts restored. Reload website tabs."; }
      catch (error) { document.getElementById("cfx-font-status").textContent = error.message; }
    };
    const mode = personaOSMode(ucid);
    const osLabels = { windows:"Windows", macos:"macOS", linux:"Linux", legacy:"all" };
    const hostLabel = { Darwin:"macOS", WINNT:"Windows", Linux:"Linux" }[Services.appinfo.OS];
    document.getElementById("cfx-persona-filter").value = mode === "host" ? hostLabel : osLabels[mode];
    renderBrowserPicker(ucid);
    document.getElementById("cfx-persona-os-current").textContent =
      `Saved generation mode: ${mode === "host" ? "this computer’s OS" : osLabels[mode] === "all" ? "all operating systems" : osLabels[mode]}. Custom overrides may differ.`;
    document.getElementById("cfx-persona-choice").value = "-1";
    loadIdentityChoices();
    updateChromiumCompatibility();
    updateNetworkProfile();
    updateHardwareChoices(Services.prefs.getStringPref(`cloakfox.container.${ucid}.persona_hardware`, "auto"));
    updateBrowserPreview();
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
    refreshCameraExposure();
    refreshMicrophoneExposure();
  }
  selectEl.addEventListener("change", () => {
    // Preserve this settings tab's editing target on reload, independently of
    // other settings tabs. Keep category hashes and other query parameters.
    const url = new URL(window.location.href);
    url.searchParams.set("ucid", selectEl.value);
    const state = {...history.state, editingContainer:selectEl.value};
    // about: documents can reject changing the query via the History API.
    // Save per-tab state first so a rejected URL rewrite cannot lose selection
    // or prevent the remaining container-scoped controls from refreshing.
    history.replaceState(state, "");
    try { history.replaceState(state, "", url.href); } catch (_error) { /* state persists on reload */ }
    refreshContainer();
  });
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
    document.getElementById("cfx-generate-new").textContent = "Generate and apply";
    document.getElementById("cfx-persona-help").textContent =
      `${choice.options.length - 1} BrowserForge previews. Both fresh generation and previews use the operating system above. Selecting an OS or preview does not apply it. Custom overrides are kept unless cleared during fresh generation.`;
  }
  document.getElementById("cfx-persona-filter").addEventListener("change", () => { loadIdentityChoices(); updateHardwareChoices(); updateBrowserPreview(); });
  document.getElementById("cfx-persona-hardware").addEventListener("change", updateBrowserPreview);
  document.getElementById("cfx-persona-version").addEventListener("change", updateBrowserPreview);

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
    const identityPrefix = `cloakfox.container.${ucid}.`;
    const savedIdentity = new Map(Services.prefs.getChildList(identityPrefix).filter(name => Services.prefs.prefHasUserValue(name)).map(name => {
      const type = Services.prefs.getPrefType(name);
      return [name, {type, value:type === Services.prefs.PREF_BOOL ? Services.prefs.getBoolPref(name) : type === Services.prefs.PREF_INT ? Services.prefs.getIntPref(name) : Services.prefs.getStringPref(name)}];
    }));
    try {
      if (!["legacy", "windows", "macos", "linux"].includes(mode)) throw new Error("Invalid persona OS mode");
      const browser = selectedBrowser();
      const version = document.getElementById("cfx-persona-version").value;
      const selection = normalizeBrowserSelection({ browser, version }, browserCapabilities());
      if (!selection) throw new Error("The selected browser engine is unavailable");
      Services.prefs.setStringPref(personaModePref(ucid), mode);
      if (!Number.isInteger(index) || index < -1 || index >= 30) throw new Error("Select a BrowserForge identity");
      if (index === -1) Services.prefs.clearUserPref(personaIndexPref(ucid));
      else Services.prefs.setIntPref(personaIndexPref(ucid), index);
      const hardware = document.getElementById("cfx-persona-hardware").value;
      const prefix = `cloakfox.container.${ucid}.`;
      Services.prefs.setStringPref(prefix + "persona_browser", selection.browser);
      Services.prefs.setStringPref(prefix + "persona_version", selection.version);
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
      showAppliedIdentity(getCloakCfg(ucid));
      renderPersonaSimilarity();
      status.textContent = "";
      document.getElementById("cfx-persona-similarity-warning")?.remove();
      const comparisons = getContainers().map(container => {
        let cfg = getCloakCfg(container.ucid);
        const savedSeed = Services.prefs.getStringPref(masterSeedPref(container.ucid), "");
        if (savedSeed) {
          try { cfg = JSON.parse(buildCloakCfg(savedSeed, container.ucid)); }
          catch (error) { Cu.reportError(`Could not compare container ${container.ucid}: ${error.message}`); }
        }
        return {...container, cfg};
      });
      const similar = findSimilarPersonas(getCloakCfg(ucid), comparisons, ucid);
      if (similar.length) {
        const warning = document.createElement("div");
        warning.id = "cfx-persona-similarity-warning";
        warning.setAttribute("role", "alert");
        const title = document.createElement("strong");
        title.textContent = "This identity closely resembles another container";
        const explanation = document.createElement("p");
        explanation.textContent = "Identity applied. Generate again or choose different graphics or screen settings for more separation. This compares configured traits; it is not a tracking probability.";
        const list = document.createElement("ul");
        for (const match of similar) {
          const item = document.createElement("li");
          item.textContent = `${match.name}: ${match.score}/100 trait overlap. Shared: ${match.shared.join(", ")}.`;
          list.append(item);
        }
        warning.append(title, explanation, list);
        status.after(warning);
      }
      document.getElementById("cfx-identity-toast")?.remove();
      const toast = document.createElement("div");
      toast.id = "cfx-identity-toast";
      toast.className = "identity-toast";
      toast.setAttribute("role", "status");
      toast.setAttribute("aria-live", "polite");
      const message = document.createElement("div");
      const heading = document.createElement("strong");
      heading.textContent = `${index === -1 ? "New identity applied" : "Selected profile applied"} · ${shortSeedTag(seed)}`;
      const reminder = document.createElement("p");
      reminder.textContent = `${clearOverrides ? "Manual field overrides replaced. " : ""}Reload website tabs to use this identity.`;
      message.append(heading, reminder);
      if (similar.length) {
        toast.classList.add("identity-toast-warning");
        reminder.textContent += ` Similar identity found in ${similar.map(item => item.name).join(", ")}. See the comparison warning in Identity generator.`;
      }
      const dismiss = document.createElement("button");
      dismiss.type = "button";
      dismiss.textContent = "Dismiss";
      dismiss.addEventListener("click", () => toast.remove());
      toast.append(message, dismiss);
      document.body.append(toast);
      // Keep confirmation available long enough to read; hovering or focusing
      // it preserves it until the user dismisses it.
      if (!similar.length) setTimeout(() => {
        if (!toast.matches(":hover, :focus-within")) toast.remove();
      }, 10000);
      const hero = document.querySelector(".current-persona-strip");
      if (hero) {
        hero.classList.remove("hero-flash");
        void hero.offsetWidth;
        hero.classList.add("hero-flash");
      }
    } catch (e) {
      for (const name of Services.prefs.getChildList(identityPrefix)) if (!savedIdentity.has(name)) Services.prefs.clearUserPref(name);
      for (const [name, saved] of savedIdentity) {
        if (saved.type === Services.prefs.PREF_BOOL) Services.prefs.setBoolPref(name, saved.value);
        else if (saved.type === Services.prefs.PREF_INT) Services.prefs.setIntPref(name, saved.value);
        else Services.prefs.setStringPref(name, saved.value);
      }
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
      try {
        if (pref === "cloakfox.opt.container_rendering_profiles") setContainerGPUProfilesEnabled(el.checked);
        else if (pref === "cloakfox.experimental.canvas_pipeline" && !el.checked) {
          requireContainerRenderingModesDisabled();
          if (Services.prefs.getBoolPref("cloakfox.opt.container_rendering_profiles", false)) throw new Error("Disable container GPU profiles before disabling their canonical backend");
          Services.prefs.setBoolPref(pref, false);
        }
        else Services.prefs.setBoolPref(pref, el.checked);
        if (pref === "cloakfox.appearance.colored_inactive_buttons") {
          Services.prefs.savePrefFile(null);
          return;
        }
        document.getElementById("cfx-container-gpu-status").textContent = "Reload pages and restart workers to apply GPU policy changes.";
      } catch (error) {
        el.checked = Services.prefs.getBoolPref(pref, false);
        document.getElementById("cfx-container-gpu-status").textContent = error.message;
      }
      const renderingOwner = parseInt(selectEl.value, 10) || 0;
      refreshContainerRenderingOptions(renderingOwner, getCloakCfg(renderingOwner));
      if (pref === "cloakfox.compat.screen_management") updateChromiumCompatibility();
      if (pref === "cloakfox.opt.gpu_backend_profiles") {
        const ucid = parseInt(selectEl.value, 10) || 0;
        updateHeadline(getCloakCfg(ucid), Services.prefs.getStringPref(masterSeedPref(ucid), ""));
      }
    });
  }
  const canonicalRenderer = document.querySelector('input[data-pref="cloakfox.experimental.canvas_pipeline"]');
  const syncCanonicalDependencies = () => {
    const full = canonicalRenderer.checked;
    for (const pref of ["cloakfox.opt.gpu_backend_profiles", "cloakfox.opt.webgl_typed_readback_disabled"]) {
      const control = document.querySelector(`input[data-pref="${pref}"]`);
      control.disabled = full;
      control.checked = full || Services.prefs.getBoolPref(pref, false);
    }
    const ucid = parseInt(selectEl.value, 10) || 0;
    updateHeadline(getCloakCfg(ucid), Services.prefs.getStringPref(masterSeedPref(ucid), ""));
  };
  canonicalRenderer.addEventListener("change", syncCanonicalDependencies);
  syncCanonicalDependencies();

  initAppearanceControls().catch(error => {
    document.getElementById("cfx-appearance-status").textContent = `Could not read application appearance: ${error.message}`;
  });
  for (const kind of ["camera", "microphone", "speaker"]) {
    initMediaWebsiteLabels(kind, { document, navigator, prefs: Services.prefs, Option });
  }
  refreshCameraExposure = initCameraExposure({ document, navigator,
    getContext: () => {
      const ucid = Number(selectEl.value) || 0, cfg = getCloakCfg(ucid) || {};
      let ids = null;
      if (cfg["mediaDevices:cameraDevices"]) {
        try {
          const parsed = JSON.parse(cfg["mediaDevices:cameraDevices"]);
          ids = Array.isArray(parsed) && parsed.every(id=>typeof id === "string" && id) ? parsed : [];
        } catch (_) { ids = []; }
      } else if (cfg["mediaDevices:cameraDevice"]) ids = [cfg["mediaDevices:cameraDevice"]];
      const maximum = cfg["mediaDevices:webcams"];
      const limit = Number.isInteger(maximum) && maximum >= 0 ? Math.min(maximum,64) : 1;
      return { id: ucid, ids, limit };
    },
    save: ids => {
      const ucid = Number(selectEl.value) || 0;
      setOverrides(ucid, { "mediaDevices:cameraDevice": "",
        "mediaDevices:cameraDevices": ids === null ? "" : JSON.stringify(ids) });
      rebuildCloakCfg(ucid);
      Services.prefs.savePrefFile(null);
      refreshContainer();
    },
  });
  refreshMicrophoneExposure = initMicrophoneExposure({ document, navigator,
    getContext: () => {
      const ucid = Number(selectEl.value) || 0, cfg = getCloakCfg(ucid) || {};
      let ids = null;
      if (cfg["mediaDevices:microphoneDevices"]) {
        try {
          const parsed = JSON.parse(cfg["mediaDevices:microphoneDevices"]);
          ids = Array.isArray(parsed) && parsed.every(id=>typeof id === "string" && id) ? parsed : [];
        } catch (_) { ids = []; }
      }
      const maximum = cfg["mediaDevices:micros"];
      const limit = Number.isInteger(maximum) && maximum >= 0 ? Math.min(maximum,64) : 1;
      return { id: ucid, ids, limit };
    },
    save: ids => {
      const ucid = Number(selectEl.value) || 0;
      setOverrides(ucid, { "mediaDevices:microphoneDevices": ids === null ? "" : JSON.stringify(ids) });
      rebuildCloakCfg(ucid);
      Services.prefs.savePrefFile(null);
      refreshContainer();
    },
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
    {id:"identity",label:"Persona & identity",description:"Generate an identity, edit its reported fields, choose an engine, reset data, or open help.",panels:["cfx-persona-panel","sec-identity","cfx-font-settings","cfx-persona-similarity","sec-appearance","sec-screen-management","cfx-engine-settings","cfx-identity-maintenance","cfx-identity-help"]},
    {id:"display",label:"Display & graphics",description:"Customize screen geometry, virtual screens, pixel density and the graphics identity.",panels:["sec-display","sec-graphics"]},
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
      button.textContent = ({console:"Focused", grouped:"All controls", light:"Light", dark:"Dark"})[value] || text;
      button.title = text; button.dataset.value = value;
      button.addEventListener("click", () => { select.value = value; select.dispatchEvent(new Event("change")); });
      segment.append(button); buttons.push(button);
    }
    const sync = () => buttons.forEach(button => button.setAttribute("aria-pressed", String(button.dataset.value === select.value)));
    select.addEventListener("change", sync); sync();
    appearance.append(segment); return select;
  }
  const layout = appearanceSelect("cfx-layout", "Layout", [["console", "Focused categories"], ["grouped", "All controls"]], "cloakfox.ui.layout", "console");
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
  const contextHeader = document.createElement("div");
  contextHeader.className = "focused-context-header";
  contextHeader.append(identitySummary, tabs);
  header.after(contextHeader);
  // Match the fixed navigation offset to the toolbar even when controls wrap.
  const topbar = document.querySelector(".topbar");
  new ResizeObserver(() => document.body.style.setProperty("--settings-topbar-height", `${topbar.offsetHeight}px`)).observe(topbar);
  const groups = new Map();
  const selectedPanels = new Map();
  // History state is scoped to this settings tab and survives a refresh.
  const savedPanels = history.state?.settingsPanels;
  if (savedPanels && typeof savedPanels === "object") {
    for (const category of categories) {
      const panel = savedPanels[category.id];
      if (category.panels.includes(panel)) selectedPanels.set(category.id, panel);
    }
  }
  function selectSettingsPanel(category, id) {
    selectedPanels.set(category, id);
    history.replaceState({...history.state, settingsPanels:Object.fromEntries(selectedPanels)}, "");
  }
  const chromiumFamilies = new Set(["chrome", "edge", "chromium"]);
  function panelSupportsSelectedBrowser(id) {
    const family = document.documentElement.dataset.identityBrowser ||
      document.querySelector(".browser-family-tile.is-selected")?.dataset.browser || "firefox";
    if (id === "sec-appearance") return family === "firefox";
    if (id === "cfx-engine-settings" || id === "sec-screen-management") return chromiumFamilies.has(family);
    return true;
  }
  function ensureGroups() {
    for (const category of categories) for (const id of category.panels) {
      const panel = document.getElementById(id);
      if (!panel || groups.has(id)) continue;
      const group = document.createElement("details"); group.className = "settings-group"; group.open = true;
      const summary = document.createElement("summary");
      summary.textContent = id === "cfx-persona-panel" ? "Identity generator"
        : id === "sec-identity" ? "Browser fields"
        : id === "cfx-engine-settings" ? "Engine"
        : id === "cfx-identity-help" ? "Help"
        : id === "cfx-identity-maintenance" ? "Reset & data"
        : (panel.querySelector("h2, h3, summary")?.textContent.trim() || category.label);
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
      history.pushState(history.state,"",`#category-${active}`); render();
      if (layout.value === "grouped") groups.get(category.panels.find(id => groups.has(id)))?.scrollIntoView({behavior:"smooth",block:"start"});
      else { title.focus({preventScroll:true}); window.scrollTo(0,0); }
    });
    nav.append(link); links.set(category.id,link);
  });
  function render() {
    ensureGroups();
    // Keep DOM, keyboard and visual order aligned with the sidebar. Only move
    // nodes that are out of place so the mutation observer settles after a pass.
    let previousGroup = contextHeader;
    for (const category of categories) for (const id of category.panels) {
      const group = groups.get(id);
      if (!group) continue;
      if (previousGroup.nextElementSibling !== group) previousGroup.after(group);
      previousGroup = group;
    }
    document.documentElement.dataset.theme = theme.value;
    document.body.dataset.layout = layout.value;
    document.body.dataset.category = active;
    const query = search.value.trim().toLocaleLowerCase();
    const currentCategory = categories.find(item => item.id === active);
    const available = currentCategory.panels.filter(id => groups.has(id) && panelSupportsSelectedBrowser(id));
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
        button.addEventListener("click", () => { selectSettingsPanel(active, id); render(); });
        button.addEventListener("keydown", event => {
          if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
          event.preventDefault();
          const index = available.indexOf(id);
          const next = event.key === "Home" ? 0 : event.key === "End" ? available.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + available.length) % available.length;
          selectSettingsPanel(active, available[next]); render(); tabs.children[next].focus();
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
        const supported = panelSupportsSelectedBrowser(id);
        const match = supported && (query ? `${category.label} ${panel.textContent}`.toLocaleLowerCase().includes(query) : layout.value === "grouped" || category.id === active);
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
    title.textContent = query ? "Search settings" : layout.value === "grouped" ? "All controls" : category.label;
    description.textContent = query ? `${count} sections match “${search.value.trim()}”. Clear search to return to your category.`
      : layout.value === "grouped" ? "The complete settings page. Use the sidebar to jump between sections, or switch to Focused for one category at a time." : category.description;
    empty.hidden = count > 0;
  }
  function followHash() {
    const hash = location.hash.slice(1);
    const category = categories.find(item=>`category-${item.id}` === hash || item.panels.includes(hash) || item.panels.some(id=>document.getElementById(id)?.contains(document.getElementById(hash))));
    if (category) {
      active = category.id;
      const panelId = category.panels.find(id => id === hash || document.getElementById(id)?.contains(document.getElementById(hash)));
      if (panelId) { selectSettingsPanel(active, panelId); if (groups.has(panelId)) groups.get(panelId).open = true; }
    }
    search.value = ""; render();
    const target = document.getElementById(hash);
    for (let node = target; node && node !== main; node = node.parentElement) {
      if (node.tagName === "DETAILS") node.open = true;
    }
  }
  search.addEventListener("input",render);
  // Hold the current category through its gaps; switch only when the next
  // category's first visible section crosses the reading line below the toolbar.
  let scrollTrackingFrame = 0;
  function trackVisibleCategory() {
    scrollTrackingFrame = 0;
    if (layout.value !== "grouped" || search.value.trim()) return;
    const readingLine = topbar.getBoundingClientRect().bottom + 24;
    let nearest = null;
    for (const category of categories) {
      const firstGroup = category.panels.map(id => groups.get(id)).find(group =>
        group && !group.hidden && group.getClientRects().length);
      if (!firstGroup) continue;
      if (!nearest) nearest = category.id;
      if (firstGroup.getBoundingClientRect().top <= readingLine) nearest = category.id;
      else break;
    }
    if (!nearest) return;
    active = nearest;
    for (const [id, link] of links) {
      if (id === active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
  }
  window.addEventListener("scroll", () => {
    if (!scrollTrackingFrame) scrollTrackingFrame = requestAnimationFrame(trackVisibleCategory);
  }, {passive:true});
  window.addEventListener("resize", () => {
    if (!scrollTrackingFrame) scrollTrackingFrame = requestAnimationFrame(trackVisibleCategory);
  });
  window.addEventListener("cloakfox-browser-family-change", render);
  window.addEventListener("hashchange",followHash);
  window.addEventListener("popstate",followHash);
  // Container workflows mount asynchronously. Classify newly mounted panels too.
  new MutationObserver(render).observe(main,{childList:true});
  followHash();
});
