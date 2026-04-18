/**
 * Core Bridge — calls C++ engine window.setXxx() methods when available.
 *
 * These are self-destructing WebIDL methods exposed by Cloakfox's C++ patches.
 * Each method stores its value in RoverfoxStorageManager (per-container IPC),
 * then deletes itself from the window object.
 *
 * Returns true if C++ handled the signal, false if JS fallback is needed.
 */

import { PRNG, base64ToUint8Array } from '@/lib/crypto';
import type { AssignedProfileData } from '@/types';

const win = window as Record<string, unknown>;

/** Try calling a C++ method. Returns true if it existed and was called. */
function callCore(method: string, ...args: unknown[]): boolean {
  const fn = win[method];
  if (typeof fn === 'function') {
    try {
      (fn as Function)(...args);
      return true;
    } catch (e) {
      console.warn(`[Cloakfox Core] ${method} failed:`, e);
      return false;
    }
  }
  return false;
}

/**
 * Create an isolated sub-PRNG for a specific signal.
 * This ensures each signal's randomness is independent —
 * one signal's behavior cannot affect another's output.
 */
function subPRNG(masterSeed: Uint8Array, signal: string): PRNG {
  const signalBytes = new TextEncoder().encode(signal);
  const combined = new Uint8Array(masterSeed.length + signalBytes.length);
  combined.set(masterSeed);
  combined.set(signalBytes, masterSeed.length);
  // XOR-fold into 32 bytes
  const folded = new Uint8Array(32);
  for (let i = 0; i < combined.length; i++) {
    folded[i % 32] ^= combined[i];
  }
  return new PRNG(folded);
}

/**
 * Apply all available C++ Core protections.
 * Returns a set of signal keys that were handled by Core (skip JS for these).
 *
 * Each signal uses its own isolated sub-PRNG derived from the master seed,
 * so signals are decoupled — one signal's PRNG usage can't affect another's.
 */
