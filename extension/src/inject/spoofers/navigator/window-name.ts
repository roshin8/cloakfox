/**
 * Window.name Spoofer
 *
 * window.name persists across navigations on the same tab and can be used
 * for cross-site tracking. Chameleon clears it on navigation.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideGetterWithValue } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';

export function initWindowNameSpoofer(mode: ProtectionMode, _prng: PRNG): void {
  if (mode === 'off') return;

  // Clear window.name and prevent setting it
  let storedName = '';

  Object.defineProperty(window, 'name', {
    get: () => { logAccess('window.name', { spoofed: true, value: 'cleared' }); return mode === 'block' ? '' : storedName; },
    set: (val: string) => {
      if (mode !== 'block') storedName = val;
      // In block mode, silently ignore sets
    },
    configurable: true,
    enumerable: true,
  });
}
