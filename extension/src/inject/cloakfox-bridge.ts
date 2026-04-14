/**
 * Cloakfox Bridge — calls window.setXxx() self-destructing methods
 * with domain-specific deterministic values.
 *
 * This replaces the entire ContainerShield spoofers/ directory.
 * All actual spoofing happens in the C++ engine; we just configure it.
 */

import { PRNG } from '@/lib/crypto';
import type { AssignedProfile, CloakfoxWindow, SpooferSettings } from '@/types';

const win = window as unknown as CloakfoxWindow;

/** Platform-appropriate font lists for font filtering */
const PLATFORM_FONTS: Record<string, readonly string[]> = {
  Win32: [
    'Arial', 'Calibri', 'Cambria', 'Comic Sans MS', 'Consolas', 'Courier New',
    'Georgia', 'Impact', 'Lucida Console', 'Microsoft Sans Serif', 'Palatino Linotype',
    'Segoe UI', 'Tahoma', 'Times New Roman', 'Trebuchet MS', 'Verdana',
  ],
  MacIntel: [
    'Arial', 'Avenir', 'Avenir Next', 'Courier New', 'Futura', 'Geneva',
    'Georgia', 'Helvetica', 'Helvetica Neue', 'Lucida Grande', 'Menlo',
    'Monaco', 'Optima', 'Palatino', 'SF Pro', 'Times New Roman', 'Trebuchet MS',
  ],
  Linux: [
    'Arial', 'Cantarell', 'Courier New', 'DejaVu Sans', 'DejaVu Serif',
    'Droid Sans', 'FreeSans', 'Georgia', 'Liberation Mono', 'Liberation Sans',
    'Liberation Serif', 'Noto Sans', 'Noto Serif', 'Times New Roman', 'Ubuntu',
  ],
};

/** Call a self-destructing window method if it exists */
function callIfAvailable<K extends keyof CloakfoxWindow>(
  method: K,
  ...args: CloakfoxWindow[K] extends ((...a: infer P) => void) | undefined ? P : never[]
): boolean {
  const fn = win[method];
  if (typeof fn === 'function') {
    (fn as (...a: unknown[]) => void)(...args);
    return true;
  }
  return false;
}

/** Select a deterministic subset of platform-appropriate fonts */
function selectPlatformFonts(platform: string, rng: PRNG): string[] {
  const baseFonts = PLATFORM_FONTS[platform] ?? PLATFORM_FONTS['Win32']!;
  const count = rng.nextInt(Math.floor(baseFonts.length * 0.6), baseFonts.length);
  const shuffled = rng.shuffle([...baseFonts]);
  return shuffled.slice(0, count).sort();
}

/** Generate a deterministic private IP from the PRNG */
function generateDeterministicIP(rng: PRNG): string {
  // 192.168.x.x range
  return `192.168.${rng.nextInt(0, 255)}.${rng.nextInt(1, 254)}`;
}

/**
 * Configure Cloakfox C++ spoofing for the current page.
 * Called once at document_start before any page scripts run.
 */
export async function configureCloakfoxSpoofing(
  containerSeed: string,
  domain: string,
  profile: AssignedProfile,
  settings: SpooferSettings
): Promise<void> {
  const rng = await PRNG.fromDerivedKey(containerSeed, domain, 'master');

  // Canvas
  if (settings.graphics?.canvas !== 'off') {
    callIfAvailable('setCanvasSeed', rng.nextInt(1, 2147483647));
  }

  // Audio
  if (settings.audio?.context !== 'off') {
    callIfAvailable('setAudioFingerprintSeed', rng.nextInt(1, 2147483647));
  }

  // Navigator
  if (settings.navigator?.userAgent !== 'off') {
    callIfAvailable('setNavigatorUserAgent', profile.userAgent.userAgent);
    callIfAvailable('setNavigatorPlatform', profile.userAgent.platform);
    callIfAvailable('setNavigatorOscpu', profile.userAgent.oscpu);
  }
  if (settings.navigator?.hardwareConcurrency !== 'off') {
    callIfAvailable('setNavigatorHardwareConcurrency', profile.hardwareConcurrency);
  }

  // Screen
  if (settings.hardware?.screen !== 'off') {
    callIfAvailable('setScreenDimensions', profile.screen.width, profile.screen.height);
    callIfAvailable('setScreenColorDepth', profile.screen.colorDepth);
  }

  // Fonts
  if (settings.fonts?.enumeration !== 'off') {
    const fontSubset = selectPlatformFonts(profile.userAgent.platform, rng);
    callIfAvailable('setFontList', fontSubset.join(','));
  }
  if (settings.fonts?.metrics !== 'off') {
    callIfAvailable('setFontSpacingSeed', rng.nextInt(1, 2147483647));
  }

  // WebGL
  if (settings.graphics?.webgl !== 'off') {
    callIfAvailable('setWebGLVendor', profile.webgl.vendor);
    callIfAvailable('setWebGLRenderer', profile.webgl.renderer);
  }

  // WebRTC
  if (settings.network?.webrtc !== 'off') {
    callIfAvailable('setWebRTCIPv4', generateDeterministicIP(rng));
    // IPv6 uses a deterministic fd00::/8 ULA address
    const ipv6 = `fd00::${rng.nextInt(1, 0xffff).toString(16)}:${rng.nextInt(1, 0xffff).toString(16)}`;
    callIfAvailable('setWebRTCIPv6', ipv6);
  }

  // Timezone
  if (settings.timing?.timezone !== 'off') {
    callIfAvailable('setTimezone', profile.timezone);
  }
}
