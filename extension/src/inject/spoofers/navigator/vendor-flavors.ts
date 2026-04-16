/**
 * Vendor Flavors Spoofer - Hides/spoofs vendor-specific window globals
 *
 * FingerprintJS checks for globals like window.chrome, window.safari, __cr_,
 * __gCrWeb, etc. to identify the real browser even when UA is spoofed.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';

export function initVendorFlavorSpoofer(mode: ProtectionMode, _prng: PRNG): void {
  if (mode === 'off') return;

  // These globals leak real browser identity
  const chromiumGlobals = [
    'chrome', '__cr_', '__gCrWeb', '__crWeb', '__gCrExtension',
    'external', 'chrome_', 'Debug',
  ];

  const safariGlobals = [
    'safari', '__safari_', '__webkit_',
  ];

  // In noise mode: remove vendor-specific globals that don't match spoofed UA
  // In block mode: remove all vendor globals
  const globalsToHide = mode === 'block'
    ? [...chromiumGlobals, ...safariGlobals]
    : [...chromiumGlobals, ...safariGlobals]; // For Firefox, hide Chrome/Safari globals

  for (const prop of globalsToHide) {
    if (prop in window) {
      try {
        Object.defineProperty(window, prop, {
          get: () => undefined,
          configurable: true,
        });
      } catch {
        // Some properties may not be configurable
      }
    }
  }
}