export function applyCoreProtections(
  masterSeed: Uint8Array,
  profile: AssignedProfileData | undefined,
  settings: Record<string, Record<string, string>>
): Set<string> {
  const handled = new Set<string>();

  // ─── Batched MaskConfig keys (via setCloakConfig) ─────────────
  // For signals without dedicated WebIDL setters — one call sets many keys.
  // Must run FIRST so individual Manager setters (below) can merge into it.
  const cloakConfig: Record<string, unknown> = {};
  if (settings.navigator?.vibration === 'block') {
    cloakConfig['navigator:vibrate:disabled'] = true;
  }
  if (settings.navigator?.clipboard === 'block') {
    cloakConfig['navigator:clipboard:disabled'] = true;
  }
  if (settings.navigator?.windowName !== 'off') {
    cloakConfig['window:name:disabled'] = true;
  }
  if (settings.permissions?.notification === 'block') {
    cloakConfig['notification:permission:disabled'] = true;
  }
  if (settings.storage?.estimate !== 'off') {
    // Fixed ~50GB quota — matches what a typical desktop reports.
    cloakConfig['storage:quota'] = 53687091200;
    cloakConfig['storage:usage'] = 0;
    cloakConfig['storage:persisted:disabled'] = true;
  }
  if (settings.devices?.gamepad === 'block') {
    cloakConfig['navigator:gamepads:disabled'] = true;
  }
  if (settings.devices?.midi === 'block') {
    cloakConfig['navigator:midi:disabled'] = true;
  }
  if (settings.graphics?.webgpu === 'block') {
    cloakConfig['navigator:webgpu:disabled'] = true;
  }
  if (settings.hardware?.touch !== 'off' && profile?.userAgent) {
    // Pick deterministic maxTouchPoints based on platform mobile flag.
    const mobile = (profile.userAgent as unknown as { mobile?: boolean }).mobile;
    cloakConfig['navigator:maxTouchPoints'] = mobile ? 5 : 0;
  }
  // Always hide webdriver unless explicitly set — automation indicator is high FP signal.
  cloakConfig['navigator:webdriver'] = false;
  if (settings.permissions?.query !== 'off') {
    cloakConfig['permissions:spoof'] = true;
  }
  if (settings.storage?.indexedDB === 'block') {
    cloakConfig['indexedDB:databases:hidden'] = true;
  }
  if (settings.hardware?.orientation !== 'off' && profile?.userAgent) {
    const mobile = (profile.userAgent as unknown as { mobile?: boolean }).mobile;
    cloakConfig['screen:orientation:type'] = mobile ? 'portrait-primary' : 'landscape-primary';
  }
  if (settings.hardware?.visualViewport !== 'off') {
    cloakConfig['window:visualViewport:spoof'] = true;
  }
  if (settings.timing?.eventLoop !== 'off') {
    // Per-page deterministic jitter (0-2ms) seeded by the page PRNG.
    cloakConfig['timing:setTimeoutJitter'] = 2;
    cloakConfig['timing:setTimeoutSeed'] = Math.floor(Math.random() * 0xFFFFFFFF) >>> 0;
  }
  if (settings.graphics?.textMetrics !== 'off') {
    // canvas:seed is set via setCanvasSeed (individual method). We just need to
    // mark this as handled so the JS spoofer gates off.
  }
  if (settings.navigator?.mediaCapabilities !== 'off') {
    cloakConfig['mediaCapabilities:spoof'] = true;
  }
  if (settings.audio?.codecs !== 'off') {
    cloakConfig['codecs:spoof'] = true;
  }
  if (settings.network?.websocket === 'block') {
    cloakConfig['webSocket:disabled'] = true;
  }
  // DRM / EME: L1 vs L3 Widevine levels are a strong identity signal.
  // Disable by default for privacy; users can enable per-site if they
  // need Netflix / Spotify etc.
  cloakConfig['navigator:eme:disabled'] = true;
  // Hide document.lastModified fallback to current time (date leak).
  cloakConfig['document:lastModified:hidden'] = true;
  if (Object.keys(cloakConfig).length > 0) {
    if (callCore('setCloakConfig', JSON.stringify(cloakConfig))) {
      if ('navigator:vibrate:disabled' in cloakConfig) handled.add('navigator.vibration');
      if ('navigator:clipboard:disabled' in cloakConfig) handled.add('navigator.clipboard');
      if ('window:name:disabled' in cloakConfig) handled.add('navigator.windowName');
      if ('notification:permission:disabled' in cloakConfig) handled.add('permissions.notification');
      if ('storage:quota' in cloakConfig) {
        handled.add('storage.estimate');
        handled.add('storage.privateModeProtection');
      }
      if ('navigator:gamepads:disabled' in cloakConfig) handled.add('devices.gamepad');
      if ('navigator:midi:disabled' in cloakConfig) handled.add('devices.midi');
      if ('navigator:webgpu:disabled' in cloakConfig) handled.add('graphics.webgpu');
      if ('navigator:maxTouchPoints' in cloakConfig) handled.add('hardware.touch');
      if ('navigator:webdriver' in cloakConfig) handled.add('navigator.webdriver');
      if ('permissions:spoof' in cloakConfig) handled.add('permissions.query');
      if ('indexedDB:databases:hidden' in cloakConfig) handled.add('storage.indexedDB');
      if ('screen:orientation:type' in cloakConfig) handled.add('hardware.orientation');
      if ('window:visualViewport:spoof' in cloakConfig) handled.add('hardware.visualViewport');
      if ('timing:setTimeoutJitter' in cloakConfig) handled.add('timing.eventLoop');
      if ('mediaCapabilities:spoof' in cloakConfig) handled.add('navigator.mediaCapabilities');
      if ('codecs:spoof' in cloakConfig) handled.add('audio.codecs');
      if ('webSocket:disabled' in cloakConfig) handled.add('network.websocket');
    }
  }
  // Text metrics, DOMRect, SVG text length, emoji canvas measurements and
  // MathML bbox all ride on the canvas:seed set by setCanvasSeed. Mark them
  // handled whenever the core canvas manager was engaged.
  if (handled.has('graphics.canvas')) {
    handled.add('graphics.textMetrics');
    handled.add('graphics.domrect');
    handled.add('graphics.svg');
    handled.add('rendering.emoji');
    handled.add('rendering.mathml');
  }
  // feature-detection.ts mostly wraps vectors we already cover in C++
  // (navigator.webdriver is always spoofed; navigator.globalPrivacyControl
  // is covered by Camoufox; pdfViewerEnabled/javaEnabled/cookieEnabled are
  // either controlled by Firefox prefs or already return safe values).
  if ('navigator:webdriver' in cloakConfig) handled.add('features.detection');

  // ─── Canvas ──────────────────────────────────────────────────
  if (settings.graphics?.canvas !== 'off') {
    const rng = subPRNG(masterSeed, 'core.canvas');
    const seed = rng.nextInt(1, 2147483647);
    if (callCore('setCanvasSeed', seed)) {
      handled.add('graphics.canvas');
      handled.add('graphics.offscreenCanvas'); // Same C++ seed covers both
    }
  }

  // ─── Audio ───────────────────────────────────────────────────
  if (settings.audio?.audioContext !== 'off') {
    const rng = subPRNG(masterSeed, 'core.audio');
    const seed = rng.nextInt(1, 2147483647);
    if (callCore('setAudioFingerprintSeed', seed)) {
      handled.add('audio.audioContext');
      handled.add('audio.offlineAudio');
      handled.add('audio.latency'); // Same C++ manager
    }
  }

  // ─── Navigator ───────────────────────────────────────────────
  // Call all three independently — don't let one failure affect others
  if (settings.navigator?.userAgent !== 'off' && profile?.userAgent) {
    const ua = profile.userAgent;
    const uaOk = callCore('setNavigatorUserAgent', ua.userAgent || '');
    const platOk = callCore('setNavigatorPlatform', ua.platform || '');
    const oscpuOk = callCore('setNavigatorOscpu', ua.oscpu || '');
    // Only mark as handled if ALL succeeded — partial state is dangerous
    if (uaOk && platOk && oscpuOk) {
      handled.add('navigator.userAgent');
    } else if (uaOk || platOk || oscpuOk) {
      // Partial failure: some C++ methods fired but not all.
      // Log warning — JS fallback will run but may conflict with the C++ values that did set.
      console.warn('[Cloakfox Core] Partial navigator failure — some C++ methods set, JS fallback may conflict');
    }
  }

  if (settings.hardware?.hardwareConcurrency !== 'off' && profile) {
    const cores = profile.hardwareConcurrency || 8;
    if (callCore('setNavigatorHardwareConcurrency', cores)) {
      handled.add('hardware.hardwareConcurrency');
    }
  }

  // ─── Screen ──────────────────────────────────────────────────
  if (settings.hardware?.screen !== 'off' && profile?.screen) {
    const s = profile.screen;
    const dimOk = callCore('setScreenDimensions', s.width, s.height);
    const depthOk = callCore('setScreenColorDepth', s.colorDepth || 24);
    if (dimOk) {
      handled.add('hardware.screen');
      handled.add('hardware.screenFrame'); // C++ dimensions cover frame too
      handled.add('hardware.screenExtended');
      handled.add('hardware.orientation');
    }
    if (depthOk && dimOk) {
      // Both set — fully handled
    } else if (dimOk || depthOk) {
      console.warn('[Cloakfox Core] Partial screen failure');
    }
  }

  // ─── Fonts ───────────────────────────────────────────────────
  if (settings.fonts?.enumeration !== 'off' && profile?.userAgent) {
    const rng = subPRNG(masterSeed, 'core.fonts');
    const fontList = generateOSFontSubset(rng, profile.userAgent.platformName || '');
    if (callCore('setFontList', fontList)) {
      handled.add('fonts.enumeration');
    }
  }

  if (settings.fonts?.cssDetection !== 'off') {
    const rng = subPRNG(masterSeed, 'core.fontSpacing');
    const seed = rng.nextInt(1, 2147483647);
    if (callCore('setFontSpacingSeed', seed)) {
      handled.add('fonts.cssDetection');
    }
  }

  // ─── WebGL ───────────────────────────────────────────────────
  // Use profile-consistent GPU — must match the spoofed platform
  if (settings.graphics?.webgl !== 'off' && profile?.userAgent) {
    const rng = subPRNG(masterSeed, 'core.webgl');
    const gpu = pickPlatformGPU(rng, profile.userAgent.platformName || '');
    const vendorOk = callCore('setWebGLVendor', gpu.vendor);
    const rendererOk = callCore('setWebGLRenderer', gpu.renderer);
    if (vendorOk && rendererOk) {
      handled.add('graphics.webgl');
      handled.add('graphics.webgl2');
      handled.add('graphics.webglShaders'); // C++ covers shader precision too
    } else if (vendorOk || rendererOk) {
      console.warn('[Cloakfox Core] Partial WebGL failure');
    }
  }

  // ─── Battery ─────────────────────────────────────────────────
  if (settings.hardware?.battery !== 'off') {
    const rng = subPRNG(masterSeed, 'core.battery');
    // Generate realistic battery: usually charging, level 0.20-1.00
    const charging = rng.nextInt(0, 3) !== 0; // 75% chance charging
    const level = rng.nextInt(20, 100) / 100;
    if (callCore('setBatteryStatus', charging, level)) {
      handled.add('hardware.battery');
    }
  }

  // ─── Media Devices ─────────────────────────────────────────
  if (settings.hardware?.mediaDevices !== 'off') {
    const rng = subPRNG(masterSeed, 'core.mediaDevices');
    // Realistic device counts: 1-3 mics, 1-2 cams, 1-3 speakers
    const mics = rng.nextInt(1, 3);
    const cams = rng.nextInt(1, 2);
    const speakers = rng.nextInt(1, 3);
    if (callCore('setMediaDeviceCounts', mics, cams, speakers)) {
      handled.add('hardware.mediaDevices');
    }
  }

  // ─── History Length ─────────────────────────────────────────
  if (settings.navigator?.tabHistory !== 'off') {
    const rng = subPRNG(masterSeed, 'core.history');
    const length = rng.nextInt(1, 8);
    if (callCore('setHistoryLength', length)) {
      handled.add('navigator.tabHistory');
    }
  }

  // ─── Geolocation ──────────────────────────────────────────
  if (settings.network?.geolocation !== 'off') {
    const rng = subPRNG(masterSeed, 'core.geolocation');
    // Generate a plausible location (major city coordinates)
    const cities = [
      { lat: 40.7128, lon: -74.0060 },  // New York
      { lat: 51.5074, lon: -0.1278 },   // London
      { lat: 48.8566, lon: 2.3522 },    // Paris
      { lat: 35.6762, lon: 139.6503 },  // Tokyo
      { lat: 37.7749, lon: -122.4194 }, // San Francisco
      { lat: 52.5200, lon: 13.4050 },   // Berlin
      { lat: 55.7558, lon: 37.6173 },   // Moscow
      { lat: -33.8688, lon: 151.2093 }, // Sydney
    ];
    const city = cities[rng.nextInt(0, cities.length - 1)];
    // Add small random offset (within ~5km)
    const lat = city.lat + (rng.nextInt(-50, 50) / 1000);
    const lon = city.lon + (rng.nextInt(-50, 50) / 1000);
    const accuracy = rng.nextInt(10, 100);
    if (callCore('setGeolocation', lat, lon, accuracy)) {
      handled.add('network.geolocation');
    }
  }

  // ─── WebRTC ──────────────────────────────────────────────────
  if (settings.network?.webrtc !== 'off') {
    const rng = subPRNG(masterSeed, 'core.webrtc');
    const a = rng.nextInt(1, 254);
    const b = rng.nextInt(1, 254);
    const ipv4 = `192.168.${a}.${b}`;
    const seg = () => rng.nextInt(0, 65535).toString(16).padStart(4, '0');
    const ipv6 = `fd00:${seg()}:${seg()}::${seg()}`;
    const v4ok = callCore('setWebRTCIPv4', ipv4);
    const v6ok = callCore('setWebRTCIPv6', ipv6);
    if (v4ok || v6ok) handled.add('network.webrtc');
  }

  // ─── Timezone ────────────────────────────────────────────────
  // Use profile-consistent timezone matching the spoofed locale
  if (settings.timezone?.intl !== 'off' && profile) {
    const tz = pickTimezoneForProfile(profile, subPRNG(masterSeed, 'core.timezone'));
    if (callCore('setTimezone', tz)) {
      handled.add('timezone.intl');
      handled.add('timezone.date');
    }
  }

  // ─── Speech ──────────────────────────────────────────────────
  // Use platform-appropriate voices
  if (settings.speech?.synthesis !== 'off' && profile?.userAgent) {
    const voices = pickVoicesForPlatform(profile.userAgent.platformName || '');
    if (callCore('setSpeechVoices', voices)) {
      handled.add('speech.synthesis');
    }
  }

  return handled;
}

