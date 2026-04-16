/**
 * Touch Events Spoofer
 *
 * Touch capability detection can reveal device type
 * and is used for fingerprinting.
 */

import type { ProtectionMode, AssignedProfileData } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

export function initTouchSpoofer(mode: ProtectionMode, prng: PRNG, assignedProfile?: AssignedProfileData): void {
  if (mode === 'off') return;

  // Determine touch points based on profile
  const isMobile = assignedProfile?.userAgent?.mobile ?? false;
  const spoofedMaxTouchPoints = mode === 'block' ? 0
    : isMobile ? prng.pick([5, 10, 10])
    : prng.pick([0, 0, 1, 2, 5]); // desktop: mostly 0, some laptops have touch
  const spoofedTouchSupport = spoofedMaxTouchPoints > 0;

  try {
    Object.defineProperty(navigator, 'maxTouchPoints', {
      get() {
        logAccess('navigator.maxTouchPoints', { spoofed: true, value: `${spoofedMaxTouchPoints} points` });
        return spoofedMaxTouchPoints;
      },
      configurable: true,
    });
  } catch {}

  // Spoof 'ontouchstart' - present on touch devices, undefined on desktop
  if (!spoofedTouchSupport) {
    try {
      Object.defineProperty(window, 'ontouchstart', {
        value: undefined, writable: true, configurable: true,
      });
    } catch {}
  }

  // Block TouchEvent/Touch on non-touch profiles
  if (!spoofedTouchSupport && mode === 'block') {
    try { Object.defineProperty(window, 'TouchEvent', { value: undefined, configurable: true }); } catch {}
    try { Object.defineProperty(window, 'Touch', { value: undefined, configurable: true }); } catch {}
  }

  // Mobile orientation
  if (!isMobile) {
    try { Object.defineProperty(window, 'orientation', { value: undefined, configurable: true }); } catch {}
  }
}
