/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox settings page.
 *
 * Runs with chrome principal (IS_SECURE_CHROME_UI set in AboutRedirector)
 * so Services.prefs.setStringPref writes through the parent process —
 * the working path the cloakfox-shield extension couldn't use.
 *
 * Proof of concept for the cpp-first architecture: one toggle, one
 * per-container seed. Real settings UI is future work.
 */

/* global Services, Components, ChromeUtils */

const PREF_ENABLED = "cloakfox.enabled";

// Helpers ---------------------------------------------------------

function getCurrentUserContextId() {
  // The settings page itself is opened in userContextId 0 (default
  // container). For real per-container config we need this from the
  // tab the user came from, not the settings page. POC just shows the
  // mechanism; wire up tab origin later.
  return 0;
}

function seedPrefName(ucid) {
  return `cloakfox.container.${ucid}.math_seed`;
}

function randomSeedB64() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes));
}

// UI wiring -------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  const enabledEl = document.getElementById("cfx-enabled");
  const ucidEl    = document.getElementById("cfx-ucid");
  const seedEl    = document.getElementById("cfx-seed");
  const regenBtn  = document.getElementById("cfx-regenerate");

  // Initial read.
  const enabled = Services.prefs.getBoolPref(PREF_ENABLED, false);
  enabledEl.checked = enabled;

  const ucid = getCurrentUserContextId();
  ucidEl.textContent = String(ucid);
  seedEl.textContent = Services.prefs.getStringPref(seedPrefName(ucid), "(not set)");

  // Toggle handler: write pref. The pref observer in C++ (see
  // cpp-first-pref-reader.patch) picks this up on the next window
  // construction and primes RoverfoxStorageManager accordingly.
  enabledEl.addEventListener("change", () => {
    Services.prefs.setBoolPref(PREF_ENABLED, enabledEl.checked);
  });

  // Seed regen button: write a fresh 32-byte seed for the current
  // container.
  regenBtn.addEventListener("click", () => {
    const seed = randomSeedB64();
    Services.prefs.setStringPref(seedPrefName(ucid), seed);
    seedEl.textContent = seed;
  });
});
