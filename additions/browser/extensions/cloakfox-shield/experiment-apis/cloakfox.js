/* Cloakfox WebExtensions Experiment API. Runs in the parent process
 * with chrome authority and exposes a small bridge to the popup.
 *
 * Errors thrown inside getAPI methods come back to the popup as a
 * generic "An unexpected error occurred". Every method wraps its
 * body in try/catch and re-throws an Error with the real message
 * so debugging from the popup side is possible.
 */

"use strict";

// btoa/atob aren't globals in experiment-api parent sandboxes.
// Inline minimal implementations.
const B64_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
function bytesToB64(bytes) {
  let out = "";
  for (let i = 0; i < bytes.length; i += 3) {
    const a = bytes[i], b = bytes[i+1] ?? 0, c = bytes[i+2] ?? 0;
    const t = (a << 16) | (b << 8) | c;
    out += B64_CHARS[(t >> 18) & 63];
    out += B64_CHARS[(t >> 12) & 63];
    out += i+1 < bytes.length ? B64_CHARS[(t >> 6) & 63] : "=";
    out += i+2 < bytes.length ? B64_CHARS[t & 63] : "=";
  }
  return out;
}
function b64ToBytes(b64) {
  const clean = b64.replace(/=+$/, "");
  const out = new Uint8Array(Math.floor(clean.length * 3 / 4));
  let bits = 0, value = 0, idx = 0;
  for (const ch of clean) {
    const v = B64_CHARS.indexOf(ch);
    if (v < 0) continue;
    value = (value << 6) | v;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      out[idx++] = (value >> bits) & 0xff;
    }
  }
  return out.subarray(0, idx);
}

const PREF_ENABLED = "cloakfox.enabled";

const masterSeedPref = (ucid) => `cloakfox.container.${ucid}.math_seed`;
const cloakCfgPref   = (ucid) => `cloakfox.s.cloak_cfg_${ucid}`;

function randomSeedB64() {
  const bytes = new Uint8Array(32);
  try {
    if (typeof crypto !== "undefined" && crypto.getRandomValues) {
      crypto.getRandomValues(bytes);
    } else {
      const rng = Cc["@mozilla.org/security/random-generator;1"]
        .createInstance(Ci.nsIRandomGenerator);
      const out = rng.generateRandomBytes(32);
      for (let i = 0; i < 32; i++) bytes[i] = out[i];
    }
  } catch (_e) {
    // Last-resort: weak Math.random — chrome scope should always have
    // one of the above, but don't crash if neither materializes.
    for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
  }
  return bytesToB64(bytes);
}

function u32(seedB64, i) {
  const bytes = b64ToBytes(seedB64);
  return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getUint32(i * 4);
}

function shortSeedTag(seedB64) {
  if (!seedB64) return "";
  try {
    const bytes = b64ToBytes(seedB64);
    return "#" + [0,1,2].map(i => bytes[i].toString(16).padStart(2,"0")).join("");
  } catch (_e) { return ""; }
}

// Build cloak_cfg by lazily loading CloakfoxPersonas at call time.
// Importing at top level can fail in the experiment-api parent
// sandbox on some build configs; lazy import keeps the addon loadable
// even if the persona module is broken.
function buildCloakCfg(seedB64, ucid) {
  const { fillPersonaKeys } = ChromeUtils.importESModule(
    "resource:///modules/CloakfoxPersonas.sys.mjs"
  );
  const base = {
    "canvas:seed": u32(seedB64, 0),
    "audio:seed":  u32(seedB64, 1),
    "font:seed":   u32(seedB64, 2),
    "font:spacing_seed": u32(seedB64, 3),
    "math:trig_seed":    u32(seedB64, 4),
    ...fillPersonaKeys(seedB64, ucid),
  };
  const branch = Services.prefs.getBranch(`cloakfox.container.${ucid}.override.`);
  for (const key of branch.getChildList("")) {
    const fullName = `cloakfox.container.${ucid}.override.${key}`;
    try {
      const t = Services.prefs.getPrefType(fullName);
      if (t === Services.prefs.PREF_INT)       base[key] = Services.prefs.getIntPref(fullName);
      else if (t === Services.prefs.PREF_BOOL) base[key] = Services.prefs.getBoolPref(fullName);
      else                                     base[key] = Services.prefs.getStringPref(fullName);
    } catch (_e) { /* skip malformed */ }
  }
  return JSON.stringify(base);
}

// Wrap a method to surface real errors to the popup. WebExtensions
// schema validation collapses thrown Errors to a generic message
// unless we re-package them as ExtensionError.
function wrap(fn) {
  return async function (...args) {
    try {
      return await fn.apply(this, args);
    } catch (e) {
      const msg = (e && (e.message || String(e))) || "unknown";
      const stack = e && e.stack ? "\n" + e.stack : "";
      Cu.reportError("cloakfox bridge error: " + msg + stack);
      // ExtensionError ensures the message survives back to the popup.
      throw new ExtensionUtils.ExtensionError(msg);
    }
  };
}

// ExtensionUtils is exposed to experiment-api scripts.
const { ExtensionUtils } = ChromeUtils.importESModule(
  "resource://gre/modules/ExtensionUtils.sys.mjs"
);

this.cloakfox = class extends ExtensionAPI {
  getAPI(_context) {
    return {
      cloakfox: {
        getEnabled: wrap(async () => {
          return { enabled: Services.prefs.getBoolPref(PREF_ENABLED, false) };
        }),

        setEnabled: wrap(async ({ enabled }) => {
          Services.prefs.setBoolPref(PREF_ENABLED, !!enabled);
          return { enabled: !!enabled };
        }),

        getCloakCfg: wrap(async ({ ucid }) => {
          const u = parseInt(ucid, 10) || 0;
          const seedB64 = Services.prefs.getStringPref(masterSeedPref(u), "");
          const raw     = Services.prefs.getStringPref(cloakCfgPref(u), "");
          let cfg = null;
          if (raw) { try { cfg = JSON.parse(raw); } catch (_e) {} }
          return { cfg, tag: shortSeedTag(seedB64) };
        }),

        regeneratePersona: wrap(async ({ ucid }) => {
          const u = parseInt(ucid, 10) || 0;
          const seed = randomSeedB64();
          Services.prefs.setStringPref(masterSeedPref(u), seed);
          Services.prefs.setStringPref(cloakCfgPref(u), buildCloakCfg(seed, u));
          return { ucid: u, tag: shortSeedTag(seed) };
        }),

        // Open about:cloakfox in the active window. Uses
        // openTrustedLinkIn which is the modern API for chrome-priv
        // tab-opening. Works even if the AboutRedirector flags
        // haven't been compiled in yet.
        openSettings: wrap(async ({ ucid }) => {
          const u = parseInt(ucid, 10) || 0;
          const url = `about:cloakfox?ucid=${u}`;
          const win = Services.wm.getMostRecentWindow("navigator:browser");
          if (!win) throw new Error("No browser window available");
          // openTrustedLinkIn is what address-bar typing uses internally.
          // Falls back to gBrowser.addTab if not available.
          if (typeof win.openTrustedLinkIn === "function") {
            win.openTrustedLinkIn(url, "tab");
          } else {
            const tab = win.gBrowser.addTab(url, {
              triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal(),
            });
            win.gBrowser.selectedTab = tab;
          }
          return { ok: true };
        }),
      },
    };
  }
};
