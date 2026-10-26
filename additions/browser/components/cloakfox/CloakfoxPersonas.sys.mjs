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
 * Identities sample complete cross-OS tuples by default. Host-conditioned
 * sampling is an explicit option. Existing identities retain their saved mode.
 * Host rendering is not an authentic renderer for a foreign OS.
 *
 * Non-BF fields (audio context, geolocation, locale, opt-in flags) are
 * filled with sensible defaults below so the cloak_cfg shape stays
 * unchanged from the C++ MaskConfig patches' perspective.
 */

import { AppConstants } from "resource://gre/modules/AppConstants.sys.mjs";
import { writeNetworkProfile } from "resource:///modules/CloakfoxNetworkProfiles.sys.mjs";
import { sampleFingerprint, samplePersonaFingerprint } from "resource:///modules/CloakfoxBayesianNetwork.sys.mjs";
import { sampleHostFingerprint } from "resource:///modules/CloakfoxHostPersona.sys.mjs";

// Pin the UA's Firefox version to the build's milestone — BF's pool has
// a mix of Firefox versions (135-147), but the page-visible UA must
// match the actual binary or that's an instant flag.
const FIREFOX_VERSION = `${parseInt(AppConstants.MOZ_APP_VERSION, 10)}.0`;

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
      "Noto Sans Math",
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
      "Noto Sans Math",
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
      "Noto Sans Math",
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

// ── WebGL static tables ────────────────────────────────────────────────────
// The C++ hooks (MaskConfig::GLParam / MParamGL / MShaderData and
// ClientWebGLContext) read these, but nothing used to emit them — so every
// driver limit, the extension list, and the RENDERER string came from the REAL
// GPU while webGl:renderer claimed another card. Verified contradiction before
// this: UNMASKED_RENDERER_WEBGL said "Radeon HD 3200 Graphics" while
// getParameter(RENDERER) said "Apple M1".
//
// Values are keyed by GPU CLASS rather than exact model: the goal is that every
// machine running a given persona reports an identical, plausible WebGL
// identity (same crowd-blending logic as the bundled font pack), not that we
// reproduce one specific card bit-for-bit. Limits below are the common modern
// desktop values shared by the large majority of GPUs in each class.
//
// Parameter keys are the GLenum pname as a DECIMAL STRING (see
// MaskConfig::GLParam -> std::to_string(pname)).
const GL = {
  VENDOR: 7936, RENDERER: 7937,
  MAX_TEXTURE_SIZE: 3379, MAX_VIEWPORT_DIMS: 3386,
  MAX_CUBE_MAP_TEXTURE_SIZE: 34076, MAX_RENDERBUFFER_SIZE: 34024,
  MAX_VERTEX_ATTRIBS: 34921, MAX_VERTEX_UNIFORM_VECTORS: 36347,
  MAX_VARYING_VECTORS: 36348, MAX_FRAGMENT_UNIFORM_VECTORS: 36349,
  MAX_TEXTURE_IMAGE_UNITS: 34930, MAX_VERTEX_TEXTURE_IMAGE_UNITS: 35660,
  MAX_COMBINED_TEXTURE_IMAGE_UNITS: 35661,
  ALIASED_LINE_WIDTH_RANGE: 33902, ALIASED_POINT_SIZE_RANGE: 33901,
  MAX_SAMPLES: 36183,
};

// class -> limit overrides on top of GL_BASE
const GL_BASE = {
  [GL.MAX_TEXTURE_SIZE]: 16384,
  [GL.MAX_CUBE_MAP_TEXTURE_SIZE]: 16384,
  [GL.MAX_RENDERBUFFER_SIZE]: 16384,
  [GL.MAX_VIEWPORT_DIMS]: [32767, 32767],
  [GL.MAX_VERTEX_ATTRIBS]: 16,
  [GL.MAX_VERTEX_UNIFORM_VECTORS]: 1024,
  [GL.MAX_VARYING_VECTORS]: 30,
  [GL.MAX_FRAGMENT_UNIFORM_VECTORS]: 1024,
  [GL.MAX_TEXTURE_IMAGE_UNITS]: 16,
  [GL.MAX_VERTEX_TEXTURE_IMAGE_UNITS]: 16,
  [GL.MAX_COMBINED_TEXTURE_IMAGE_UNITS]: 32,
  [GL.ALIASED_LINE_WIDTH_RANGE]: [1, 1],
  [GL.ALIASED_POINT_SIZE_RANGE]: [1, 1024],
  [GL.MAX_SAMPLES]: 4,
};

