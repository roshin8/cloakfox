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

/* ─── Chrome / OS-decoration heights ──────────────────────────────────
 *
 * Firefox chrome (URL bar + tab strip) and OS task/menu bar sizes,
 * used to derive coherent inner / outer / avail dimensions from a
 * persona's screen.width × screen.height.
 *
 * Approximate values — exact pixel counts depend on theme / DPI /
 * compact mode, but the C++ MaskConfig consumers don't probe for
 * theme accuracy; they just want internally-consistent numbers
 * across screen.* / window.outer.* / window.inner.*.
 */
const CHROME_DECOR = {
  darwin: { menuBar: 25, taskbar: 0,  firefoxChrome: 86 },  // OS X menubar at top, Dock auto-hides on Retina laptops, Firefox chrome ~86
  winnt:  { menuBar: 0,  taskbar: 40, firefoxChrome: 90 },  // Win10/11 taskbar usually 40px, Firefox chrome ~90
  linux:  { menuBar: 0,  taskbar: 32, firefoxChrome: 80 },  // GNOME / KDE typical ~32px panel
};

function decorFor(hostOS) {
  return CHROME_DECOR[hostOS] || CHROME_DECOR.linux;
}

/* ─── Per-OS persona pools ───────────────────────────────────────────
 *
 * Eight personas per OS family, picked to span common-laptop dimensions,
 * core counts, and GPU vendors. Resolution + DPR pairs are realistic
 * Apple / common Windows / Linux configs. WebGL renderer strings match
 * what real Firefox reports for those GPUs (verified against browser-
 * leaks samples). With ~8 personas/OS the pool is large enough that
 * "you're one of N known Cloakfox personas" is a weaker correlation
 * signal — random selection by seed gives ~1/8 collision rate per
 * pair instead of the previous ~1/3.
 *
 * Each persona has identical UA-suffix / appVersion / platform / oscpu
 * within its OS family — those can't vary on the same Firefox without
 * looking like a different browser. The variance is in screen dims,
 * GPU, hwc, and where applicable language.
 */

// Shared OS-family fields, factored out to keep pools compact.
const MAC_BASE = {
  osVersion: "14.5",  // Sonoma
  uaSuffix: "Macintosh; Intel Mac OS X 10.15",
  appVersion: "5.0 (Macintosh)",
  platform: "MacIntel",
  oscpu: "Intel Mac OS X 10.15",
  locale: { lang: "en-US", langs: ["en-US", "en"] },
  audioOutputLatency: 0.005,
  webGl: { vendor: "Apple Inc.", renderer: "Apple GPU" },
};
const WIN_BASE = {
  osVersion: "10.0",
  uaSuffix: "Windows NT 10.0; Win64; x64",
  appVersion: "5.0 (Windows)",
  platform: "Win32",
  oscpu: "Windows NT 10.0; Win64; x64",
  locale: { lang: "en-US", langs: ["en-US", "en"] },
  audioOutputLatency: 0.012,
};
const LIN_BASE = {
  osVersion: "x86_64",
  uaSuffix: "X11; Linux x86_64",
  appVersion: "5.0 (X11)",
  platform: "Linux x86_64",
  oscpu: "Linux x86_64",
  locale: { lang: "en-US", langs: ["en-US", "en"] },
  audioOutputLatency: 0.010,
};

const MAC_PERSONAS = [
  { ...MAC_BASE, label: "macOS-1280x800-M1",   screen: { width: 1280, height: 800,  dpr: 2.0 }, hardwareConcurrency: 8,  deviceMemory: 8 },
  { ...MAC_BASE, label: "macOS-1440x900-M1",   screen: { width: 1440, height: 900,  dpr: 2.0 }, hardwareConcurrency: 8,  deviceMemory: 8 },
  { ...MAC_BASE, label: "macOS-1512x982-M2",   screen: { width: 1512, height: 982,  dpr: 2.0 }, hardwareConcurrency: 10, deviceMemory: 8 },
  { ...MAC_BASE, label: "macOS-1680x1050-M2",  screen: { width: 1680, height: 1050, dpr: 2.0 }, hardwareConcurrency: 10, deviceMemory: 16 },
  { ...MAC_BASE, label: "macOS-1728x1117-M3",  screen: { width: 1728, height: 1117, dpr: 2.0 }, hardwareConcurrency: 12, deviceMemory: 16 },
  { ...MAC_BASE, label: "macOS-1920x1080-Int", screen: { width: 1920, height: 1080, dpr: 1.0 }, hardwareConcurrency: 12, deviceMemory: 16 },
  { ...MAC_BASE, label: "macOS-2056x1329-M3M", screen: { width: 2056, height: 1329, dpr: 2.0 }, hardwareConcurrency: 14, deviceMemory: 32 },
  { ...MAC_BASE, label: "macOS-2560x1440-Int", screen: { width: 2560, height: 1440, dpr: 1.0 }, hardwareConcurrency: 16, deviceMemory: 32 },
];

