/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox settings page.
 *
 * Runs chrome-privileged (IS_SECURE_CHROME_UI in AboutRedirector), so
 * Services.prefs / Services.contextualIdentityService are available.
 *
 * Surfaces the prefs that live elsewhere in the codebase as a UI:
 *
 *   - cloakfox.enabled                    — global on/off
 *   - cloakfox.container.<ucid>.math_seed — per-container PRNG seed
 *   - cloakfox.container.<ucid>.timezone  — per-container IANA tz
 *   - cloakfox.opt.*                       — 10 stealth-vs-compat toggles
 *   - cloakfox.s.cloak_cfg_<ucid>         — derived JSON the C++ MaskConfig
 *                                            patches consume (regen-only,
 *                                            not user-editable)
 *
 * The "Regenerate" button mirrors what SeedSync does at startup —
 * generates a new math_seed + writes the persona-derived cloak_cfg.
 * Importantly, it shares the SAME fillPersonaKeys path as SeedSync so
 * the JSON shape stays identical (otherwise users who regenerated would
 * end up with a stripped-down cloak_cfg, downgrading their spoof
 * coverage versus a fresh install).
 */

/* global Services, ChromeUtils */

// Chrome pages use ChromeUtils.importESModule rather than raw `import`
// for resource:// modules — the static import syntax doesn't resolve
// resource:// URLs the way it does in .sys.mjs files. importESModule
// returns the module's exports synchronously and works inside the
// document's chrome principal.
const { fillPersonaKeys, pickPersona } = ChromeUtils.importESModule(
  "resource:///modules/CloakfoxPersonas.sys.mjs"
);

const PREF_ENABLED = "cloakfox.enabled";

// ── pref name helpers ───────────────────────────────────────────────

const masterSeedPref = (ucid) => `cloakfox.container.${ucid}.math_seed`;
const cloakCfgPref   = (ucid) => `cloakfox.s.cloak_cfg_${ucid}`;
const tzPref         = (ucid) => `cloakfox.container.${ucid}.timezone`;

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

// MUST match SeedSync.buildCloakCfg shape — the persona keys come from
// fillPersonaKeys (BF-driven pool); the 4 hash-based seeds come from
// u32 derivation. If either layer drifts, regen and SeedSync auto-gen
// produce different configs and downstream spoof coverage diverges.
function buildCloakCfg(seedB64) {
  return JSON.stringify({
    "canvas:seed": u32(seedB64, 0),
    "audio:seed": u32(seedB64, 1),
    "font:seed": u32(seedB64, 2),
    "font:spacing_seed": u32(seedB64, 3),
    ...fillPersonaKeys(seedB64),
  });
}

// ── container enumeration ──────────────────────────────────────────

function getContainers() {
  const list = [{ ucid: 0, name: "Default (no container)" }];
  try {
    const identities = Services.contextualIdentityService.getPublicIdentities();
    for (const id of identities) {
      list.push({
        ucid: id.userContextId,
        name: id.name || `Container ${id.userContextId}`,
      });
    }
  } catch (_e) { /* CIS may be unavailable in some build configs */ }
  return list;
}

// ── persona summary ─────────────────────────────────────────────────

// Render the picked persona as a human-readable one-liner so users can
// see what each container is pretending to be. Pulls a few key fields
// out of the persona dict; full dict is available in the cloak_cfg pref.
function personaSummary(seedB64) {
  if (!seedB64) return "(not set)";
  try {
    const p = pickPersona(seedB64);
    const platform = p["navigator.platform"] || "?";
    const w = p["screen.width"] ?? "?";
    const h = p["screen.height"] ?? "?";
    const dpr = p["window.devicePixelRatio"] ?? "?";
    const renderer = (p["webGl:renderer"] || "?").slice(0, 40);
    const hwc = p["navigator.hardwareConcurrency"] ?? "?";
    return `${platform} · ${w}×${h}@${dpr}x · ${hwc}-core · ${renderer}`;
  } catch (e) {
    return `(error: ${e.message})`;
  }
}