const GL_CLASS = {
  nvidia: { [GL.MAX_VIEWPORT_DIMS]: [32768, 32768], [GL.MAX_SAMPLES]: 8 },
  amd:    { [GL.MAX_VIEWPORT_DIMS]: [16384, 16384], [GL.MAX_SAMPLES]: 8 },
  intel:  { [GL.MAX_VIEWPORT_DIMS]: [16384, 16384],
            [GL.MAX_COMBINED_TEXTURE_IMAGE_UNITS]: 32 },
  apple:  { [GL.MAX_VIEWPORT_DIMS]: [16384, 16384],
            [GL.MAX_COMBINED_TEXTURE_IMAGE_UNITS]: 80,
            [GL.MAX_VARYING_VECTORS]: 32 },
  generic: {},
};

function gpuClass(renderer) {
  const r = String(renderer).toLowerCase();
  if (/nvidia|geforce|quadro|rtx|gtx/.test(r)) return "nvidia";
  if (/amd|radeon|firepro/.test(r)) return "amd";
  if (/intel|hd graphics|uhd|iris/.test(r)) return "intel";
  if (/apple|m1|m2|m3/.test(r)) return "apple";
  return "generic";
}

// Extensions exposed by a modern desktop Firefox. Acts as an ALLOWLIST: the
// C++ hooks intersect these names with the backend's supported/permitted set.
// This avoids promising functionality the driver cannot supply. The resulting
// subset can vary by backend; these lists reduce exposure, not emulate support.
const GL1_EXTENSIONS = [
  "ANGLE_instanced_arrays", "EXT_blend_minmax", "EXT_color_buffer_half_float",
  "EXT_float_blend", "EXT_frag_depth", "EXT_shader_texture_lod",
  "EXT_sRGB", "EXT_texture_compression_bptc", "EXT_texture_compression_rgtc",
  "EXT_texture_filter_anisotropic", "OES_element_index_uint",
  "OES_fbo_render_mipmap", "OES_standard_derivatives", "OES_texture_float",
  "OES_texture_float_linear", "OES_texture_half_float",
  "OES_texture_half_float_linear", "OES_vertex_array_object",
  "WEBGL_color_buffer_float", "WEBGL_compressed_texture_s3tc",
  "WEBGL_compressed_texture_s3tc_srgb", "WEBGL_debug_renderer_info",
  "WEBGL_debug_shaders", "WEBGL_depth_texture", "WEBGL_draw_buffers",
  "WEBGL_lose_context",
];
const GL2_EXTENSIONS = [
  "EXT_color_buffer_float", "EXT_color_buffer_half_float", "EXT_float_blend",
  "EXT_texture_compression_bptc", "EXT_texture_compression_rgtc",
  "EXT_texture_filter_anisotropic", "OES_draw_buffers_indexed",
  "OES_texture_float_linear", "WEBGL_compressed_texture_s3tc",
  "WEBGL_compressed_texture_s3tc_srgb", "WEBGL_debug_renderer_info",
  "WEBGL_debug_shaders", "WEBGL_lose_context", "WEBGL_multi_draw",
];

// IEEE-754 single precision — identical on essentially all desktop GPUs, so
// pinning removes a per-driver signal without looking unusual. Keyed
// "shaderType,precisionType" (see MaskConfig::MShaderData).
function shaderPrecision() {
  const VERTEX = 35633, FRAGMENT = 35632;
  const LOW_F = 36336, MED_F = 36337, HIGH_F = 36338;
  const LOW_I = 36339, MED_I = 36340, HIGH_I = 36341;
  const f = { rangeMin: 127, rangeMax: 127, precision: 23 };
  const i = { rangeMin: 31, rangeMax: 30, precision: 0 };
  const out = {};
  for (const st of [VERTEX, FRAGMENT]) {
    for (const pt of [LOW_F, MED_F, HIGH_F]) out[`${st},${pt}`] = { ...f };
    for (const pt of [LOW_I, MED_I, HIGH_I]) out[`${st},${pt}`] = { ...i };
  }
  return out;
}

