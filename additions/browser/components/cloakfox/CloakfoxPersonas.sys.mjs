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

// Canonical navigator.platform / navigator.oscpu per OS. These are the
// frozen values modern Firefox reports, and they're low-entropy (~3
// possibilities), so we derive them from the UA's OS rather than trusting
// BrowserForge's independently-sampled fields — which can otherwise pair
// e.g. platform "Linux armv81" (ARM) with an x86_64 UA/oscpu, an obvious
// self-contradiction any detector flags.
const NAV_IDENTITY = {
  windows: { platform: "Win32",        oscpu: "Windows NT 10.0; Win64; x64" },
  macos:   { platform: "MacIntel",     oscpu: "Intel Mac OS X 10.15" },
  linux:   { platform: "Linux x86_64", oscpu: "Linux x86_64" },
};

// Canonical per-OS system-font sets. The C++ font-hijacker treats the
// cloak_cfg "fonts" key as an ALLOWLIST — only listed system fonts are
// exposed to enumeration and rendering. Each OS has a `base` (always
// present on a stock install — includes the web-safe families so generic
// CSS fallbacks resolve, and the OS emoji font) plus an `optional` pool
// (fonts that vary machine-to-machine) that we seed-sample per container
// for entropy. We do NOT reuse BrowserForge's sampled `fonts` field: its
// values are cross-OS-contaminated (a Mac UA can sample a Windows font
// set), which is exactly the incoherence this replaces.
const CANONICAL_FONTS = {
  windows: {
    base: [
      "Arial", "Arial Black", "Bahnschrift", "Calibri", "Cambria",
      "Cambria Math", "Comic Sans MS", "Consolas", "Constantia", "Corbel",
      "Courier New", "Ebrima", "Franklin Gothic Medium", "Gadugi", "Georgia",
      "Impact", "Lucida Console", "Lucida Sans Unicode", "Malgun Gothic",
      "Marlett", "Microsoft Sans Serif", "MS Gothic", "MV Boli",
      "Palatino Linotype", "Segoe UI", "Segoe UI Emoji", "Segoe UI Symbol",
      "SimSun", "Sylfaen", "Tahoma", "Times New Roman", "Trebuchet MS",
      "Verdana", "Webdings", "Wingdings",
    ],
    optional: [
      "Candara", "Gabriola", "Ink Free", "Javanese Text", "Leelawadee UI",
      "Microsoft Himalaya", "Microsoft JhengHei", "Microsoft YaHei",
      "Mongolian Baiti", "Myanmar Text", "Nirmala UI", "Segoe Print",
      "Segoe Script", "Sitka", "Yu Gothic", "MingLiU-ExtB",
    ],
  },
  macos: {
    base: [
      "American Typewriter", "Andale Mono", "Apple Color Emoji", "Arial",
      "Arial Black", "Arial Narrow", "Arial Unicode MS", "Avenir",
      "Avenir Next", "Baskerville", "Big Caslon", "Bodoni 72", "Bradley Hand",
      "Brush Script MT", "Chalkboard", "Chalkduster", "Cochin", "Comic Sans MS",
      "Copperplate", "Courier", "Courier New", "Didot", "Futura", "Geneva",
      "Georgia", "Gill Sans", "Helvetica", "Helvetica Neue", "Hoefler Text",
      "Impact", "Lucida Grande", "Menlo", "Microsoft Sans Serif", "Monaco",
      "Optima", "Palatino", "Papyrus", "Times", "Times New Roman",
      "Trebuchet MS", "Verdana", "Zapfino",
    ],
    optional: [
      "Apple Chancery", "Apple SD Gothic Neo", "Avenir Next Condensed",
      "Chalkboard SE", "DIN Alternate", "DIN Condensed", "Herculanum",
      "Luminari", "Marker Felt", "Noteworthy", "Phosphate", "Rockwell",
      "Savoye LET", "SignPainter", "Skia", "Snell Roundhand", "Trattatello",
    ],
  },
  linux: {
    base: [
      "Cantarell", "DejaVu Sans", "DejaVu Sans Mono", "DejaVu Serif",
      "FreeMono", "FreeSans", "FreeSerif", "Liberation Mono",
      "Liberation Sans", "Liberation Serif", "Noto Color Emoji", "Noto Mono",
      "Noto Sans", "Noto Serif", "Ubuntu", "Ubuntu Condensed", "Ubuntu Mono",
    ],
    optional: [
      "Bitstream Vera Sans", "Bitstream Vera Sans Mono", "Bitstream Vera Serif",
      "Century Schoolbook L", "Droid Sans", "Droid Sans Mono", "Droid Serif",
      "Nimbus Mono PS", "Nimbus Roman", "Nimbus Sans", "Noto Sans CJK JP",
      "Noto Sans Mono", "Standard Symbols PS", "URW Bookman", "URW Gothic",
    ],
  },
};

