/**
 * Signal Options - Static data for fingerprint signal configuration UI.
 * Extracted from FingerprintTab to keep components focused.
 */

export const LANGUAGE_OPTIONS = [
  { id: 'en-US', name: 'English (US)', value: ['en-US', 'en'] },
  { id: 'en-GB', name: 'English (UK)', value: ['en-GB', 'en'] },
  { id: 'en-AU', name: 'English (Australia)', value: ['en-AU', 'en'] },
  { id: 'en-CA', name: 'English (Canada)', value: ['en-CA', 'en'] },
  { id: 'es-ES', name: 'Spanish (Spain)', value: ['es-ES', 'es'] },
  { id: 'es-MX', name: 'Spanish (Mexico)', value: ['es-MX', 'es'] },
  { id: 'fr-FR', name: 'French (France)', value: ['fr-FR', 'fr'] },
  { id: 'fr-CA', name: 'French (Canada)', value: ['fr-CA', 'fr'] },
  { id: 'de-DE', name: 'German (Germany)', value: ['de-DE', 'de'] },
  { id: 'it-IT', name: 'Italian', value: ['it-IT', 'it'] },
  { id: 'pt-BR', name: 'Portuguese (Brazil)', value: ['pt-BR', 'pt'] },
  { id: 'nl-NL', name: 'Dutch', value: ['nl-NL', 'nl'] },
  { id: 'pl-PL', name: 'Polish', value: ['pl-PL', 'pl'] },
  { id: 'ru-RU', name: 'Russian', value: ['ru-RU', 'ru'] },
  { id: 'ja-JP', name: 'Japanese', value: ['ja-JP', 'ja'] },
  { id: 'ko-KR', name: 'Korean', value: ['ko-KR', 'ko'] },
  { id: 'zh-CN', name: 'Chinese (Simplified)', value: ['zh-CN', 'zh'] },
  { id: 'zh-TW', name: 'Chinese (Traditional)', value: ['zh-TW', 'zh'] },
  { id: 'ar-SA', name: 'Arabic', value: ['ar-SA', 'ar'] },
  { id: 'hi-IN', name: 'Hindi', value: ['hi-IN', 'hi'] },
  { id: 'th-TH', name: 'Thai', value: ['th-TH', 'th'] },
  { id: 'vi-VN', name: 'Vietnamese', value: ['vi-VN', 'vi'] },
  { id: 'tr-TR', name: 'Turkish', value: ['tr-TR', 'tr'] },
  { id: 'sv-SE', name: 'Swedish', value: ['sv-SE', 'sv'] },
  { id: 'da-DK', name: 'Danish', value: ['da-DK', 'da'] },
  { id: 'fi-FI', name: 'Finnish', value: ['fi-FI', 'fi'] },
  { id: 'no-NO', name: 'Norwegian', value: ['no-NO', 'no'] },
];

export const TIMEZONE_OPTIONS = [
  // US timezones
  { id: 'US-HI', name: 'US - Hawaii (HST)', offset: 600 },
  { id: 'US-AK', name: 'US - Alaska (AKST)', offset: 540 },
  { id: 'US-PT', name: 'US - Pacific (Los Angeles)', offset: 480 },
  { id: 'US-MT', name: 'US - Mountain (Denver)', offset: 420 },
  { id: 'US-AZ', name: 'US - Arizona (no DST)', offset: 420 },
  { id: 'US-CT', name: 'US - Central (Chicago)', offset: 360 },
  { id: 'US-ET', name: 'US - Eastern (New York)', offset: 300 },
  // Americas
  { id: 'CA-AT', name: 'Canada - Atlantic (Halifax)', offset: 240 },
  { id: 'BR-SP', name: 'Brazil - Sao Paulo', offset: 180 },
  { id: 'MX-CT', name: 'Mexico - Mexico City', offset: 360 },
  // Europe
  { id: 'EU-UK', name: 'UK - London (GMT)', offset: 0 },
  { id: 'EU-CET', name: 'Europe - Paris/Berlin (CET)', offset: -60 },
  { id: 'EU-EET', name: 'Europe - Helsinki/Athens (EET)', offset: -120 },
  { id: 'EU-MSK', name: 'Russia - Moscow (MSK)', offset: -180 },
  { id: 'EU-IST', name: 'Turkey - Istanbul', offset: -180 },
  // Middle East / Africa
  { id: 'ME-DXB', name: 'UAE - Dubai (GST)', offset: -240 },
  { id: 'AF-CAI', name: 'Egypt - Cairo (EET)', offset: -120 },
  { id: 'ME-RUH', name: 'Saudi Arabia - Riyadh', offset: -180 },
  // South Asia
  { id: 'SA-KHI', name: 'Pakistan - Karachi (PKT)', offset: -300 },
  { id: 'SA-DEL', name: 'India - Mumbai/Delhi (IST)', offset: -330 },
  { id: 'SA-DAC', name: 'Bangladesh - Dhaka', offset: -360 },
  // Southeast Asia
  { id: 'SEA-BKK', name: 'Thailand - Bangkok (ICT)', offset: -420 },
  { id: 'SEA-SGP', name: 'Singapore / Hong Kong', offset: -480 },
  // East Asia
  { id: 'EA-SH', name: 'China - Shanghai/Beijing', offset: -480 },
  { id: 'EA-TYO', name: 'Japan - Tokyo (JST)', offset: -540 },
  { id: 'EA-SEL', name: 'Korea - Seoul (KST)', offset: -540 },
  // Oceania
  { id: 'OC-SYD', name: 'Australia - Sydney (AEST)', offset: -600 },
  { id: 'OC-AKL', name: 'New Zealand - Auckland', offset: -720 },
];