// Emit the tables for both WebGL1 and WebGL2. blockIfNotDefined is deliberately
// NOT set: unlisted pnames fall through to the real value rather than becoming
// null, which would break real WebGL content and is itself a loud tell.
export function fillWebGLKeys(keys, renderer) {
  const params = { ...GL_BASE, ...GL_CLASS[gpuClass(renderer)] };
  // RENDERER must agree with webGl:renderer (UNMASKED_RENDERER_WEBGL) — the
  // mismatch between them was the original bug. VENDOR stays "Mozilla", which
  // is what stock Firefox reports.
  const table = {};
  for (const [pname, value] of Object.entries(params)) table[pname] = value;
  table[GL.VENDOR] = "Mozilla";
  if (renderer) table[GL.RENDERER] = renderer;

  keys["webGl:parameters"] = table;
  // WebGL2-only pnames must not become valid queries on a WebGL1 context.
  // Pair vector queries with their WebGL2 scalar-component queries. These
  // describe one profile; leaving components native mixed unrelated devices.
  // Gecko derives varying vectors from fragment inputs, independently of
  // vertex outputs and MAX_VARYING_COMPONENTS. This does not change backend
  // allocation/validation limits: the static profile is not a capability grant.
  keys["webGl2:parameters"] = {
    ...table,
    35658: 4 * params[GL.MAX_VERTEX_UNIFORM_VECTORS],
    35657: 4 * params[GL.MAX_FRAGMENT_UNIFORM_VECTORS],
    37157: 4 * params[GL.MAX_VARYING_VECTORS], // MAX_FRAGMENT_INPUT_COMPONENTS
    35375: 24,   // MAX_UNIFORM_BUFFER_BINDINGS
    35380: 256,  // UNIFORM_BUFFER_OFFSET_ALIGNMENT
    32883: 2048, // MAX_3D_TEXTURE_SIZE
    35071: 256,  // MAX_ARRAY_TEXTURE_LAYERS
  };
  keys["webGl:supportedExtensions"] = GL1_EXTENSIONS;
  keys["webGl2:supportedExtensions"] = GL2_EXTENSIONS;
  const prec = shaderPrecision();
  keys["webGl:shaderPrecisionFormats"] = prec;
  keys["webGl2:shaderPrecisionFormats"] = prec;
}

// Repair saved generated tables only when BOTH versions exactly match the old
// emitter for this renderer class. Any customized/unknown/missing field opts
// the entire tuple out. Independent scalar override prefs are applied later by
// SeedSync, so their existing precedence is preserved.
function migrateGeneratedWebGLProfile(keys) {
  const renderer = keys["webGl:renderer"];
  if (typeof renderer !== "string" || !renderer) return keys;
  const generated = {};
  fillWebGLKeys(generated, renderer);
  // Immutable pre-repair emitter snapshot: deriving this from today's table
  // would silently widen/change the migration whenever new profiles evolve.
  const legacy1 = {
    7936: "Mozilla", 7937: renderer,
    3379: 16384, 34076: 16384, 34024: 16384, 3386: [32767, 32767],
    34921: 16, 36347: 4096, 36348: 30, 36349: 1024,
    34930: 16, 35660: 16, 35661: 32,
    33902: [1, 1], 33901: [1, 1024], 36183: 4,
  };
  switch (gpuClass(renderer)) {
    case "nvidia": Object.assign(legacy1, { 3386: [32768, 32768], 36183: 8 }); break;
    case "amd": Object.assign(legacy1, { 3386: [16384, 16384], 36183: 8 }); break;
    case "intel": Object.assign(legacy1, { 3386: [16384, 16384] }); break;
    case "apple": Object.assign(legacy1, { 3386: [16384, 16384], 35661: 80, 36348: 32 }); break;
  }
  const legacy2 = { ...legacy1, 35375: 24, 35380: 256, 32883: 2048, 35071: 256 };
  const matches = (actual, expected) => actual && typeof actual === "object" &&
    !Array.isArray(actual) && Object.keys(actual).length === Object.keys(expected).length &&
    Object.keys(expected).every(key => Object.hasOwn(actual, key) &&
      JSON.stringify(actual[key]) === JSON.stringify(expected[key]));
  if (!matches(keys["webGl:parameters"], legacy1) ||
      !matches(keys["webGl2:parameters"], legacy2)) return keys;
  return { ...keys,
    "webGl:parameters": generated["webGl:parameters"],
    "webGl2:parameters": generated["webGl2:parameters"],
  };
}

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

