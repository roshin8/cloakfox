/**
 * Screen Extended Spoofer
 *
 * screen.isExtended reveals multi-monitor setups.
 * Fingerprint.com uses this to identify desktop configurations.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideGetterWithValue } from '@/lib/stealth';

export function initScreenExtendedSpoofer(mode: ProtectionMode, _prng: PRNG): void {
  if (mode === 'off') return;

  // Always report single monitor to reduce fingerprint surface
  if ('isExtended' in Screen.prototype) {
    overrideGetterWithValue(Screen.prototype, 'isExtended', () => false);
  }
}
