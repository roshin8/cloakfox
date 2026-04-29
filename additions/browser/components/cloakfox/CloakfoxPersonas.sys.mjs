/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: per-container fingerprint persona — BrowserForge runtime.
 *
 * Each container's master seed deterministically samples a fingerprint
 * from Apify BrowserForge's filtered desktop-Firefox Bayesian network
 * (CloakfoxBayesianNetwork). The sample is a coherent bundle: webGl
 * renderer matches platform, screen matches devicePixelRatio, etc. —
 * coherence comes for free from the joint distribution.
 *
 * Replaces the predefined 30-personas-per-OS pool. Cross-OS by default
 * (Mac host can pretend to be Windows; the BF distribution covers all
 * three desktop OSes with proper coherence).
 *
 * Non-BF fields (audio context, geolocation, locale, opt-in flags) are
 * filled with sensible defaults below so the cloak_cfg shape stays
 * unchanged from the C++ MaskConfig patches' perspective.
 */

import { sampleFingerprint } from "resource:///modules/CloakfoxBayesianNetwork.sys.mjs";

// Pin the UA's Firefox version to the build's milestone — BF's pool has
// a mix of Firefox versions (135-147), but the page-visible UA must
// match the actual binary or that's an instant flag.
const FIREFOX_VERSION = "146.0";

// US cities for geolocation jitter. BF doesn't emit lat/lng so we draw
// from this pool and apply ±0.04° (~5km) noise. Synced with the older
// scripts/generate-personas.py US_CITIES list.
const US_CITIES = [
  ["New York",      40.7128,  -74.0060],
  ["Los Angeles",   34.0522, -118.2437],
  ["Chicago",       41.8781,  -87.6298],
  ["Houston",       29.7604,  -95.3698],
  ["Phoenix",       33.4484, -112.0740],
  ["Philadelphia",  39.9526,  -75.1652],
  ["San Antonio",   29.4241,  -98.4936],
  ["San Diego",     32.7157, -117.1611],
  ["Dallas",        32.7767,  -96.7970],
  ["San Jose",      37.3382, -121.8863],
  ["Austin",        30.2672,  -97.7431],
  ["Jacksonville",  30.3322,  -81.6557],
  ["San Francisco", 37.7749, -122.4194],
  ["Seattle",       47.6062, -122.3321],
  ["Denver",        39.7392, -104.9903],
  ["Boston",        42.3601,  -71.0589],
  ["Miami",         25.7617,  -80.1918],
  ["Atlanta",       33.7490,  -84.3880],
  ["Portland",      45.5152, -122.6784],
  ["Minneapolis",   44.9778,  -93.2650],
];

// Per-OS chrome decoration heights for deriving inner/outer/avail
// dimensions when BF doesn't emit them.
const CHROME_DECOR = {
  macos:   { menuBar: 25, taskbar: 0,  firefoxChrome: 86 },
  windows: { menuBar: 0,  taskbar: 40, firefoxChrome: 90 },
  linux:   { menuBar: 0,  taskbar: 32, firefoxChrome: 80 },
};

function detectOSFromUA(ua) {
  if (!ua) return "linux";
  if (ua.includes("Macintosh") || ua.includes("Mac OS")) return "macos";
  if (ua.includes("Windows")) return "windows";
  return "linux";
}

function normalizeUA(ua) {
  if (!ua) return ua;
  return ua
    .replace(/rv:\d+\.\d+/, `rv:${FIREFOX_VERSION}`)
    .replace(/Firefox\/\d+\.\d+/, `Firefox/${FIREFOX_VERSION}`);
}