// The CSS-generic prefs (font.name-list.<generic>.x-western) are PROCESS-GLOBAL
// — one value for every container — but each container narrows to its own
// persona's font allowlist. font.name-list.* prefs are COMMA-SEPARATED fallback
// LISTS, so we publish the UNION of all three OSes' generics and let Gecko pick
// the first that resolves under the active container's per-container filter
// (FontListManager). For this to work cross-OS, font-hijacker.patch also keeps
// all these families in the process-global whitelist so ApplyWhitelist doesn't
// delete them; the per-container filter still hides the ones outside a
// container's persona.
//
// ORDER MATTERS — macOS → Windows → Linux — so each OS resolves its OWN generic,
// not merely a valid one:
//   serif: Times(mac-only) → Times New Roman(win, also mac) → DejaVu Serif(linux)
//   sans:  Helvetica(mac-only) → Arial(win, also mac) → DejaVu Sans(linux)
//   mono:  Menlo(mac-only) → Consolas(win-only) → DejaVu Sans Mono(linux)
// A macOS container hits its exclusive font first (Times/Helvetica/Menlo); a
// Windows container skips those (not in its allowlist) and lands on
// TNR/Arial/Consolas; Linux lands on DejaVu — each matching GENERIC_FONTS[os].
export function genericFontListUnion() {
  const order = ["macos", "windows", "linux"];
  const join = (slot) => {
    const seen = new Set();
    const out = [];
    for (const os of order) {
      const fam = GENERIC_FONTS[os][slot];
      if (fam && !seen.has(fam)) { seen.add(fam); out.push(fam); }
    }
    return out.join(", ");
  };
  return { serif: join("serif"), sans: join("sans"), mono: join("mono") };
}

function detectOSFromUA(ua) {
  if (!ua) return "linux";
  if (ua.includes("Macintosh") || ua.includes("Mac OS")) return "macos";
  if (ua.includes("Windows")) return "windows";
  return "linux";
}

function normalizeUA(ua, version = FIREFOX_VERSION, browser = "firefox") {
  if (!ua) return ua;
  const major = parseInt(version, 10);
  const firefoxVersion = `${major}.0`;
  if (browser === "firefox") return ua
    .replace(/rv:\d+\.\d+/, `rv:${firefoxVersion}`)
    .replace(/Firefox\/\d+\.\d+/, `Firefox/${firefoxVersion}`);
  const os = detectOSFromUA(ua);
  const platform = os === "windows" ? "Windows NT 10.0; Win64; x64" :
    os === "macos" ? "Macintosh; Intel Mac OS X 10_15_7" : "X11; Linux x86_64";
  const chrome = `Mozilla/5.0 (${platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${major}.0.0.0 Safari/537.36`;
  if (browser === "chrome") return chrome;
  if (browser === "edge") return `${chrome} Edg/${major}.0.0.0`;
  if (browser === "chromium") return chrome.replace("Chrome/", "Chromium/");
  if (browser === "safari") {
    const safariPlatform = os === "macos" ? platform : "Macintosh; Intel Mac OS X 10_15_7";
    return `Mozilla/5.0 (${safariPlatform}) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/${major}.0 Safari/605.1.15`;
  }
  throw new Error("Unknown browser identity family.");
}

