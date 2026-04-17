/**
 * Screen Spoofer - Spoofs screen dimensions and related properties
 * Uses assigned profile for guaranteed uniqueness across containers.
 * Overrides on PROTOTYPE level to avoid detection.
 */

import type { ProtectionMode, AssignedProfileData } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { farbleScreenResolution, COMMON_SCREEN_RESOLUTIONS } from '@/lib/farbling';
import { overrideGetterWithValue } from '@/lib/stealth';
import { logAccess, markScreenSpoofed } from '../../monitor/fingerprint-monitor';

interface AssignedScreenConfig {
  width: number;
  height: number;
  availWidth: number;
  availHeight: number;
  colorDepth: number;
  pixelDepth: number;
  devicePixelRatio: number;
}

export function initScreenSpoofer(
  mode: ProtectionMode,
  prng: PRNG,
  assignedScreen?: AssignedScreenConfig
): void {
  if (mode === 'off') return;

  markScreenSpoofed(mode);

  let targetScreen: { width: number; height: number };
  let availWidth: number;
  let availHeight: number;
  let colorDepth: number;
  let pixelDepth: number;
  let devicePixelRatio: number;

  if (assignedScreen && assignedScreen.width && assignedScreen.height) {
    targetScreen = { width: assignedScreen.width, height: assignedScreen.height };
    availWidth = assignedScreen.availWidth;
    availHeight = assignedScreen.availHeight;
    colorDepth = assignedScreen.colorDepth;
    pixelDepth = assignedScreen.pixelDepth;
    devicePixelRatio = assignedScreen.devicePixelRatio;
  } else if (mode === 'noise') {
    targetScreen = farbleScreenResolution(prng);
    colorDepth = prng.pick([24, 32]);
    pixelDepth = colorDepth;
    devicePixelRatio = prng.pick([1, 1.25, 1.5, 2]);
    availWidth = targetScreen.width;
    availHeight = targetScreen.height - prng.nextInt(30, 50);
  } else {
    targetScreen = COMMON_SCREEN_RESOLUTIONS[0];
    colorDepth = 24;
    pixelDepth = 24;
    devicePixelRatio = 1;
    availWidth = targetScreen.width;
    availHeight = targetScreen.height - 40;
  }

  const innerWidth = Math.min(targetScreen.width, prng.nextInt(1200, targetScreen.width));
  const innerHeight = Math.min(availHeight, prng.nextInt(700, availHeight));
  const outerWidth = innerWidth + prng.nextInt(0, 20);
  const outerHeight = innerHeight + prng.nextInt(70, 120);

  let screenLogged = false;
  const logScreen = () => {
    if (!screenLogged) {
      logAccess('screen.width', { spoofed: true, value: `${targetScreen.width}x${targetScreen.height}` });
      screenLogged = true;
    }
  };

  // Override on Screen.prototype (not instance) to match native behavior
  overrideGetterWithValue(Screen.prototype, 'width', () => { logScreen(); return targetScreen.width; });
  overrideGetterWithValue(Screen.prototype, 'height', () => { logScreen(); return targetScreen.height; });
  overrideGetterWithValue(Screen.prototype, 'availWidth', () => { logScreen(); return availWidth; });
  overrideGetterWithValue(Screen.prototype, 'availHeight', () => { logScreen(); return availHeight; });
  overrideGetterWithValue(Screen.prototype, 'availLeft', () => 0);
  overrideGetterWithValue(Screen.prototype, 'availTop', () => 0);
  overrideGetterWithValue(Screen.prototype, 'colorDepth', () => { logScreen(); return colorDepth; });
  overrideGetterWithValue(Screen.prototype, 'pixelDepth', () => { logScreen(); return pixelDepth; });

  // Also override directly on window.screen instance as fallback
  // (Firefox may not honor prototype-level defineProperty for Screen)
  const screenOverrides: Record<string, number> = {
    width: targetScreen.width, height: targetScreen.height,
    availWidth, availHeight, colorDepth, pixelDepth,
  };
  for (const [prop, val] of Object.entries(screenOverrides)) {
    try { Object.defineProperty(window.screen, prop, { get: () => val, configurable: true }); } catch {}
  }

  // Window properties - these are own properties on window, use defineProperty
  const screenTopValue = prng.nextInt(0, 30);
  const windowProps: Record<string, () => any> = {
    innerWidth: () => { logScreen(); return innerWidth; },
    innerHeight: () => { logScreen(); return innerHeight; },
    outerWidth: () => { logScreen(); return outerWidth; },
    outerHeight: () => { logScreen(); return outerHeight; },
    devicePixelRatio: () => { logAccess('window.devicePixelRatio', { spoofed: true }); return devicePixelRatio; },
    screenX: () => 0,
    screenY: () => 0,
    screenLeft: () => 0,
    screenTop: () => screenTopValue,
  };

  for (const [prop, getter] of Object.entries(windowProps)) {
    overrideGetterWithValue(window as any, prop, getter);
  }
}