export const CPU_CORES = [1, 2, 4, 6, 8, 10, 12, 16, 24, 32, 64];
export const DEVICE_MEMORY = [0.5, 1, 2, 4, 8, 16, 32];

export const GPU_OPTIONS = [
  { id: 'gtx-1060', vendor: 'Google Inc. (NVIDIA)', renderer: 'ANGLE (NVIDIA GeForce GTX 1060 6GB Direct3D11 vs_5_0 ps_5_0)' },
  { id: 'gtx-1080', vendor: 'Google Inc. (NVIDIA)', renderer: 'ANGLE (NVIDIA GeForce GTX 1080 Direct3D11 vs_5_0 ps_5_0)' },
  { id: 'rtx-2060', vendor: 'Google Inc. (NVIDIA)', renderer: 'ANGLE (NVIDIA GeForce RTX 2060 Direct3D11 vs_5_0 ps_5_0)' },
  { id: 'rtx-3060', vendor: 'Google Inc. (NVIDIA)', renderer: 'ANGLE (NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)' },
  { id: 'rtx-3080', vendor: 'Google Inc. (NVIDIA)', renderer: 'ANGLE (NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0)' },
  { id: 'rtx-4070', vendor: 'Google Inc. (NVIDIA)', renderer: 'ANGLE (NVIDIA GeForce RTX 4070 Ti Direct3D11 vs_5_0 ps_5_0)' },
  { id: 'rtx-4090', vendor: 'Google Inc. (NVIDIA)', renderer: 'ANGLE (NVIDIA GeForce RTX 4090 Direct3D11 vs_5_0 ps_5_0)' },
  { id: 'rx-580', vendor: 'Google Inc. (AMD)', renderer: 'ANGLE (AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0)' },
  { id: 'rx-5700xt', vendor: 'Google Inc. (AMD)', renderer: 'ANGLE (AMD Radeon RX 5700 XT Direct3D11 vs_5_0 ps_5_0)' },
  { id: 'rx-6700xt', vendor: 'Google Inc. (AMD)', renderer: 'ANGLE (AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0)' },
  { id: 'rx-7900xtx', vendor: 'Google Inc. (AMD)', renderer: 'ANGLE (AMD Radeon RX 7900 XTX Direct3D11 vs_5_0 ps_5_0)' },
  { id: 'uhd-630', vendor: 'Google Inc. (Intel)', renderer: 'ANGLE (Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)' },
  { id: 'iris-xe', vendor: 'Google Inc. (Intel)', renderer: 'ANGLE (Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0)' },
  { id: 'apple-m1', vendor: 'Apple Inc.', renderer: 'Apple M1' },
  { id: 'apple-m2', vendor: 'Apple Inc.', renderer: 'Apple M2' },
  { id: 'apple-m3', vendor: 'Apple Inc.', renderer: 'Apple M3' },
  { id: 'apple-m3-pro', vendor: 'Apple Inc.', renderer: 'Apple M3 Pro' },
];

export const OS_FILTERS = ['all', 'windows', 'macos', 'linux', 'android', 'ios'] as const;

export const BROWSER_FILTERS = ['all', 'chrome', 'firefox', 'safari', 'edge', 'opera', 'brave', 'vivaldi', 'samsung'] as const;

export const WEBRTC_OPTIONS = [
  { id: 'off', name: 'Off' },
  { id: 'public_only', name: 'Spoof (public only)' },
  { id: 'block', name: 'Block' },
];

