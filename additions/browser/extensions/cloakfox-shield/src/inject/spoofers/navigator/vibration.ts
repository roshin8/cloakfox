/**
 * Vibration API Spoofer
 *
 * Spoofs navigator.vibrate to prevent fingerprinting via vibration support detection.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize Vibration API spoofing
 */
export function initVibrationSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Check if vibrate exists
  if (!('vibrate' in navigator)) {
    // If it doesn't exist, we might want to add a fake one to normalize
    if (mode === 'noise') {
      try {
        (navigator as any).vibrate = function (pattern: VibratePattern): boolean {
          logAccess('navigator.vibrate', { spoofed: true, value: 'spoofed' });
          return true; // Pretend it worked
        };
      } catch {
        // Can't add
      }
    }
    return;
  }

  const originalVibrate = navigator.vibrate.bind(navigator);

  // Replace navigator.vibrate
  try {
    (navigator as any).vibrate = function (pattern: VibratePattern): boolean {
      logAccess('navigator.vibrate', { spoofed: true, blocked: mode === 'block', value: 'spoofed' });

      if (mode === 'block') {
        return false; // Pretend vibration is not supported
      }

      // In noise mode, we still allow it but log it
      return originalVibrate(pattern);
    };
  } catch {
    // Can't override
  }

}