// Upgrade only the generated desktop Firefox identity shape. Version tokens
// change in place, preserving OS, hardware, and all seed-derived entropy.
// Custom identity strings are left alone; explicit override prefs are applied
// last by SeedSync, even when they contain the same shape as generated values.
export function migratePersonaVersion(keys) {
  const out = { ...migrateGeneratedWebGLProfile(keys) };
  const generatedUA = /^(?:Mozilla\/)?5\.0 \((?:Windows NT|Macintosh;|X11;|Linux )[^)]*; rv:\d+\.\d+\) Gecko\/20100101 Firefox\/\d+\.\d+$/;
  for (const key of ["navigator.userAgent", "headers.User-Agent", "navigator.appVersion"]) {
    if (typeof out[key] === "string" && generatedUA.test(out[key])) {
      out[key] = normalizeUA(out[key]);
    }
  }
  // Early BrowserForge identities could persist a coherent navigator tuple
  // alongside the font set of another OS. This is visible to users as an
  // unexpected generic fallback (for example, a MacIntel identity rendering
  // every textarea with DejaVu Sans Mono) and is also fingerprint-incoherent.
  // Repair only a recognized generated Firefox UA with explicit contradictory
  // generic metadata. Configs without generic metadata and custom UAs retain
  // their historical values.
  const ua = out["navigator.userAgent"];
  if (typeof ua === "string" && generatedUA.test(ua)) {
    const os = detectOSFromUA(ua);
    const expected = GENERIC_FONTS[os];
    const genericKeys = [
      ["font:generic:serif", "serif"],
      ["font:generic:sans-serif", "sans"],
      ["font:generic:monospace", "mono"],
    ];
    const hasGenericMetadata = genericKeys.some(([key]) => key in out);
    const contradictsOS = hasGenericMetadata && genericKeys.some(
      ([key, slot]) => key in out && out[key] !== expected[slot]
    );
    if (contradictsOS) {
      const canonical = CANONICAL_FONTS[os];
      const retainedOptional = Array.isArray(out.fonts)
        ? out.fonts.filter(font => canonical.optional.includes(font))
        : [];
      out.fonts = [...new Set([...canonical.base, ...retainedOptional])].sort();
      for (const [key, slot] of genericKeys) out[key] = expected[slot];
    }
  }
  // A shipped, uniform fallback for styled mathematical Unicode letters.
  // Explicit custom font overrides are applied later and remain authoritative.
  if (typeof ua === "string" && generatedUA.test(ua) && Array.isArray(out.fonts) && !out.fonts.includes("Noto Sans Math")) {
    out.fonts = [...out.fonts, "Noto Sans Math"].sort();
  }
  return out;
}

// Legacy default-only helper; opt-in intent is resolved by the registry.
export function deriveHttpProfile(_ua) {
  // The wire protocol comes from Gecko/NSS/neqo. UA overrides do not change
  // the engine: keep H2 and H3 in the same Firefox cohort as the ClientHello.
  return { h2: "firefox", h3: 0 };
}

