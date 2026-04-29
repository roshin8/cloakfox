/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: per-container fingerprint persona selection.
 *
 * The persona pool itself lives in CloakfoxPersonaData.sys.mjs — a
 * generated module containing 30 personas per OS family sampled from
 * BrowserForge's real-world Bayesian-network distribution. Each persona
 * is a flat dict of MaskConfig keys (the same shape our C++ patches
 * read), so fillPersonaKeys is just "pick + spread + add user opt-in
 * overrides."
 *
 * Regenerate the pool when Firefox version changes or when the
 * antibot battery surfaces a real-world detection issue:
 *     pip install browserforge
 *     python3 scripts/generate-personas.py
 *
 * Host-OS lock: a Mac host gets only macOS personas, etc. Cross-OS
 * personas (Mac host pretending to be Windows) need a coherence
 * engine to ensure WebGL renderer family / font list / locale all
 * match the claimed UA — task #84.
 */

import { PERSONAS } from "resource:///modules/CloakfoxPersonaData.sys.mjs";

function detectHostOS() {
  // Services.appinfo.OS returns "Darwin", "WINNT", or "Linux".
  try {
    return (Services.appinfo.OS || "").toLowerCase();
  } catch (_e) { return "linux"; }
}

// Hash the seed's first 4 bytes into a uint32 for deterministic pick.
function seedU32(seedB64) {
  const bin = atob(seedB64);
  return ((bin.charCodeAt(0) << 24) |
          (bin.charCodeAt(1) << 16) |
          (bin.charCodeAt(2) << 8)  |
           bin.charCodeAt(3)) >>> 0;
}

export function pickPersona(seedB64, hostOS = detectHostOS(), ucid = null) {
  const pool = PERSONAS[hostOS] || PERSONAS.linux;
  // Per-container override: cloakfox.container.<ucid>.persona_index pins
  // a specific persona regardless of seed. Set via about:cloakfox UI for
  // users who want a particular config (e.g. "always make this container
  // a Win11-1366x768 user"). Out-of-range / unset → fall through to
  // seed-based pick.
  if (ucid !== null) {
    try {
      const override = Services.prefs.getIntPref(
        `cloakfox.container.${ucid}.persona_index`, -1
      );
      if (override >= 0 && override < pool.length) {
        return pool[override];
      }
    } catch (_e) { /* ignore */ }
  }
  return pool[seedU32(seedB64) % pool.length];
}

/* Public list-personas API for the about:cloakfox UI: returns the
 * host-OS pool with human-readable labels and indices the dropdown
 * binds to. Label format is the same one personaSummary renders for
 * the active persona, so users see consistent strings.
 */
export function listPersonas(hostOS = detectHostOS()) {
  const pool = PERSONAS[hostOS] || PERSONAS.linux;
  return pool.map((p, i) => ({
    index: i,
    label: `${p["navigator.platform"]} · ${p["screen.width"]}×${p["screen.height"]}@${p["window.devicePixelRatio"]}x · ${p["navigator.hardwareConcurrency"]}c · ${(p["webGl:renderer"] || "?").slice(0, 40)}`,
  }));
}

/* User opt-in flags. Each persona-driven "disable" / "spoof" key that
 * could plausibly break legitimate usage is gated on a Services.prefs
 * boolean, default false. Set via about:cloakfox UI (or about:config
 * for power users); no MaskConfig key is emitted unless the matching
 * pref reads true. Lets users trade compatibility for stealth on
 * surfaces that have legitimate cross-origin uses.
 */
function userOpt(name, def = false) {
  try {
    return Services.prefs.getBoolPref(`cloakfox.opt.${name}`, def);
  } catch (_e) { return def; }
}

export function fillPersonaKeys(seedB64, ucid = null) {
  // BrowserForge-generated persona is already a flat MaskConfig dict.
  // ucid lets pickPersona honor any per-container persona_index override.
  const persona = pickPersona(seedB64, detectHostOS(), ucid);
  const keys = { ...persona };

  // ── User opt-in dangerous-disable flags ─────────────────────────
  // window.name: breaks fpscanner / popup-orchestrated auth flows
  // (window.opener.name pattern). Off by default. Power user can
  // enable via cloakfox.opt.window_name_disabled = true.
  if (userOpt("window_name_disabled")) keys["window:name:disabled"] = true;
  // WebSocket: disabling breaks any site using realtime channels.
  if (userOpt("websocket_disabled")) keys["webSocket:disabled"] = true;
  // Clipboard read API: disabling breaks "paste" UX on some sites.
  if (userOpt("clipboard_disabled")) keys["navigator:clipboard:disabled"] = true;
  // EME: disabling breaks DRM-protected video (Netflix etc.).
  if (userOpt("eme_disabled")) keys["navigator:eme:disabled"] = true;
  // mediaDevices: disabling enumerateDevices breaks WebRTC/getUserMedia.
  if (userOpt("mediadevices_disabled")) keys["mediaDevices:enabled"] = false;
  // Notification permission: forces Notification.permission = "default",
  // so sites can't tell if user granted/denied. Off by default — most
  // users want this to follow real permission state.
  if (userOpt("notification_permission_disabled")) {
    keys["notification:permission:disabled"] = true;
  }
  // Storage persisted: forces navigator.storage.persisted() to false.
  // Off by default — apps that legit need persistent storage break.
  if (userOpt("storage_persisted_disabled")) {
    keys["storage:persisted:disabled"] = true;
  }

  return keys;
}
