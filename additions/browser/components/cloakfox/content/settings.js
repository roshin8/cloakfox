/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox settings page — container-aware version (Phase 3).
 *
 * Runs chrome-privileged (IS_SECURE_CHROME_UI set in AboutRedirector),
 * so Services.prefs + Services.contextualIdentityService are available.
 *
 * Features:
 *   - Master Enable toggle (cloakfox.enabled pref)
 *   - Container dropdown built from ContextualIdentityService
 *   - Per-container seed display + regen + clear buttons
 *   - Regen writes:
 *       cloakfox.container.<ucid>.math_seed    (32-byte base64 — used
 *         by Math, Keyboard, Timing, TabHistory actors via
 *         makePRNG(b64ToBytes(seedB64)))
 *       cloakfox.s.cloak_cfg_<ucid>            (JSON blob consumed
 *         by C++ canvas/audio/font managers via MaskConfig)
 */

/* global Services */

const PREF_ENABLED = "cloakfox.enabled";

// ── pref name helpers ───────────────────────────────────────────────

const masterSeedPref = (ucid) => `cloakfox.container.${ucid}.math_seed`;
const cloakCfgPref   = (ucid) => `cloakfox.s.cloak_cfg_${ucid}`;

// ── seed / config helpers ───────────────────────────────────────────

function randomSeedB64() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes));
}

// Derive a uint32 from the seed at offset i*4 (deterministic; gives
// per-signal values that are stable per container without needing
// extra prefs).
function u32(seedB64, i) {
  const bin = atob(seedB64);
  const bytes = Uint8Array.from(bin, c => c.charCodeAt(0));
  return new DataView(bytes.buffer).getUint32(i * 4);
}

function buildCloakCfg(seedB64) {
  return JSON.stringify({
    "canvas:seed": u32(seedB64, 0),
    "audio:seed": u32(seedB64, 1),
    "font:seed": u32(seedB64, 2),
    "font:spacing_seed": u32(seedB64, 3),
  });
}

// ── container enumeration ──────────────────────────────────────────

function getContainers() {
  // Returns [{ucid, name}] for default + every user-defined container.
  const list = [{ ucid: 0, name: "Default (no container)" }];
  try {
    const identities =
      Services.contextualIdentityService.getPublicIdentities();
    for (const id of identities) {
      list.push({
        ucid: id.userContextId,
        name: id.name || `Container ${id.userContextId}`,
      });
    }
  } catch (e) {
    // If ContextualIdentityService isn't available, fall through to
    // just the default container.
  }
  return list;
}

// ── wire up UI ─────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  const enabledEl  = document.getElementById("cfx-enabled");
  const selectEl   = document.getElementById("cfx-container-select");
  const masterEl   = document.getElementById("cfx-seed-master");
  const cloakCfgEl = document.getElementById("cfx-seed-cloakcfg");
  const regenBtn   = document.getElementById("cfx-regenerate");
  const clearBtn   = document.getElementById("cfx-clear");

  // Populate master enable.
  enabledEl.checked = Services.prefs.getBoolPref(PREF_ENABLED, false);
  enabledEl.addEventListener("change", () => {
    Services.prefs.setBoolPref(PREF_ENABLED, enabledEl.checked);
  });

  // Populate container dropdown.
  const containers = getContainers();
  selectEl.innerHTML = "";
  for (const c of containers) {
    const opt = document.createElement("option");
    opt.value = String(c.ucid);
    opt.textContent = c.name;
    selectEl.appendChild(opt);
  }

  function refreshSeeds() {
    const ucid = parseInt(selectEl.value, 10) || 0;
    masterEl.textContent = Services.prefs.getStringPref(
      masterSeedPref(ucid), "(not set)"
    );
    cloakCfgEl.textContent = Services.prefs.getStringPref(
      cloakCfgPref(ucid), "(not set)"
    );
  }
  selectEl.addEventListener("change", refreshSeeds);
  refreshSeeds();

  regenBtn.addEventListener("click", () => {
    const ucid = parseInt(selectEl.value, 10) || 0;
    const seed = randomSeedB64();
    Services.prefs.setStringPref(masterSeedPref(ucid), seed);
    Services.prefs.setStringPref(cloakCfgPref(ucid), buildCloakCfg(seed));
    refreshSeeds();
  });

  clearBtn.addEventListener("click", () => {
    const ucid = parseInt(selectEl.value, 10) || 0;
    Services.prefs.clearUserPref(masterSeedPref(ucid));
    Services.prefs.clearUserPref(cloakCfgPref(ucid));
    refreshSeeds();
  });
});