// ─── Platform-consistent data generators ───────────────────────

interface GPUProfile { vendor: string; renderer: string }

function pickPlatformGPU(rng: PRNG, platform: string): GPUProfile {
  const gpus: GPUProfile[] = platform.includes('Mac') || platform === 'macOS' ? [
    { vendor: 'Google Inc. (Apple)', renderer: 'ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)' },
    { vendor: 'Google Inc. (Apple)', renderer: 'ANGLE (Apple, ANGLE Metal Renderer: Apple M2, Unspecified Version)' },
    { vendor: 'Google Inc. (Apple)', renderer: 'ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Pro, Unspecified Version)' },
    { vendor: 'Google Inc. (Apple)', renderer: 'ANGLE (Apple, ANGLE Metal Renderer: Apple M3, Unspecified Version)' },
    { vendor: 'Google Inc. (Intel)', renderer: 'ANGLE (Intel Inc., Intel(R) Iris(TM) Plus Graphics, OpenGL 4.1)' },
  ] : platform.includes('Linux') ? [
    { vendor: 'Mesa', renderer: 'Mesa Intel(R) UHD Graphics 630 (CFL GT2)' },
    { vendor: 'Mesa', renderer: 'Mesa Intel(R) Xe Graphics (TGL GT2)' },
    { vendor: 'X.Org', renderer: 'AMD Radeon RX 580 (polaris10, LLVM 15.0.7, DRM 3.49, 6.1.0)' },
    { vendor: 'X.Org', renderer: 'AMD Radeon RX 6700 XT (navi22, LLVM 16.0.6, DRM 3.52, 6.5.0)' },
  ] : [ // Windows
    { vendor: 'Google Inc. (NVIDIA)', renderer: 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)' },
    { vendor: 'Google Inc. (NVIDIA)', renderer: 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0, D3D11)' },
    { vendor: 'Google Inc. (NVIDIA)', renderer: 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0, D3D11)' },
    { vendor: 'Google Inc. (AMD)', renderer: 'ANGLE (AMD, AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0, D3D11)' },
    { vendor: 'Google Inc. (Intel)', renderer: 'ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)' },
    { vendor: 'Google Inc. (Intel)', renderer: 'ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)' },
  ];
  return gpus[rng.nextInt(0, gpus.length - 1)];
}

