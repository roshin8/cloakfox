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
  if (settings.fonts?.enumeration !== 'off') {
    const rng = subPRNG(masterSeed, 'core.fonts');
    // Generate a deterministic font list from common fonts
    const allFonts = [
      'Arial', 'Arial Black', 'Comic Sans MS', 'Courier New', 'Georgia',
      'Impact', 'Lucida Console', 'Lucida Sans Unicode', 'Palatino Linotype',
      'Tahoma', 'Times New Roman', 'Trebuchet MS', 'Verdana', 'Segoe UI',
      'Helvetica Neue', 'Helvetica', 'Calibri', 'Cambria', 'Consolas',
      'Garamond', 'Futura', 'Gill Sans', 'Optima', 'Book Antiqua',
    ];
    // Shuffle and take a subset
    const shuffled = [...allFonts];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = rng.nextInt(0, i);
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    const count = rng.nextInt(12, 20);
    const fontList = shuffled.slice(0, count).join(',');
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