// Persist the per-container H2/H3 fingerprint profile derived from the
// parent-process network registry. Preserve this entry point for persona
// callers; the registry owns saved intent and exact container profile IDs.
export function writeHttpProfilePrefs(ucid, ua) {
  writeNetworkProfile(ucid, ua);
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
function bfToCloakKeys(fp, prng, version = FIREFOX_VERSION, browser = "firefox") {
  const keys = {};
  const ua = normalizeUA(fp.userAgent || "", version, browser);
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
  // maxTouchPoints is pinned to 0 for these desktop personas. BrowserForge
  // occasionally samples a touch-capable device (observed: 5), but the touch
  // API SURFACE is controlled by dom.w3c_touch_events.enabled, which is off —
  // so a non-zero value ships with no TouchEvent/Touch constructor and no
  // ontouchstart. FingerprintJS's touchSupport reads exactly that triple, and
  // "5 touch points but the browser has no touch API" is impossible. Pinning 0
  // matches both the actual surface and the desktop majority.
  keys["navigator:maxTouchPoints"] = 0;

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
    // Window geometry must be DERIVED, not taken from BrowserForge's
    // independently-sampled inner*/outer* fields — those can contradict each
    // other (observed: inner 2056x1218 inside outer 1690x956, a viewport wider
    // than its own window, which is impossible and trivially detectable). Same
    // reasoning as NAV_IDENTITY above, which derives platform/oscpu rather than
    // trusting BF's separate samples.
    //
    // Invariants enforced here:
    //   inner <= outer <= avail <= screen
    //   innerWidth  == outerWidth        (modern Firefox has no side borders)
    //   innerHeight == outerHeight - browser chrome
    const availW = keys["screen.availWidth"] || w;
    const availH = keys["screen.availHeight"] || h;
    const outerW = Math.min(sc.outerWidth || availW, availW);
    const outerH = Math.min(sc.outerHeight || (h - decor.taskbar), availH);
    keys["window.outerWidth"]  = outerW;
    keys["window.outerHeight"] = outerH;
    keys["window.innerWidth"]  = outerW;
    keys["window.innerHeight"] = Math.max(200, outerH - decor.firefoxChrome);
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
    fillWebGLKeys(keys, fp.videoCard.renderer || "");
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
  // (Gecko_MediaFeatures_ColorGamut / _PrefersContrast). These must be emitted,
  // otherwise CSS `@media` sees the
  // real host while CloakfoxMediaQueryChild pins the JS matchMedia side — a
  // contradiction no real browser produces. CloakfoxMediaQueryChild reads
  // these same keys so both paths share one source of truth.
  //   colorGamut:  0 = srgb, 1 = p3, 2 = rec2020
  //   contrast:    0 = no-preference, 1 = less, 2 = more, 3 = custom
  // Website appearance follows Firefox preferences; do not pin a persona theme.
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
  // Cap the real inventory and normalize labels; exact device selection still
  // resolves to the physical capture backend, never a synthetic replacement.
  keys["mediaDevices:enabled"] = true;
  keys["mediaDevices:micros"] = 1;
  keys["mediaDevices:webcams"] = 1;
  keys["mediaDevices:speakers"] = 1;
  keys["mediaFeature:invertedColors"]             = false;
  keys["mediaFeature:prefersReducedMotion"]       = false;
  keys["mediaFeature:prefersReducedTransparency"] = false;
  // Gecko_MediaFeatures_GetResolution returns DPPX (device pixels per CSS
  // pixel), not DPI — see its comment in nsMediaFeatures.cpp. Emitting 96*dpr
  // made the engine claim a 96x pixel ratio, so `(resolution: 1dppx)` did not
  // match on a dpr=1 persona: impossible in a real browser and a one-token
  // tamper signature. Emit the dpr itself.
  const dpr = keys["window.devicePixelRatio"] || 1;
  keys["mediaFeature:resolution"]   = dpr;
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
 * @param {number|null} ucid  Container userContextId; resolves the optional
 *                            OS/hardware generation filters for that container.
 * @param {Object|null} constraints  Explicit filters when validating a new generation.
 * @returns {Object}  Flat dict keyed on cloak_cfg keys.
 */
// Missing mode means a pre-existing identity. Never silently re-sample it on
// an ordinary settings change or upgrade.
export function personaOSMode(ucid) {
  const mode = ucid === null ? "legacy" : Services.prefs.getStringPref(
    `cloakfox.container.${ucid}.persona_os_mode`, "legacy");
  return ["host", "legacy", "windows", "macos", "linux"].includes(mode) ? mode : "legacy";
}
function sampleForMode(prng, mode, hostOS = Services.appinfo.OS) {
  if (mode === "legacy") return sampleFingerprint(prng);
  return sampleHostFingerprint(prng, sampleFingerprint, mode === "host" ? hostOS : mode);
}

export function fillPersonaKeys(seedB64, ucid = null, constraints = null) {
  const prng = makeSeededPRNG(seedB64);
  const mode = personaOSMode(ucid);
  const prefix = `cloakfox.container.${ucid}.`;
  const rawOS = ucid === null ? "auto" : Services.prefs.getStringPref(prefix + "persona_os", "auto");
  const rawHardware = ucid === null ? "auto" : Services.prefs.getStringPref(prefix + "persona_hardware", "auto");
  const rawBrowser = ucid === null ? "firefox" : Services.prefs.getStringPref(prefix + "persona_browser", "firefox");
  const rawVersion = ucid === null ? "auto" : Services.prefs.getStringPref(prefix + "persona_version", "auto");
  const savedOS = ["auto", "windows", "macos", "linux"].includes(rawOS) ? rawOS : "auto";
  const savedHardware = ["auto", "apple", "intel", "nvidia", "amd", "software", "other"].includes(rawHardware) ? rawHardware : "auto";
  const filtered = constraints !== null || savedOS !== "auto" || savedHardware !== "auto";
  const savedBrowser = ["firefox", "chrome", "edge", "chromium", "safari"].includes(rawBrowser) ? rawBrowser : "firefox";
  const savedVersion = rawVersion === "random-recent" || /^\d+$/.test(rawVersion) ? rawVersion : "auto";
  const filters = constraints || (savedVersion === "auto"
    ? { os: savedOS, hardware: savedHardware }
    : { browser: savedBrowser, version: savedVersion, os: savedOS, hardware: savedHardware });
  let fp = filtered ? samplePersonaFingerprint(prng, filters) : sampleForMode(prng, mode);
  if (ucid !== null) {
    const index = Services.prefs.getIntPref(`cloakfox.container.${ucid}.persona_index`, -1);
    if (!filtered && index >= 0 && index < 30) fp = previewPersona(index, mode);
  }
  let selectedVersion = filters.version || "auto";
  if (selectedVersion === "random-recent") selectedVersion = String(parseInt(FIREFOX_VERSION, 10) - Math.floor(prng() * 3));
  const keys = bfToCloakKeys(fp, prng, selectedVersion === "auto" ? FIREFOX_VERSION : selectedVersion, filters.browser || savedBrowser);

  // Precise/PBO GPU readbacks bypass canvas noise. Explicit opt-out preserves
  // compute compatibility; never perturb numerical application buffers.
  keys["webgl:typed_readback:disabled"] = userOpt("webgl_typed_readback_disabled", true);
  keys["canvas:render_privacy"] = userOpt("canvas_render_privacy") === true;
  keys["webGl:backend_profile"] = userOpt("gpu_backend_profiles") === true;
  // Internal foundation experiment; existing readback guards remain enabled.
  keys["canvas:canonical_2d"] = false;
  try {
    keys["canvas:canonical_2d"] = Services.prefs.getBoolPref(
        "cloakfox.experimental.canvas_pipeline", false) === true;
  } catch (_e) { /* malformed preference keeps the experiment disabled */ }
  keys["canvas:canonical_gpu"] = keys["canvas:canonical_2d"];
  if (keys["canvas:canonical_gpu"]) {
    keys["webGl:backend_profile"] = true;
    keys["webgl:typed_readback:disabled"] = true;
  }

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
 * Legacy fixed-persona picker compatibility: generate a
 * deterministic preview list of N personas using fixed seeds. The
 * persona_index pref pins which preview a container uses (overriding
 * its master seed).
 *
 * This replaces the predefined PERSONAS pool's listPersonas. From the
 * UI's perspective the API is identical — array of {index, label} —
 * but personas come from BF runtime sampling rather than a baked file.
 */
export function listPersonas(hostOS = Services.appinfo.OS, mode = "legacy") {
  const N = 30;
  const out = [];
  for (let i = 0; i < N; i++) {
    // Fixed-seed sampling: deterministic preview list. Index 0 always
    // looks the same, index 1 always looks the same, etc. Across browser
    // restarts the user sees a stable list.
    const prng = mulberry32(0xC10A * (i + 1));
    const fp = sampleForMode(prng, mode, hostOS);
    const platform = ({MacIntel: "macOS", Win32: "Windows", "Linux x86_64": "Linux"})[fp.platform] || fp.platform || "?";
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
function previewPersona(index, mode = "legacy", hostOS = Services.appinfo.OS) {
  const prng = mulberry32(0xC10A * (index + 1));
  return sampleForMode(prng, mode, hostOS);
}

/**
 * Compatibility shim for callers that still expect the old
 * pickPersona API (returns a flat persona dict). Honors the
 * cloakfox.container.<ucid>.persona_index pref by sampling from a
 * fixed-seed preview index instead of the master seed.
 *
 * Most callers should use fillPersonaKeys directly.
 */
export function pickPersona(seedB64, hostOS = Services.appinfo.OS, ucid = null) {
  const mode = personaOSMode(ucid);
  if (ucid !== null) {
    try {
      const idx = Services.prefs.getIntPref(
        `cloakfox.container.${ucid}.persona_index`, -1
      );
      if (idx >= 0 && idx < 30) {
        return bfToFlatPreview(previewPersona(idx, mode, hostOS));
      }
    } catch (_e) { /* fall through */ }
  }
  // Deterministic from master seed.
  const prng = makeSeededPRNG(seedB64);
  return bfToFlatPreview(sampleForMode(prng, mode, hostOS));
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