function pickTimezoneForProfile(profile: AssignedProfileData, rng: PRNG): string {
  // Match timezone to language when possible
  const lang = profile.languages?.[0] || 'en-US';
  const langTzMap: Record<string, string[]> = {
    'en-US': ['America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles'],
    'en-GB': ['Europe/London'],
    'de-DE': ['Europe/Berlin'],
    'de': ['Europe/Berlin'],
    'fr-FR': ['Europe/Paris'],
    'fr': ['Europe/Paris'],
    'ja-JP': ['Asia/Tokyo'],
    'ja': ['Asia/Tokyo'],
    'zh-CN': ['Asia/Shanghai'],
    'zh': ['Asia/Shanghai'],
    'ko-KR': ['Asia/Seoul'],
    'ko': ['Asia/Seoul'],
    'es-ES': ['Europe/Madrid'],
    'es': ['America/Mexico_City', 'Europe/Madrid'],
    'pt-BR': ['America/Sao_Paulo'],
    'pt': ['Europe/Lisbon', 'America/Sao_Paulo'],
    'ru-RU': ['Europe/Moscow'],
    'ru': ['Europe/Moscow'],
    'it-IT': ['Europe/Rome'],
    'it': ['Europe/Rome'],
    'nl-NL': ['Europe/Amsterdam'],
    'ar-SA': ['Asia/Riyadh'],
    'hi-IN': ['Asia/Kolkata'],
    'th-TH': ['Asia/Bangkok'],
  };

  const candidates = langTzMap[lang] || langTzMap[lang.split('-')[0]] || [
    'America/New_York', 'America/Chicago', 'America/Los_Angeles',
    'Europe/London', 'Europe/Paris', 'Europe/Berlin',
    'Asia/Tokyo', 'Asia/Shanghai', 'Australia/Sydney',
  ];
  return candidates[rng.nextInt(0, candidates.length - 1)];
}