// 32-byte b64 master seed → mulberry32 PRNG. Mixes all 4 leading bytes
// + last 4 bytes so even seeds with low entropy in the first word
// produce diverse samples.
function makeSeededPRNG(seedB64) {
  const bin = atob(seedB64);
  let s = 0;
  for (let i = 0; i < 4; i++) s = (s * 256 + bin.charCodeAt(i)) >>> 0;
  for (let i = 28; i < 32 && i < bin.length; i++) s = ((s * 16777619) ^ bin.charCodeAt(i)) >>> 0;
  return function next() {
    let t = (s = (s + 0x6d2b79f5) | 0);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Map a BrowserForge fingerprint sample to our cloak_cfg key shape.
function bfToCloakKeys(fp, prng) {
  const keys = {};
  const ua = normalizeUA(fp.userAgent || "");
  const os = detectOSFromUA(ua);

  // Navigator
  keys["navigator.userAgent"] = ua;
  keys["headers.User-Agent"]  = ua;
  if (fp.platform)   keys["navigator.platform"]   = fp.platform;
  if (fp.oscpu)      keys["navigator.oscpu"]      = fp.oscpu;
  if (fp.appVersion) keys["navigator.appVersion"] = fp.appVersion;
  if (fp.hardwareConcurrency != null) {
    keys["navigator.hardwareConcurrency"] = parseInt(fp.hardwareConcurrency, 10);
  }
  if (fp.maxTouchPoints != null) {
    const mtp = parseInt(fp.maxTouchPoints, 10);
    keys["navigator:maxTouchPoints"] = Number.isFinite(mtp) ? mtp : 0;
  }

  // Screen — BF emits an object with width/height/dpr/etc. Some inner*
  // fields are 0 in BF training data; derive coherent values from
  // outer + chrome decoration when they're missing.
  if (fp.screen && typeof fp.screen === "object") {
    const sc = fp.screen;
    const decor = CHROME_DECOR[os] || CHROME_DECOR.linux;
    const w  = sc.width  || 1920;
    const h  = sc.height || 1080;
    const dpr = sc.devicePixelRatio || 1.0;
    keys["screen.width"]      = w;
    keys["screen.height"]     = h;
    keys["screen.availWidth"] = sc.availWidth  || w;
    keys["screen.availHeight"] = (sc.availHeight && sc.availHeight > 0)
      ? sc.availHeight : (h - decor.menuBar - decor.taskbar);
    keys["screen.availLeft"]   = sc.availLeft  ?? 0;
    keys["screen.availTop"]    = sc.availTop   ?? decor.menuBar;
    keys["screen.pageXOffset"] = sc.pageXOffset ?? 0;
    keys["screen.pageYOffset"] = sc.pageYOffset ?? 0;
    keys["window.devicePixelRatio"] = dpr;
    keys["window.outerWidth"]  = sc.outerWidth  || w;
    keys["window.outerHeight"] = sc.outerHeight || (h - decor.taskbar);
    const innerH = (sc.innerHeight && sc.innerHeight > 0)
      ? sc.innerHeight
      : Math.max(200, h - decor.menuBar - decor.taskbar - decor.firefoxChrome);
    keys["window.innerWidth"]  = sc.innerWidth  || w;
    keys["window.innerHeight"] = innerH;
    keys["window.screenX"]     = sc.screenX ?? 0;
    keys["window.screenY"]     = sc.screenY ?? 0;
    keys["window.scrollMinX"]  = 0;
    keys["window.scrollMinY"]  = 0;
    keys["screen:orientation:type"] = (w >= h) ? "landscape-primary" : "portrait-primary";
  }

  // WebGL
  if (fp.videoCard && typeof fp.videoCard === "object") {
    if (fp.videoCard.vendor)   keys["webGl:vendor"]   = fp.videoCard.vendor;
    if (fp.videoCard.renderer) keys["webGl:renderer"] = fp.videoCard.renderer;
  }

  // Audio context — not in BF; pick plausible values per-container.
  keys["AudioContext:sampleRate"] = [44100, 48000][Math.floor(prng() * 2)];
  keys["AudioContext:maxChannelCount"] = [2, 2, 2, 6][Math.floor(prng() * 4)];
  keys["AudioContext:outputLatency"] =
    [0.005, 0.0085, 0.01, 0.02, 0.04][Math.floor(prng() * 5)];

  // Locale — pin to en-US for now (cross-locale support is future work).
  keys["headers.Accept-Language"] = "en-US,en;q=0.5";
  keys["headers.Accept-Encoding"] = "gzip, deflate, br, zstd";
  keys["navigator.language"]      = "en-US";
  keys["locale:language"]         = "en";
  keys["locale:region"]           = "US";
  keys["locale:script"]           = "Latn";

  // Geolocation — pick a US city + jitter.
  const city = US_CITIES[Math.floor(prng() * US_CITIES.length)];
  keys["geolocation:latitude"]  = city[1] + (prng() - 0.5) * 0.08;
  keys["geolocation:longitude"] = city[2] + (prng() - 0.5) * 0.08;
  keys["geolocation:accuracy"]  = 30 + Math.floor(prng() * 50);

  return keys;
}

// User opt-in flags. Each persona-driven "disable" / "spoof" key that
// could plausibly break legitimate usage is gated on a Services.prefs
// boolean, default false. Set via about:cloakfox UI (or about:config
// for power users); no MaskConfig key is emitted unless the matching
// pref reads true. Lets users trade compatibility for stealth on
// surfaces that have legitimate cross-origin uses.
function userOpt(name, def = false) {
  try {
    return Services.prefs.getBoolPref(`cloakfox.opt.${name}`, def);
  } catch (_e) { return def; }
}

/**
 * Sample a fingerprint deterministically from the seed and return the
 * cloak_cfg keys. Same seed → same persona across browser restarts.
 *
 * @param {string} seedB64  Master seed (32 bytes, base64).
 * @param {number|null} ucid  Container userContextId; reserved for
 *                            future per-container BF input constraints
 *                            (unused today since each container has its
 *                            own seed already).
 * @returns {Object}  Flat dict keyed on cloak_cfg keys.
 */
export function fillPersonaKeys(seedB64, ucid = null) {
  const prng = makeSeededPRNG(seedB64);
  const fp = sampleFingerprint(prng);
  const keys = bfToCloakKeys(fp, prng);

  // ── User opt-in dangerous-disable flags (unchanged from prior impl) ──
  if (userOpt("window_name_disabled"))   keys["window:name:disabled"] = true;
  if (userOpt("websocket_disabled"))     keys["webSocket:disabled"] = true;
  if (userOpt("clipboard_disabled"))     keys["navigator:clipboard:disabled"] = true;
  if (userOpt("eme_disabled"))           keys["navigator:eme:disabled"] = true;
  if (userOpt("mediadevices_disabled"))  keys["mediaDevices:enabled"] = false;
  if (userOpt("notification_permission_disabled")) {
    keys["notification:permission:disabled"] = true;
  }
  if (userOpt("storage_persisted_disabled")) {
    keys["storage:persisted:disabled"] = true;
  }

  return keys;
}

/**
 * For about:cloakfox's "Persona override" dropdown: generate a
 * deterministic preview list of N personas using fixed seeds. The
 * persona_index pref pins which preview a container uses (overriding
 * its master seed).
 *
 * This replaces the predefined PERSONAS pool's listPersonas. From the
 * UI's perspective the API is identical — array of {index, label} —
 * but personas come from BF runtime sampling rather than a baked file.
 */
export function listPersonas(_hostOS) {
  const N = 30;
  const out = [];
  for (let i = 0; i < N; i++) {
    // Fixed-seed sampling: deterministic preview list. Index 0 always
    // looks the same, index 1 always looks the same, etc. Across browser
    // restarts the user sees a stable list.
    const prng = mulberry32(0xC10A * (i + 1));
    const fp = sampleFingerprint(prng);
    const platform = fp.platform || "?";
    const w = (fp.screen && fp.screen.width) || "?";
    const h = (fp.screen && fp.screen.height) || "?";
    const dpr = (fp.screen && fp.screen.devicePixelRatio) || "?";
    const hwc = fp.hardwareConcurrency ?? "?";
    const renderer = ((fp.videoCard && fp.videoCard.renderer) || "?").slice(0, 40);
    out.push({
      index: i,
      label: `${platform} · ${w}×${h}@${dpr}x · ${hwc}c · ${renderer}`,
    });
  }
  return out;
}

function mulberry32(seed) {
  return function() {
    let t = (seed = (seed + 0x6d2b79f5) | 0);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Returns one of the preview personas as a fingerprint sample. Used
 * when a container has cloakfox.container.<ucid>.persona_index set so
 * the same fixed-seed preview gets sampled.
 */
function previewPersona(index) {
  const prng = mulberry32(0xC10A * (index + 1));
  return sampleFingerprint(prng);
}

/**
 * Compatibility shim for callers that still expect the old
 * pickPersona API (returns a flat persona dict). Honors the
 * cloakfox.container.<ucid>.persona_index pref by sampling from a
 * fixed-seed preview index instead of the master seed.
 *
 * Most callers should use fillPersonaKeys directly.
 */
export function pickPersona(seedB64, _hostOS, ucid = null) {
  if (ucid !== null) {
    try {
      const idx = Services.prefs.getIntPref(
        `cloakfox.container.${ucid}.persona_index`, -1
      );
      if (idx >= 0 && idx < 30) {
        return bfToFlatPreview(previewPersona(idx));
      }
    } catch (_e) { /* fall through */ }
  }
  // Deterministic from master seed.
  const prng = makeSeededPRNG(seedB64);
  return bfToFlatPreview(sampleFingerprint(prng));
}

// For the legacy pickPersona API — flatten BF output to a few headline
// keys the callers (about:cloakfox personaSummary) expect.
function bfToFlatPreview(fp) {
  return {
    "navigator.platform": fp.platform || "?",
    "screen.width":       (fp.screen && fp.screen.width)  || 0,
    "screen.height":      (fp.screen && fp.screen.height) || 0,
    "window.devicePixelRatio": (fp.screen && fp.screen.devicePixelRatio) || 1,
    "navigator.hardwareConcurrency": fp.hardwareConcurrency ?? 0,
    "webGl:renderer":     (fp.videoCard && fp.videoCard.renderer) || "",
  };
}
