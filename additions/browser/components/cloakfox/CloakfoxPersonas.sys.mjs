/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: per-container fingerprint personas.
 *
 * A "persona" is a coherent identity package — UA, platform string,
 * screen dimensions, GPU details, hardware concurrency, language —
 * picked to be internally consistent so a fingerprinter can't catch
 * us on a "Windows UA + Apple GPU" mismatch. One persona per
 * container, deterministically picked from math_seed.
 *
 * SCOPE: persona generation is OS-family-locked to the host OS. A
 * macOS host sees only macOS personas, Windows host sees Windows,
 * Linux host sees Linux. This avoids the deepest fingerprint
 * mismatches (UA says Windows but WebGL says Apple) while still
 * giving per-container variance in screen / GPU / language. Cross-
 * OS personas (BrowserForge-style "Mac host pretending to be
 * Windows") are a future enhancement requiring a coherence engine.
 *
 * Each persona's MaskConfig keys are normalized — every key Firefox
 * reads via MaskConfig::Get* gets a value here, so no patch falls
 * through to system defaults. The output of fillPersonaKeys() is
 * merged into cloak_cfg_<ucid> alongside the canvas/audio/font seed
 * keys. Driver order in the JSON doesn't matter — the C++ side reads
 * by key name.
 *
 * Firefox version follows the actual build: MOZILLA_UAVERSION via
 * the milestone. Hardcoded "146.0" here; bump when upstream rebases.
 */

const FIREFOX_VERSION = "146.0";

/* ─── Per-OS persona pools ───────────────────────────────────────────
 *
 * Three personas per OS family, picked to span common-laptop dimensions
 * and GPU vendors. Resolution + DPR pairs are realistic Apple / common
 * Windows / Linux configs. WebGL renderer strings match what real Firefox
 * reports for those GPUs (verified against browserleaks samples).
 */

const MAC_PERSONAS = [
  {
    label: "macOS-1440x900-AppleM1",
    osVersion: "14.5",  // Sonoma
    uaSuffix: "Macintosh; Intel Mac OS X 10.15",
    appVersion: "5.0 (Macintosh)",
    platform: "MacIntel",
    oscpu: "Intel Mac OS X 10.15",
    locale: { lang: "en-US", langs: ["en-US", "en"] },
    screen: { width: 1440, height: 900, dpr: 2.0 },
    hardwareConcurrency: 8,
    deviceMemory: 8,
    webGl: { vendor: "Apple Inc.", renderer: "Apple GPU" },
    audioOutputLatency: 0.005,
  },
  {
    label: "macOS-1512x982-M2",
    osVersion: "14.5",
    uaSuffix: "Macintosh; Intel Mac OS X 10.15",
    appVersion: "5.0 (Macintosh)",
    platform: "MacIntel",
    oscpu: "Intel Mac OS X 10.15",
    locale: { lang: "en-US", langs: ["en-US", "en"] },
    screen: { width: 1512, height: 982, dpr: 2.0 },
    hardwareConcurrency: 10,
    deviceMemory: 8,
    webGl: { vendor: "Apple Inc.", renderer: "Apple GPU" },
    audioOutputLatency: 0.005,
  },
  {
    label: "macOS-1920x1080-Intel",
    osVersion: "14.5",
    uaSuffix: "Macintosh; Intel Mac OS X 10.15",
    appVersion: "5.0 (Macintosh)",
    platform: "MacIntel",
    oscpu: "Intel Mac OS X 10.15",
    locale: { lang: "en-US", langs: ["en-US", "en"] },
    screen: { width: 1920, height: 1080, dpr: 1.0 },
    hardwareConcurrency: 12,
    deviceMemory: 16,
    webGl: { vendor: "Apple Inc.", renderer: "Apple GPU" },
    audioOutputLatency: 0.005,
  },
];

const WIN_PERSONAS = [
  {
    label: "Win10-1920x1080-Intel",
    osVersion: "10.0",
    uaSuffix: "Windows NT 10.0; Win64; x64",
    appVersion: "5.0 (Windows)",
    platform: "Win32",
    oscpu: "Windows NT 10.0; Win64; x64",
    locale: { lang: "en-US", langs: ["en-US", "en"] },
    screen: { width: 1920, height: 1080, dpr: 1.0 },
    hardwareConcurrency: 8,
    deviceMemory: 8,
    webGl: { vendor: "Google Inc. (Intel)", renderer: "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0)" },
    audioOutputLatency: 0.012,
  },
  {
    label: "Win11-1366x768-Intel",
    osVersion: "10.0",
    uaSuffix: "Windows NT 10.0; Win64; x64",
    appVersion: "5.0 (Windows)",
    platform: "Win32",
    oscpu: "Windows NT 10.0; Win64; x64",
    locale: { lang: "en-US", langs: ["en-US", "en"] },
    screen: { width: 1366, height: 768, dpr: 1.0 },
    hardwareConcurrency: 4,
    deviceMemory: 8,
    webGl: { vendor: "Google Inc. (Intel)", renderer: "ANGLE (Intel, Intel(R) HD Graphics 4600 Direct3D11 vs_5_0 ps_5_0)" },
    audioOutputLatency: 0.012,
  },
  {
    label: "Win11-2560x1440-NVIDIA",
    osVersion: "10.0",
    uaSuffix: "Windows NT 10.0; Win64; x64",
    appVersion: "5.0 (Windows)",
    platform: "Win32",
    oscpu: "Windows NT 10.0; Win64; x64",
    locale: { lang: "en-US", langs: ["en-US", "en"] },
    screen: { width: 2560, height: 1440, dpr: 1.0 },
    hardwareConcurrency: 16,
    deviceMemory: 16,
    webGl: { vendor: "Google Inc. (NVIDIA)", renderer: "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)" },
    audioOutputLatency: 0.012,
  },
];

const LINUX_PERSONAS = [
  {
    label: "Linux-1920x1080-Intel",
    osVersion: "x86_64",
    uaSuffix: "X11; Linux x86_64",
    appVersion: "5.0 (X11)",
    platform: "Linux x86_64",
    oscpu: "Linux x86_64",
    locale: { lang: "en-US", langs: ["en-US", "en"] },
    screen: { width: 1920, height: 1080, dpr: 1.0 },
    hardwareConcurrency: 8,
    deviceMemory: 16,
    webGl: { vendor: "Mesa", renderer: "Mesa Intel(R) UHD Graphics 620 (KBL GT2)" },
    audioOutputLatency: 0.010,
  },
  {
    label: "Linux-1440x900-AMD",
    osVersion: "x86_64",
    uaSuffix: "X11; Linux x86_64",
    appVersion: "5.0 (X11)",
    platform: "Linux x86_64",
    oscpu: "Linux x86_64",
    locale: { lang: "en-US", langs: ["en-US", "en"] },
    screen: { width: 1440, height: 900, dpr: 1.0 },
    hardwareConcurrency: 12,
    deviceMemory: 16,
    webGl: { vendor: "Mesa", renderer: "AMD Radeon Graphics (radeonsi, raphael_mendocino, LLVM 17.0.6, DRM 3.57, 6.8.0)" },
    audioOutputLatency: 0.010,
  },
  {
    label: "Linux-2560x1440-NVIDIA",
    osVersion: "x86_64",
    uaSuffix: "X11; Linux x86_64",
    appVersion: "5.0 (X11)",
    platform: "Linux x86_64",
    oscpu: "Linux x86_64",
    locale: { lang: "en-US", langs: ["en-US", "en"] },
    screen: { width: 2560, height: 1440, dpr: 1.0 },
    hardwareConcurrency: 16,
    deviceMemory: 32,
    webGl: { vendor: "NVIDIA Corporation", renderer: "NVIDIA GeForce RTX 3060/PCIe/SSE2" },
    audioOutputLatency: 0.010,
  },
];

const POOLS = {
  darwin: MAC_PERSONAS,
  winnt: WIN_PERSONAS,
  linux: LINUX_PERSONAS,
};

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

export function pickPersona(seedB64, hostOS = detectHostOS()) {
  const pool = POOLS[hostOS] || LINUX_PERSONAS;
  return pool[seedU32(seedB64) % pool.length];
}

export function fillPersonaKeys(seedB64) {
  const p = pickPersona(seedB64);
  const ua = `Mozilla/5.0 (${p.uaSuffix}; rv:${FIREFOX_VERSION}) Gecko/20100101 Firefox/${FIREFOX_VERSION}`;
  return {
    // ── UA + headers ─────────────────────────────────────────────
    "navigator.userAgent": ua,
    "navigator.appVersion": p.appVersion,
    "navigator.platform": p.platform,
    "navigator.oscpu": p.oscpu,
    "navigator.language": p.locale.lang,
    "headers.User-Agent": ua,
    "headers.Accept-Language": `${p.locale.lang},en;q=0.5`,
    "headers.Accept-Encoding": "gzip, deflate, br, zstd",

    // ── locale ────────────────────────────────────────────────────
    "locale:language": p.locale.lang.split("-")[0],
    "locale:region": p.locale.lang.split("-")[1] || "US",
    "locale:script": "Latn",

    // ── screen / window ───────────────────────────────────────────
    "window.innerWidth": p.screen.width,
    "window.innerHeight": p.screen.height,
    "window.devicePixelRatio": p.screen.dpr,
    "screen.pageXOffset": 0,
    "screen.pageYOffset": 0,
    "screen:orientation:type": "landscape-primary",
    "mediaFeature:resolution": p.screen.dpr,

    // ── WebGL ─────────────────────────────────────────────────────
    "webGl:vendor": p.webGl.vendor,
    "webGl:renderer": p.webGl.renderer,

    // ── Audio ─────────────────────────────────────────────────────
    "AudioContext:outputLatency": p.audioOutputLatency,

    // ── Spoof flags (bool=true means C++ patch substitutes) ──────
    "codecs:spoof": true,
    "mediaCapabilities:spoof": true,
    "permissions:spoof": true,
    "voices:fakeCompletion": true,
    "voices:fakeCompletion:charsPerSecond": 16,
    "voices:blockIfNotDefined": false,

    // ── Disable noisy / leaky surfaces ───────────────────────────
    "navigator:vibrate:disabled": true,
    "navigator:webgpu:disabled": true,
    "document:lastModified:hidden": true,
    "indexedDB:databases:hidden": true,
    "window:name:disabled": true,

    // ── Media features (avoid OS-theme leak) ─────────────────────
    "mediaFeature:invertedColors": false,
    "mediaFeature:prefersReducedMotion": false,
    "mediaFeature:prefersReducedTransparency": false,
  };
}
