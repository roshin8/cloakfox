/**
 * ProfileManager — generates deterministic, coherent fingerprint profiles
 * per container using the container's entropy seed.
 *
 * Same entropy seed always produces the same profile.
 * Different containers get different profiles.
 */

import { PRNG } from '@/lib/crypto';
import { STORAGE_KEYS } from '@/constants';
import type { AssignedProfile } from '@/types';

/** Platform definitions with coherent property sets */
const PLATFORMS = [
  {
    platform: 'Win32',
    oscpuPrefix: 'Windows NT ',
    osVersions: ['10.0', '10.0', '10.0', '11.0'], // weighted toward Win10
    uaOS: (v: string) =>
      `Windows NT ${v}; Win64; x64`,
    appVersionOS: (v: string) =>
      `Windows NT ${v}; Win64; x64`,
    webglVendors: [
      { vendor: 'Google Inc. (NVIDIA)', renderers: [
        'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)',
        'ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0, D3D11)',
        'ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0, D3D11)',
        'ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Direct3D11 vs_5_0 ps_5_0, D3D11)',
      ]},
      { vendor: 'Google Inc. (AMD)', renderers: [
        'ANGLE (AMD, AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0, D3D11)',
        'ANGLE (AMD, AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0, D3D11)',
      ]},
      { vendor: 'Google Inc. (Intel)', renderers: [
        'ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)',
        'ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)',
      ]},
    ],
  },
  {
    platform: 'MacIntel',
    oscpuPrefix: 'Intel Mac OS X ',
    osVersions: ['10.15', '10.15', '11.0', '12.0', '13.0', '14.0'],
    uaOS: (v: string) =>
      `Macintosh; Intel Mac OS X ${v.replace('.', '_')}`,
    appVersionOS: (v: string) =>
      `Macintosh; Intel Mac OS X ${v.replace('.', '_')}`,
    webglVendors: [
      { vendor: 'Google Inc. (Apple)', renderers: [
        'ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)',
        'ANGLE (Apple, ANGLE Metal Renderer: Apple M2, Unspecified Version)',
        'ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Pro, Unspecified Version)',
        'ANGLE (Apple, ANGLE Metal Renderer: Apple M3, Unspecified Version)',
      ]},
      { vendor: 'Google Inc. (Intel)', renderers: [
        'ANGLE (Intel Inc., Intel(R) Iris(TM) Plus Graphics, OpenGL 4.1)',
        'ANGLE (Intel Inc., Intel(R) UHD Graphics 630, OpenGL 4.1)',
      ]},
    ],
  },
  {
    platform: 'Linux x86_64',
    oscpuPrefix: 'Linux x86_64',
    osVersions: [''],
    uaOS: () => 'X11; Linux x86_64',
    appVersionOS: () => 'X11; Linux x86_64',
    webglVendors: [
      { vendor: 'Mesa', renderers: [
        'Mesa Intel(R) UHD Graphics 630 (CFL GT2)',
        'Mesa Intel(R) Xe Graphics (TGL GT2)',
      ]},
      { vendor: 'X.Org', renderers: [
        'AMD Radeon RX 580 (polaris10, LLVM 15.0.7, DRM 3.49, 6.1.0)',
        'AMD Radeon RX 6700 XT (navi22, LLVM 16.0.6, DRM 3.52, 6.5.0)',
      ]},
    ],
  },
] as const;

/** Common screen resolutions */
const SCREENS = [
  { w: 1920, h: 1080 },
  { w: 1920, h: 1080 },
  { w: 2560, h: 1440 },
  { w: 1366, h: 768 },
  { w: 1536, h: 864 },
  { w: 1440, h: 900 },
  { w: 1680, h: 1050 },
  { w: 3840, h: 2160 },
];

/** Taskbar height offsets (availHeight = height - offset) */
const TASKBAR_OFFSETS = [25, 30, 40, 48, 55, 65];

/** Common hardware concurrency values */
const CORE_COUNTS = [4, 4, 6, 8, 8, 12, 16];

/** Common device memory values (GB) */
const MEMORY_VALUES = [4, 8, 8, 16, 16, 32];

