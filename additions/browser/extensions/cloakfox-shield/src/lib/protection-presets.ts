/**
 * Protection Level Presets
 *
 * Level 0: Off - all spoofers disabled
 * Level 1: Minimal - headers only, basic navigator
 * Level 2: Balanced - noise on ALL signals (recommended)
 * Level 3: Strict - block sensitive APIs, noise everything else
 */

import type { SpooferSettings, ProtectionLevel } from '@/types/settings';

function allNoise(): SpooferSettings {
  return {
    graphics: { canvas: 'noise', offscreenCanvas: 'noise', webgl: 'noise', webgl2: 'noise', webglShaders: 'noise', webgpu: 'noise', svg: 'noise', domRect: 'noise', textMetrics: 'noise' },
    audio: { audioContext: 'noise', offlineAudio: 'noise', latency: 'noise', codecs: 'noise' },
    hardware: { screen: 'noise', screenFrame: 'noise', screenExtended: 'noise', orientation: 'noise', deviceMemory: 'noise', hardwareConcurrency: 'noise', mediaDevices: 'noise', battery: 'noise', gpu: 'noise', touch: 'noise', sensors: 'noise', architecture: 'noise', visualViewport: 'noise' },
    navigator: { userAgent: 'noise', languages: 'noise', plugins: 'noise', clientHints: 'noise', clipboard: 'noise', vibration: 'noise', vendorFlavors: 'noise', fontPreferences: 'noise', windowName: 'noise', tabHistory: 'noise', mediaCapabilities: 'noise' },
    timezone: { intl: 'noise', date: 'noise' },
    fonts: { enumeration: 'noise', cssDetection: 'noise' },
    network: { webrtc: 'public_only', connection: 'noise', geolocation: 'noise', websocket: 'noise' },
    timing: { performance: 'noise', memory: 'noise', eventLoop: 'noise' },
    css: { mediaQueries: 'noise' },
    speech: { synthesis: 'noise' },
    permissions: { query: 'noise', notification: 'noise' },
    storage: { estimate: 'noise', indexedDB: 'noise', webSQL: 'noise', privateModeProtection: 'noise' },
    math: { functions: 'noise' },
    keyboard: { layout: 'noise', cadence: 'noise' },
    workers: { fingerprint: 'noise', serviceWorker: 'noise' },
    errors: { stackTrace: 'noise' },
    rendering: { emoji: 'noise', mathml: 'noise' },
    intl: { apis: 'noise' },
    crypto: { webCrypto: 'noise' },
    devices: { gamepad: 'noise', midi: 'noise', bluetooth: 'noise', usb: 'noise', serial: 'noise', hid: 'noise' },
    features: { detection: 'noise' },
    payment: { applePay: 'noise' },
  };
}

function allOff(): SpooferSettings {
  const n = allNoise();
  const off: any = {};
  for (const [cat, vals] of Object.entries(n)) {
    off[cat] = {};
    for (const key of Object.keys(vals as any)) {
      off[cat][key] = 'off';
    }
  }
  return off as SpooferSettings;
}

// Level 0: Everything off
const LEVEL_0: SpooferSettings = allOff();

// Level 1: Only headers + basic navigator spoofing
const LEVEL_1: SpooferSettings = {
  ...allOff(),
  navigator: { ...allOff().navigator, userAgent: 'noise', languages: 'noise' },
  features: { detection: 'noise' },
};

// Level 2: Noise on ALL signals - nothing blocked, everything spoofed
const LEVEL_2: SpooferSettings = allNoise();

// Level 3: Strict - noise everything + block sensitive APIs
const LEVEL_3: SpooferSettings = {
  ...allNoise(),
  hardware: { ...allNoise().hardware, battery: 'block', sensors: 'block' },
  navigator: { ...allNoise().navigator, clipboard: 'block', windowName: 'block' },
  network: { webrtc: 'block', connection: 'noise', geolocation: 'block', websocket: 'block' },
  storage: { estimate: 'noise', indexedDB: 'noise', webSQL: 'block', privateModeProtection: 'block' },
  devices: { gamepad: 'block', midi: 'block', bluetooth: 'block', usb: 'block', serial: 'block', hid: 'block' },
  payment: { applePay: 'block' },
};

export const PROTECTION_PRESETS: Record<ProtectionLevel, SpooferSettings> = {
  0: LEVEL_0,
  1: LEVEL_1,
  2: LEVEL_2,
  3: LEVEL_3,
};

export const PROTECTION_DESCRIPTIONS: Record<ProtectionLevel, string> = {
  0: 'No protection - real fingerprint exposed',
  1: 'Minimal - headers and user agent only',
  2: 'Balanced - noise on all signals (recommended)',
  3: 'Strict - blocks sensitive APIs, may break some sites',
};