/**
 * Generate an OS-appropriate font subset (30-78% of available fonts).
 * Always includes OS marker fonts that fingerprinting scripts check for.
 * Matches Camoufox's approach: random subset per context, OS markers always present.
 */
function generateOSFontSubset(rng: PRNG, platform: string): string {
  const isMac = platform.includes('Mac') || platform === 'macOS';
  const isLinux = platform.includes('Linux');

  // OS marker fonts — ALWAYS included (fingerprinters check for these)
  const markers = isMac ? [
    'Helvetica Neue', 'Helvetica', 'SF Pro Text', 'SF Pro Display',
    'Menlo', 'Monaco', 'Lucida Grande', 'Apple Color Emoji',
  ] : isLinux ? [
    'Liberation Sans', 'Liberation Serif', 'Liberation Mono',
    'DejaVu Sans', 'DejaVu Serif', 'DejaVu Sans Mono', 'Noto Sans',
  ] : [ // Windows
    'Segoe UI', 'Segoe UI Emoji', 'Calibri', 'Consolas',
    'Cambria', 'Tahoma', 'Verdana', 'Microsoft YaHei',
  ];

  // Common cross-platform fonts
  const common = [
    'Arial', 'Arial Black', 'Comic Sans MS', 'Courier New', 'Georgia',
    'Impact', 'Times New Roman', 'Trebuchet MS',
  ];

  // OS-specific additional fonts
  const osExtra = isMac ? [
    'Avenir', 'Avenir Next', 'Futura', 'Gill Sans', 'Optima',
    'Palatino', 'American Typewriter', 'Baskerville', 'Big Caslon',
    'Copperplate', 'Didot', 'Franklin Gothic Medium', 'Hoefler Text',
    'Iowan Old Style', 'Marion', 'Noteworthy', 'Phosphate',
    'Rockwell', 'Savoye LET', 'SignPainter', 'Snell Roundhand',
    'Apple Chancery', 'Chalkboard', 'Chalkboard SE', 'Chalkduster',
    'Cochin', 'Corsiva Hebrew', 'Damascus', 'Devanagari MT',
  ] : isLinux ? [
    'Ubuntu', 'Ubuntu Mono', 'Cantarell', 'Droid Sans', 'Droid Serif',
    'Fira Sans', 'Fira Mono', 'Noto Serif', 'Noto Mono',
    'Nimbus Sans', 'Nimbus Roman', 'FreeSans', 'FreeSerif',
    'Source Code Pro', 'Source Sans Pro', 'Bitstream Vera Sans',
  ] : [ // Windows
    'Palatino Linotype', 'Lucida Console', 'Lucida Sans Unicode',
    'Book Antiqua', 'Garamond', 'Century Gothic', 'Candara',
    'Corbel', 'Constantia', 'Franklin Gothic Medium',
    'Gill Sans MT', 'Gloucester MT Extra Condensed', 'Goudy Old Style',
    'Harrington', 'Lucida Bright', 'Lucida Fax', 'Magneto',
    'MS Gothic', 'MS PGothic', 'MS Mincho', 'MS PMincho',
    'Meiryo', 'Meiryo UI', 'Yu Gothic', 'Yu Mincho',
    'Malgun Gothic', 'Microsoft Sans Serif', 'Sylfaen',
  ];

  // Combine all available fonts for this OS
  const allFonts = [...common, ...osExtra];

  // Shuffle the non-marker fonts
  const shuffled = [...allFonts];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = rng.nextInt(0, i);
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }

  // Take 30-78% subset (matching Camoufox's range)
  const total = markers.length + shuffled.length;
  const minCount = Math.floor(total * 0.30);
  const maxCount = Math.floor(total * 0.78);
  const subsetSize = rng.nextInt(minCount, maxCount) - markers.length;
  const subset = shuffled.slice(0, Math.max(subsetSize, 4));

  // Markers always first, then shuffled subset
  const finalList = [...markers, ...subset];
  return finalList.join(',');
}

function pickVoicesForPlatform(platform: string): string {
  if (platform.includes('Mac') || platform === 'macOS') {
    return 'Samantha,Alex,Victoria,Daniel,Karen,Moira,Tessa';
  } else if (platform.includes('Linux')) {
    return 'English (America)+anika,English (Great Britain)+female1,English (America)+male1';
  } else {
    // Windows
    return 'Microsoft David,Microsoft Zira,Microsoft Mark,Microsoft Hazel';
  }
}