/** Timezones */
const TIMEZONES = [
  'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles',
  'America/Toronto', 'Europe/London', 'Europe/Paris', 'Europe/Berlin',
  'Europe/Amsterdam', 'Asia/Tokyo', 'Asia/Shanghai', 'Asia/Singapore',
  'Australia/Sydney', 'Pacific/Auckland',
];

/** Languages */
const LANGUAGES = [
  { primary: 'en-US', list: ['en-US', 'en'] },
  { primary: 'en-GB', list: ['en-GB', 'en'] },
  { primary: 'en-US', list: ['en-US', 'en'] },
  { primary: 'en-US', list: ['en-US', 'en'] },
  { primary: 'de', list: ['de', 'en-US', 'en'] },
  { primary: 'fr', list: ['fr', 'en-US', 'en'] },
  { primary: 'ja', list: ['ja', 'en-US', 'en'] },
];

/** Profile cache: cookieStoreId → AssignedProfile */
const profileCache = new Map<string, AssignedProfile>();

/**
 * Generate or retrieve a deterministic profile for a container.
 * Same entropy seed always produces the same profile.
 */
export async function getProfileForContainer(
  cookieStoreId: string,
  entropySeed: string
): Promise<AssignedProfile> {
  const cached = profileCache.get(cookieStoreId);
  if (cached) return cached;

  // Check storage for persisted profiles
  const stored = await browser.storage.local.get(STORAGE_KEYS.CONTAINER_PROFILES);
  const allProfiles = (stored[STORAGE_KEYS.CONTAINER_PROFILES] ?? {}) as Record<
    string,
    AssignedProfile
  >;

  if (allProfiles[cookieStoreId]) {
    profileCache.set(cookieStoreId, allProfiles[cookieStoreId]);
    return allProfiles[cookieStoreId];
  }

  // Generate new profile deterministically from entropy
  const profile = await generateProfile(entropySeed);

  // Persist
  allProfiles[cookieStoreId] = profile;
  await browser.storage.local.set({ [STORAGE_KEYS.CONTAINER_PROFILES]: allProfiles });
  profileCache.set(cookieStoreId, profile);
  return profile;
}

/** Generate a coherent profile from an entropy seed */
async function generateProfile(entropy: string): Promise<AssignedProfile> {
  const rng = await PRNG.fromDerivedKey(entropy, 'profile', 'generation');

  // Pick platform
  const platformDef = rng.pick(PLATFORMS);
  const osVersion = rng.pick(platformDef.osVersions);
  const platform = platformDef.platform;
  const oscpu = platformDef.oscpuPrefix + osVersion;

  // Build user agent
  const ffVersion = '146.0';
  const uaOS = platformDef.uaOS(osVersion);
  const userAgent = `Mozilla/5.0 (${uaOS}) Gecko/20100101 Firefox/${ffVersion}`;
  const appVersion = `5.0 (${platformDef.appVersionOS(osVersion)})`;

  // Screen
  const screen = rng.pick(SCREENS);
  const taskbarOffset = rng.pick(TASKBAR_OFFSETS);

  // WebGL — pick vendor/renderer coherent with platform
  const vendorDef = rng.pick(platformDef.webglVendors);
  const webglVendor = vendorDef.vendor;
  const webglRenderer = rng.pick(vendorDef.renderers);

  // Other hardware
  const cores = rng.pick(CORE_COUNTS);
  const memory = rng.pick(MEMORY_VALUES);
  const tz = rng.pick(TIMEZONES);
  const lang = rng.pick(LANGUAGES);

  return {
    userAgent: {
      userAgent,
      platform,
      oscpu,
      appVersion,
    },
    screen: {
      width: screen.w,
      height: screen.h,
      availWidth: screen.w,
      availHeight: screen.h - taskbarOffset,
      colorDepth: 24,
      pixelDepth: 24,
    },
    hardwareConcurrency: cores,
    deviceMemory: memory,
    maxTouchPoints: 0,
    language: lang.primary,
    languages: lang.list,
    timezone: tz,
    webgl: {
      vendor: webglVendor,
      renderer: webglRenderer,
    },
  };
}

/** Clear the profile cache (e.g., on rotation) */
export function clearProfileCache(): void {
  profileCache.clear();
}