// Per-OS CSS generic-font mapping. Each value must be in that OS's
// CANONICAL_FONTS (so it survives the persona whitelist) AND in the bundled
// font pack (bundle/fonts/) so it renders on a mismatched host. Applied to
// font.name-list.<generic>.x-western by CloakfoxSeedSync.
const GENERIC_FONTS = {
  windows: { serif: "Times New Roman", sans: "Arial", mono: "Consolas" },
  macos: { serif: "Times", sans: "Helvetica", mono: "Menlo" },
  // Linux uses DejaVu (in CANONICAL_FONTS.linux); resolves once the linux
  // bundle pack ships those faces.
  linux: { serif: "DejaVu Serif", sans: "DejaVu Sans", mono: "DejaVu Sans Mono" },
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

// Derive the HTTP/2 + HTTP/3 fingerprint profile that keeps the wire
// transport coherent with the persona's browser family. h3 int mapping
// matches settings/cloakfox.cfg and the test harness: firefox=0, chrome=1,
// safari=2. Order matters — Chrome UAs also contain "Safari/", and Firefox
// UAs contain "Gecko", so test firefox → chrome → safari and default to
// firefox (the coherent choice for this fork's Firefox-based engine).
export function deriveHttpProfile(ua) {
  const s = (ua || "").toLowerCase();
  if (s.includes("firefox/") || s.includes("gecko/")) {
    return { h2: "firefox", h3: 0 };
  }
  if (s.includes("chrome/") || s.includes("chromium/") ||
      s.includes("edg/") || s.includes("opr/")) {
    return { h2: "chrome", h3: 1 };
  }
  if (s.includes("safari/") && s.includes("version/")) {
    return { h2: "safari", h3: 2 };
  }
  return { h2: "firefox", h3: 0 };
}

// Persist the per-container H2/H3 fingerprint profile derived from the
// persona UA, so the network stack (Http2Session / neqo) can key the wire
// fingerprint by userContextId. Call wherever a container's cloak_cfg is
// (re)written — the derivation and the pref names live only here.
export function writeHttpProfilePrefs(ucid, ua) {
  const { h2, h3 } = deriveHttpProfile(ua);
  Services.prefs.setCharPref(`cloakfox.container.${ucid}.h2_profile`, h2);
  Services.prefs.setIntPref(`cloakfox.container.${ucid}.h3_profile`, h3);
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
  // Derive platform/oscpu/appVersion coherently from the UA's OS instead
  // of trusting BrowserForge's independently-sampled fields (which can
  // mismatch — e.g. an ARM platform under an x86_64 UA). Firefox's
  // navigator.appVersion is exactly the UA with the leading "Mozilla/"
  // removed, so derive it from the (normalized) UA.
  const navId = NAV_IDENTITY[os] || NAV_IDENTITY.linux;
  keys["navigator.platform"]   = navId.platform;
  keys["navigator.oscpu"]      = navId.oscpu;
  keys["navigator.appVersion"] = ua.replace(/^Mozilla\//, "");
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

  // Fonts — coherent per-OS system-font allowlist. The C++ font-hijacker
  // exposes ONLY the fonts in cloak_cfg "fonts"; without this key the real
  // host fonts leak (uncoordinated with the persona OS, identical across
  // containers). Pin the OS base set + a seed-varied subset of the optional
  // pool so same-OS containers still differ. Sorted so ordering isn't a
  // signal.
  const fontSet = CANONICAL_FONTS[os] || CANONICAL_FONTS.linux;
  const fonts = fontSet.base.slice();
  for (const f of fontSet.optional) {
    if (prng() < 0.6) fonts.push(f);
  }
  keys["fonts"] = fonts.sort();

  // CSS generic-font mapping per OS. serif/sans-serif/monospace must resolve to
  // fonts that are BOTH in the persona's whitelist (above) AND present in the
  // bundled pack, else the generic falls back to sans-serif when the real
  // host's default generic fonts are whitelisted out (the collapse tell).
  // CloakfoxSeedSync applies these to font.name-list.<generic>.x-western.
  const gen = GENERIC_FONTS[os] || GENERIC_FONTS.linux;
  keys["font:generic:serif"] = gen.serif;
  keys["font:generic:sans-serif"] = gen.sans;
  keys["font:generic:monospace"] = gen.mono;

  // CSS media features that the STYLESHEET path resolves in C++
  // (Document::PreferredColorScheme, Gecko_MediaFeatures_ColorGamut /
  // _PrefersContrast). These must be emitted, otherwise CSS `@media` sees the
  // real host while CloakfoxMediaQueryChild pins the JS matchMedia side — a
  // contradiction no real browser produces (verified: host dark-mode rule
  // applied while matchMedia reported light). CloakfoxMediaQueryChild reads
  // these same keys so both paths share one source of truth.
  //   colorScheme: 0 = light, 1 = dark
  //   colorGamut:  0 = srgb, 1 = p3, 2 = rec2020
  //   contrast:    0 = no-preference, 1 = less, 2 = more, 3 = custom
  keys["document:prefersColorScheme"] = 0;
  keys["mediaFeature:colorGamut"] = os === "macos" ? 1 : 0;
  keys["mediaFeature:prefersContrast"] = 0;

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

  // Always-on persona-level spoofs. The predefined-pool generator
  // emitted these on every persona; preserving that behavior keeps
  // the C++ MaskConfig patches activated for every container by
  // default. The about:cloakfox UI surfaces them as "spoofed (on)" /
  // editable so power users can flip them off via per-field override.
  keys["codecs:spoof"]              = true;
  keys["mediaCapabilities:spoof"]   = true;
  keys["mediaFeature:invertedColors"]             = false;
  keys["mediaFeature:prefersReducedMotion"]       = false;
  keys["mediaFeature:prefersReducedTransparency"] = false;
  // matchMedia resolution = 96 dpi × dpr (rounded). Real Firefox emits
  // ~96 on standard displays, ~192 on 2x.
  const dpr = keys["window.devicePixelRatio"] || 1;
  keys["mediaFeature:resolution"]   = Math.round(96 * dpr);
  keys["voices:blockIfNotDefined"]              = true;
  keys["voices:fakeCompletion"]                 = true;
  keys["voices:fakeCompletion:charsPerSecond"]  = 12;
  keys["permissions:spoof"]            = true;
  keys["indexedDB:databases:hidden"]   = true;
  keys["document:lastModified:hidden"] = true;
  keys["navigator:vibrate:disabled"]   = true;
  keys["navigator:webgpu:disabled"]    = true;

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
