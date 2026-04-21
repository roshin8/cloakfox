/**
 * Boot config generator — shared by content/index.ts (ISOLATED) and
 * inject/index.ts (MAIN).
 *
 * Historically the MAIN-world inject script was the only place this ran,
 * but after moving C++ setter calls to ISOLATED (for stealth — page
 * scripts in MAIN can't probe typeof setCanvasSeed anymore), both content
 * scripts need the same deterministic config. Centralizing here avoids
 * drift between the two.
 */

import type { InjectConfig, AssignedProfileData } from '@/types';
import { createDefaultSettings } from '@/types/settings';
import { ALL_PROFILES } from '@/lib/profiles/user-agents';
import { PRNG, base64ToUint8Array } from '@/lib/crypto';

// DO NOT include the domain here. initializeSpoofers() XORs the domain into
// this seed AGAIN to derive the per-page PRNG — if the seed already carried
// domain bits, the two XORs cancel and every fallback-path page ends up with
// the same PRNG state. The fallback seed is a fixed salt; all per-domain
// entropy comes from the second XOR inside the spoofers module.
const FALLBACK_SALT = ':cloakfox:fallback:seed:v1';

export function generateSeed(): string {
  const bytes = new Uint8Array(32);
  const saltBytes = new TextEncoder().encode(FALLBACK_SALT);
  for (let i = 0; i < saltBytes.length; i++) {
    bytes[i % 32] ^= saltBytes[i];
  }
  if (bytes.every(b => b === 0)) bytes[0] = 1;
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

const WINDOWS_SCREENS = [
  { w: 1366, h: 768, dpr: 1 }, { w: 1440, h: 900, dpr: 1 },
  { w: 1536, h: 864, dpr: 1.25 }, { w: 1600, h: 900, dpr: 1 },
  { w: 1680, h: 1050, dpr: 1 }, { w: 1920, h: 1200, dpr: 1 },
  { w: 2560, h: 1440, dpr: 1 },
] as const;

const MAC_SCREENS = [
  { w: 1440, h: 900, dpr: 2 }, { w: 1512, h: 982, dpr: 2 },
  { w: 1680, h: 1050, dpr: 2 }, { w: 1728, h: 1117, dpr: 2 },
  { w: 1800, h: 1169, dpr: 2 }, { w: 2560, h: 1600, dpr: 2 },
] as const;

const LINUX_SCREENS = [
  { w: 1366, h: 768, dpr: 1 }, { w: 1920, h: 1080, dpr: 1 },
  { w: 2560, h: 1440, dpr: 1 }, { w: 3440, h: 1440, dpr: 1 },
] as const;

const LOCALE_TIMEZONE_PAIRS = [
  { lang: ['en-US', 'en'], tz: -300 }, { lang: ['en-US', 'en'], tz: -480 },
  { lang: ['en-US', 'en'], tz: -360 }, { lang: ['en-GB', 'en'], tz: 0 },
  { lang: ['de-DE', 'de', 'en'], tz: 60 }, { lang: ['fr-FR', 'fr', 'en'], tz: 60 },
  { lang: ['ja-JP', 'ja'], tz: 540 }, { lang: ['es-ES', 'es', 'en'], tz: 60 },
  { lang: ['pt-BR', 'pt', 'en'], tz: -180 },
] as const;

export function generateProfile(seed: string, realPlatform: string): AssignedProfileData {
  const prng = new PRNG(base64ToUint8Array(seed));
  const pick = <T,>(arr: readonly T[]): T => arr[prng.nextInt(0, arr.length - 1)];

  const realIsMac = realPlatform === 'MacIntel' || realPlatform.includes('Mac');
  const realIsWin = realPlatform === 'Win32' || realPlatform.includes('Win');
  const realIsLinux = realPlatform.includes('Linux');

  const recentDesktop = ALL_PROFILES.filter(p => {
    if (p.mobile) return false;
    const versionMatch = p.userAgent.match(/Chrome\/(\d+)|Firefox\/(\d+)/);
    if (!versionMatch) return false;
    const version = parseInt(versionMatch[1] || versionMatch[2], 10);
    if (version < 120) return false;
    if (realIsMac && p.platformName === 'macOS') return false;
    if (realIsWin && p.platformName === 'Windows') return false;
    if (realIsLinux && p.platformName === 'Linux') return false;
    return true;
  });
  const ua = pick(recentDesktop.length > 0 ? recentDesktop : ALL_PROFILES.filter(p => !p.mobile));

  const isMac = ua.platformName === 'macOS';
  const isLinux = ua.platformName === 'Linux';
  const isFirefox = !ua.brands;

  const screenList: readonly { readonly w: number; readonly h: number; readonly dpr: number }[] =
    isMac ? MAC_SCREENS : isLinux ? LINUX_SCREENS : WINDOWS_SCREENS;
  const scr = pick(screenList);
  const locale = pick(LOCALE_TIMEZONE_PAIRS);

  return {
    userAgent: {
      id: ua.id, name: ua.name, userAgent: ua.userAgent, platform: ua.platform,
      vendor: ua.vendor, appVersion: ua.appVersion, oscpu: ua.oscpu,
      mobile: ua.mobile, platformName: ua.platformName, platformVersion: ua.platformVersion,
      brands: ua.brands,
    },
    screen: {
      width: scr.w, height: scr.h,
      availWidth: scr.w, availHeight: scr.h - (isMac ? 25 : 40),
      colorDepth: isMac ? 30 : 24, pixelDepth: isMac ? 30 : 24,
      devicePixelRatio: scr.dpr,
    },
    hardwareConcurrency: pick(isMac ? [8, 10, 12] as const : [4, 8, 12, 16] as const),
    deviceMemory: isFirefox ? undefined : pick([4, 8] as const),
    timezoneOffset: locale.tz,
    languages: [...locale.lang],
  };
}

/**
 * Build the full InjectConfig from the current origin + real platform.
 * Deterministic: same origin + same real platform produces the same config.
 */
export function generateConfig(origin: string, realPlatform: string): InjectConfig {
  const seed = generateSeed();
  return {
    containerId: 'fallback',
    domain: origin,
    seed,
    useCoreEngine: true,
    settings: createDefaultSettings().spoofers,
    profile: { mode: 'random' as const },
    assignedProfile: generateProfile(seed, realPlatform),
  };
}
