/* Cloakfox WebExtensions Experiment API. Runs in the parent process
 * with chrome authority and exposes a small bridge to the popup.
 *
 * Loaded by Firefox via the experiment_apis manifest entry. The
 * extension's popup can then call browser.cloakfox.{getEnabled,
 * setEnabled, getCloakCfg, regeneratePersona, ...} as if they were
 * native WebExtensions APIs.
 *
 * Why this exists: WebExtensions don't have Services.prefs access.
 * The popup needs to read the per-container cloak_cfg and write a
 * new master seed. Both require chrome authority. This Experiment
 * API is the standard Mozilla pattern for built-in addons that need
 * privileged access without spinning up a full add-on with custom
 * permissions.
 */

"use strict";

ChromeUtils.defineESModuleGetters(this, {
  CloakfoxPersonas: "resource:///modules/CloakfoxPersonas.sys.mjs",
});

const PREF_ENABLED = "cloakfox.enabled";

const masterSeedPref = (ucid) => `cloakfox.container.${ucid}.math_seed`;
const cloakCfgPref   = (ucid) => `cloakfox.s.cloak_cfg_${ucid}`;

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

// Mirror SeedSync.buildCloakCfg + apply per-container overrides.
function buildCloakCfg(seedB64, ucid) {
  const { fillPersonaKeys } = CloakfoxPersonas;
  const base = {
    "canvas:seed": u32(seedB64, 0),
    "audio:seed": u32(seedB64, 1),
    "font:seed": u32(seedB64, 2),
    "font:spacing_seed": u32(seedB64, 3),
    "math:trig_seed": u32(seedB64, 4),
    ...fillPersonaKeys(seedB64, ucid),
  };
  // Apply user-set field overrides on top.
  const branch = Services.prefs.getBranch(`cloakfox.container.${ucid}.override.`);
  for (const key of branch.getChildList("")) {
    try {
      const t = Services.prefs.getPrefType(`cloakfox.container.${ucid}.override.${key}`);
      let val;
      if (t === Services.prefs.PREF_INT)        val = Services.prefs.getIntPref(`cloakfox.container.${ucid}.override.${key}`);
      else if (t === Services.prefs.PREF_BOOL)  val = Services.prefs.getBoolPref(`cloakfox.container.${ucid}.override.${key}`);
      else                                      val = Services.prefs.getStringPref(`cloakfox.container.${ucid}.override.${key}`);
      base[key] = val;
    } catch (_e) { /* skip */ }
  }
  return JSON.stringify(base);
}

function shortSeedTag(seedB64) {
  if (!seedB64) return "";
  try {
    const bin = atob(seedB64);
    return "#" + [0,1,2].map(i => bin.charCodeAt(i).toString(16).padStart(2,"0")).join("");
  } catch (_e) { return ""; }
}

this.cloakfox = class extends ExtensionAPI {
  getAPI(_context) {
    return {
      cloakfox: {
        async getEnabled() {
          try {
            return { enabled: Services.prefs.getBoolPref(PREF_ENABLED, false) };
          } catch (_e) { return { enabled: false }; }
        },

        async setEnabled({ enabled }) {
          Services.prefs.setBoolPref(PREF_ENABLED, !!enabled);
          return { enabled: !!enabled };
        },

        async getCloakCfg({ ucid }) {
          const u = parseInt(ucid, 10) || 0;
          const seedB64 = Services.prefs.getStringPref(masterSeedPref(u), "");
          const raw = Services.prefs.getStringPref(cloakCfgPref(u), "");
          let cfg = null;
          if (raw) { try { cfg = JSON.parse(raw); } catch (_e) {} }
          return { cfg, tag: shortSeedTag(seedB64) };
        },

        async regeneratePersona({ ucid }) {
          const u = parseInt(ucid, 10) || 0;
          const seed = randomSeedB64();
          Services.prefs.setStringPref(masterSeedPref(u), seed);
          Services.prefs.setStringPref(cloakCfgPref(u), buildCloakCfg(seed, u));
          return { ucid: u, tag: shortSeedTag(seed) };
        },
      },
    };
  }
};