// Windows GPU strings — ANGLE-prefixed, real samples from browserleaks
// FP collection. Mix of Intel UHD/HD/Iris generations + NVIDIA + AMD.
const WIN_GPU_INTEL_HD =     { vendor: "Google Inc. (Intel)",  renderer: "ANGLE (Intel, Intel(R) HD Graphics 4600 Direct3D11 vs_5_0 ps_5_0)" };
const WIN_GPU_INTEL_UHD =    { vendor: "Google Inc. (Intel)",  renderer: "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0)" };
const WIN_GPU_INTEL_IRIS =   { vendor: "Google Inc. (Intel)",  renderer: "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0)" };
const WIN_GPU_NVIDIA_3060 =  { vendor: "Google Inc. (NVIDIA)", renderer: "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)" };
const WIN_GPU_NVIDIA_3070 =  { vendor: "Google Inc. (NVIDIA)", renderer: "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0)" };
const WIN_GPU_AMD_RX580 =    { vendor: "Google Inc. (AMD)",    renderer: "ANGLE (AMD, AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0)" };

const WIN_PERSONAS = [
  { ...WIN_BASE, label: "Win10-1366x768-IntelHD",       screen: { width: 1366, height: 768,  dpr: 1.0 }, hardwareConcurrency: 4,  deviceMemory: 8,  webGl: WIN_GPU_INTEL_HD },
  { ...WIN_BASE, label: "Win10-1920x1080-IntelUHD",     screen: { width: 1920, height: 1080, dpr: 1.0 }, hardwareConcurrency: 8,  deviceMemory: 8,  webGl: WIN_GPU_INTEL_UHD },
  { ...WIN_BASE, label: "Win11-1920x1080-IrisXe",       screen: { width: 1920, height: 1080, dpr: 1.25 },hardwareConcurrency: 12, deviceMemory: 16, webGl: WIN_GPU_INTEL_IRIS },
  { ...WIN_BASE, label: "Win11-1920x1200-IntelUHD",     screen: { width: 1920, height: 1200, dpr: 1.0 }, hardwareConcurrency: 8,  deviceMemory: 16, webGl: WIN_GPU_INTEL_UHD },
  { ...WIN_BASE, label: "Win11-2560x1440-NVIDIA-3060",  screen: { width: 2560, height: 1440, dpr: 1.0 }, hardwareConcurrency: 12, deviceMemory: 16, webGl: WIN_GPU_NVIDIA_3060 },
  { ...WIN_BASE, label: "Win11-2560x1440-NVIDIA-3070",  screen: { width: 2560, height: 1440, dpr: 1.0 }, hardwareConcurrency: 16, deviceMemory: 32, webGl: WIN_GPU_NVIDIA_3070 },
  { ...WIN_BASE, label: "Win11-1920x1080-AMD-RX580",    screen: { width: 1920, height: 1080, dpr: 1.0 }, hardwareConcurrency: 8,  deviceMemory: 16, webGl: WIN_GPU_AMD_RX580 },
  { ...WIN_BASE, label: "Win11-3840x2160-NVIDIA-3070",  screen: { width: 3840, height: 2160, dpr: 1.5 }, hardwareConcurrency: 16, deviceMemory: 32, webGl: WIN_GPU_NVIDIA_3070 },
];

const LIN_GPU_INTEL =  { vendor: "Mesa",                renderer: "Mesa Intel(R) UHD Graphics 620 (KBL GT2)" };
const LIN_GPU_INTEL2 = { vendor: "Mesa",                renderer: "Mesa Intel(R) Iris(R) Plus Graphics (ICL GT2)" };
const LIN_GPU_AMD =    { vendor: "Mesa",                renderer: "AMD Radeon Graphics (radeonsi, raphael_mendocino, LLVM 17.0.6, DRM 3.57, 6.8.0)" };
const LIN_GPU_AMD2 =   { vendor: "Mesa",                renderer: "AMD Radeon RX 6700 XT (radeonsi, navi22, LLVM 17.0.6, DRM 3.57, 6.8.0)" };
const LIN_GPU_NVIDIA = { vendor: "NVIDIA Corporation",  renderer: "NVIDIA GeForce RTX 3060/PCIe/SSE2" };