export const CANVAS_NOISE_OPTIONS = [
  { id: 'minimal', name: 'Minimal (±0.5)' },
  { id: 'low', name: 'Low (±1)' },
  { id: 'medium', name: 'Medium (±2)' },
  { id: 'high', name: 'High (±4)' },
  { id: 'extreme', name: 'Extreme (±16)' },
];

export const AUDIO_NOISE_OPTIONS = [
  { id: 'minimal', name: 'Minimal (±0.00001)' },
  { id: 'low', name: 'Low (±0.0001)' },
  { id: 'medium', name: 'Medium (±0.001)' },
  { id: 'high', name: 'High (±0.01)' },
];

export const TIMING_PRECISION_OPTIONS = [
  { id: '100', name: '100ms (low entropy)' },
  { id: '50', name: '50ms' },
  { id: '20', name: '20ms' },
  { id: '5', name: '5ms' },
  { id: '1', name: '1ms' },
  { id: '0.1', name: '0.1ms (high entropy)' },
];

export const BATTERY_OPTIONS = [
  { id: '100', name: '100% Full' },
  { id: '80', name: '80% Good' },
  { id: '60', name: '60% Moderate' },
  { id: '40', name: '40% Low' },
  { id: '20', name: '20% Very Low' },
  { id: 'charging', name: 'Charging' },
];

export const TOUCH_OPTIONS = [
  { id: '0', name: '0 (desktop)' },
  { id: '1', name: '1' },
  { id: '2', name: '2' },
  { id: '5', name: '5 (mobile)' },
  { id: '10', name: '10 (tablet)' },
];

export const DOMRECT_NOISE_OPTIONS = [
  { id: 'minimal', name: '±0.01px' },
  { id: 'low', name: '±0.05px' },
  { id: 'medium', name: '±0.1px' },
  { id: 'high', name: '±0.5px' },
  { id: 'very-high', name: '±1px' },
];

export const FONT_LIST_OPTIONS = [
  { id: 'minimal', name: '5 fonts' },
  { id: 'small', name: '10 fonts' },
  { id: 'medium', name: '25 fonts' },
  { id: 'large', name: '50 fonts' },
  { id: 'full', name: '100+ fonts' },
];

export const MEDIA_DEVICE_OPTIONS = [
  { id: '0-0', name: 'No devices' },
  { id: '1-1', name: '1 cam, 1 mic' },
  { id: '1-2', name: '1 cam, 2 mics' },
  { id: '2-1', name: '2 cams, 1 mic' },
  { id: '2-2', name: '2 cams, 2 mics' },
];


export const WEBSOCKET_OPTIONS = [
  { id: 'off', name: 'Off' },
  { id: 'noise', name: 'Spoof (block 3rd party)' },
  { id: 'block', name: 'Block' },
];

export const WEBGL_NOISE_OPTIONS = [
  { id: 'minimal', name: 'Minimal noise' },
  { id: 'medium', name: 'Medium noise' },
  { id: 'high', name: 'High noise' },
];

export const SVG_NOISE_OPTIONS = [
  { id: 'minimal', name: '±0.01px' },
  { id: 'medium', name: '±0.1px' },
  { id: 'high', name: '±0.5px' },
];

export const SPEECH_OPTIONS = [
  { id: 'noise', name: 'Randomize voices' },
  { id: 'block', name: 'Empty voice list' },
];

export const MATH_NOISE_OPTIONS = [
  { id: 'minimal', name: 'Minimal (±1e-15)' },
  { id: 'medium', name: 'Medium (±1e-12)' },
  { id: 'high', name: 'High (±1e-10)' },
];

export const PLUGINS_OPTIONS = [
  { id: '0', name: '0 plugins' },
  { id: '1', name: '1 plugin' },
  { id: '2', name: '2 plugins' },
  { id: '3', name: '3 plugins' },
  { id: '4', name: '4 plugins' },
  { id: '5', name: '5 plugins (standard)' },
  { id: '6', name: '6 plugins' },
  { id: '7', name: '7 plugins' },
  { id: '8', name: '8 plugins' },
  { id: '10', name: '10 plugins' },
  { id: '12', name: '12 plugins' },
  { id: '15', name: '15 plugins' },
];

export const HISTORY_OPTIONS = [
  { id: '2', name: '2 entries' },
  { id: '3', name: '3 entries' },
  { id: '5', name: '5 entries' },
  { id: '8', name: '8 entries' },
  { id: '10', name: '10 entries' },
  { id: '15', name: '15 entries' },
  { id: '20', name: '20 entries' },
  { id: '30', name: '30 entries' },
  { id: '50', name: '50 entries' },
  { id: '75', name: '75 entries' },
  { id: '100', name: '100 entries' },
];