// ── timezone list ───────────────────────────────────────────────────

// Common IANA names. Not exhaustive — power users can set any IANA
// string via about:config (cloakfox.container.<ucid>.timezone). This
// list covers the common cases without being a 600-entry dropdown.
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
  const enabledEl   = document.getElementById("cfx-enabled");
  const selectEl    = document.getElementById("cfx-container-select");
  const masterEl    = document.getElementById("cfx-seed-master");
  const personaEl   = document.getElementById("cfx-persona-summary");
  const tzSelectEl  = document.getElementById("cfx-tz-select");
  const regenBtn    = document.getElementById("cfx-regenerate");
  const clearBtn    = document.getElementById("cfx-clear");

  // Master enable toggle.
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
  // Skip the prepopulated "Default" option in the HTML — we just
  // re-added it above. Strip the duplicate.
  if (selectEl.options.length > 1 && selectEl.options[0].value === "0" &&
      selectEl.options[1].value === "0") {
    selectEl.options[0].remove();
  }

  // Honor ?ucid=N deep-link from the popup — pre-selects the matching
  // container so the user lands on their tab's settings.
  try {
    const params = new URLSearchParams(window.location.search);
    const requested = params.get("ucid");
    if (requested !== null) {
      const targetUcid = String(parseInt(requested, 10) || 0);
      if (Array.from(selectEl.options).some(o => o.value === targetUcid)) {
        selectEl.value = targetUcid;
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

  function refreshContainer() {
    const ucid = parseInt(selectEl.value, 10) || 0;
    const seed = Services.prefs.getStringPref(masterSeedPref(ucid), "");
    masterEl.textContent = seed
      ? seed.slice(0, 28) + "…" + seed.slice(-4)  // truncate for display
      : "(not set)";
    personaEl.textContent = personaSummary(seed);
    tzSelectEl.value = Services.prefs.getStringPref(tzPref(ucid), "");
  }
  selectEl.addEventListener("change", refreshContainer);
  refreshContainer();

  // Timezone picker — empty value clears the pref so the global UTC
  // default applies; any other value pins this container's timezone.
  tzSelectEl.addEventListener("change", () => {
    const ucid = parseInt(selectEl.value, 10) || 0;
    if (tzSelectEl.value === "") {
      Services.prefs.clearUserPref(tzPref(ucid));
    } else {
      Services.prefs.setStringPref(tzPref(ucid), tzSelectEl.value);
    }
  });

  // Regenerate persona — share the same path as SeedSync so the
  // resulting cloak_cfg matches what auto-gen produces.
  regenBtn.addEventListener("click", () => {
    const ucid = parseInt(selectEl.value, 10) || 0;
    const seed = randomSeedB64();
    Services.prefs.setStringPref(masterSeedPref(ucid), seed);
    Services.prefs.setStringPref(cloakCfgPref(ucid), buildCloakCfg(seed));
    refreshContainer();
  });

  // Clear — strips both seed AND cloak_cfg so the container falls back
  // to host's real values (no spoofing). Useful for debugging or for
  // a "trusted" container that needs to look like real Firefox.
  clearBtn.addEventListener("click", () => {
    const ucid = parseInt(selectEl.value, 10) || 0;
    Services.prefs.clearUserPref(masterSeedPref(ucid));
    Services.prefs.clearUserPref(cloakCfgPref(ucid));
    Services.prefs.clearUserPref(tzPref(ucid));
    refreshContainer();
  });

  // ── Opt-in flag toggles ────────────────────────────────────────
  // Each <input data-pref="cloakfox.opt.foo"> auto-binds to its pref.
  // Changes write through immediately. Default reads from
  // getBoolPref's fallback, which honors the cloakfox.cfg defaultPref.
  for (const el of document.querySelectorAll("input[data-pref]")) {
    const pref = el.dataset.pref;
    el.checked = Services.prefs.getBoolPref(pref, false);
    el.addEventListener("change", () => {
      Services.prefs.setBoolPref(pref, el.checked);
    });
  }
});