const LINUX_PERSONAS = [
  { ...LIN_BASE, label: "Linux-1366x768-Intel",  screen: { width: 1366, height: 768,  dpr: 1.0 }, hardwareConcurrency: 4,  deviceMemory: 8,  webGl: LIN_GPU_INTEL },
  { ...LIN_BASE, label: "Linux-1440x900-AMD",    screen: { width: 1440, height: 900,  dpr: 1.0 }, hardwareConcurrency: 12, deviceMemory: 16, webGl: LIN_GPU_AMD },
  { ...LIN_BASE, label: "Linux-1680x1050-Intel", screen: { width: 1680, height: 1050, dpr: 1.0 }, hardwareConcurrency: 8,  deviceMemory: 16, webGl: LIN_GPU_INTEL2 },
  { ...LIN_BASE, label: "Linux-1920x1080-IntelU",screen: { width: 1920, height: 1080, dpr: 1.0 }, hardwareConcurrency: 8,  deviceMemory: 16, webGl: LIN_GPU_INTEL },
  { ...LIN_BASE, label: "Linux-1920x1080-AMD",   screen: { width: 1920, height: 1080, dpr: 1.0 }, hardwareConcurrency: 16, deviceMemory: 32, webGl: LIN_GPU_AMD2 },
  { ...LIN_BASE, label: "Linux-2560x1440-NVIDIA",screen: { width: 2560, height: 1440, dpr: 1.0 }, hardwareConcurrency: 16, deviceMemory: 32, webGl: LIN_GPU_NVIDIA },
  { ...LIN_BASE, label: "Linux-2560x1600-Intel", screen: { width: 2560, height: 1600, dpr: 1.0 }, hardwareConcurrency: 12, deviceMemory: 32, webGl: LIN_GPU_INTEL2 },
  { ...LIN_BASE, label: "Linux-3840x2160-NVIDIA",screen: { width: 3840, height: 2160, dpr: 1.5 }, hardwareConcurrency: 16, deviceMemory: 64, webGl: LIN_GPU_NVIDIA },
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

export function fillPersonaKeys(seedB64) {
  const hostOS = detectHostOS();
  const p = pickPersona(seedB64, hostOS);
  const decor = decorFor(hostOS);
  const ua = `Mozilla/5.0 (${p.uaSuffix}; rv:${FIREFOX_VERSION}) Gecko/20100101 Firefox/${FIREFOX_VERSION}`;

  // Coherent screen / window dimensions: derived from one source
  // (persona's screen.width × screen.height) so window.innerWidth /
  // outerWidth / screen.width / availWidth all line up. fpscanner-
  // style consistency checks pass.
  const sw = p.screen.width;
  const sh = p.screen.height;
  const dpr = p.screen.dpr;
  const availTop = decor.menuBar;             // 25 on macOS, 0 elsewhere
  const availHeight = sh - decor.menuBar - decor.taskbar;
  const innerHeight = availHeight - decor.firefoxChrome;
  const outerHeight = availHeight;            // browser maxed within avail area

  const keys = {
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

    // ── Hardware identity ─────────────────────────────────────────
    // navigator.hardwareConcurrency hook lives in patches/navigator-
    // spoofing.patch (MaskConfig::GetUint64). Without this key the
    // hooked function falls through to the real OS core count —
    // persona-vs-host mismatch (Windows persona reporting 12 cores
    // from host's Mac) catches us on consistency probes.
    "navigator.hardwareConcurrency": p.hardwareConcurrency,
    // maxTouchPoints: 0 = no touch input. Desktop personas always.
    "navigator:maxTouchPoints": 0,

    // ── screen + window (coherent set) ────────────────────────────
    // All dimensions derived from persona.screen.width × .height so
    // screen.width === window.outerWidth, screen.availWidth ≥
    // window.innerWidth, etc. Required for fpscanner / sannysoft and
    // generally any site that does dimension-consistency checks.
    "screen.width": sw,
    "screen.height": sh,
    "screen.availLeft": 0,
    "screen.availTop": availTop,
    "screen.availWidth": sw,
    "screen.availHeight": availHeight,
    "window.innerWidth": sw,
    "window.innerHeight": innerHeight,
    "window.outerWidth": sw,
    "window.outerHeight": outerHeight,
    "window.devicePixelRatio": dpr,
    "window.screenX": 0,
    "window.screenY": 0,
    "window.scrollMinX": 0,
    "window.scrollMinY": 0,
    "screen.pageXOffset": 0,
    "screen.pageYOffset": 0,
    "screen:orientation:type": "landscape-primary",
    "mediaFeature:resolution": dpr,

    // ── WebGL ─────────────────────────────────────────────────────
    "webGl:vendor": p.webGl.vendor,
    "webGl:renderer": p.webGl.renderer,

    // ── Audio ─────────────────────────────────────────────────────
    "AudioContext:outputLatency": p.audioOutputLatency,
    "AudioContext:sampleRate": 48000,
    "AudioContext:maxChannelCount": 2,

    // ── Spoof flags (bool=true means C++ patch substitutes) ──────
    "codecs:spoof": true,
    "mediaCapabilities:spoof": true,
    "permissions:spoof": true,
    "voices:fakeCompletion": true,
    "voices:fakeCompletion:charsPerSecond": 16,
    "voices:blockIfNotDefined": false,

    // ── Always-safe disable flags ────────────────────────────────
    "navigator:vibrate:disabled": true,
    "navigator:webgpu:disabled": true,
    "document:lastModified:hidden": true,
    "indexedDB:databases:hidden": true,

    // ── Media features (avoid OS-theme leak) ─────────────────────
    "mediaFeature:invertedColors": false,
    "mediaFeature:prefersReducedMotion": false,
    "mediaFeature:prefersReducedTransparency": false,
  };

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
  // Pref name uses _disabled for consistency, but underlying key is
  // mediaDevices:enabled (set false to disable).
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
