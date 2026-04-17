/**
 * Tab History Spoofer
 *
 * window.history.length reveals how many pages the user has visited in this tab.
 * Real browsing sessions typically have 3-50+ entries.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideGetterWithValue } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';

export function initTabHistorySpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Realistic history lengths based on real browsing patterns:
  // - Short session: 2-5 (just opened tab, clicked a few links)
  // - Normal session: 5-15 (browsing around a site)
  // - Long session: 15-50 (deep research, shopping)
  const fakeLength = mode === 'block'
    ? 2
    : prng.pick([3, 4, 5, 6, 7, 8, 10, 12, 15, 18, 22, 28, 35, 42, 50]);

  overrideGetterWithValue(History.prototype, 'length', () => { logAccess('history.length', { spoofed: true, value: `${fakeLength}` }); return fakeLength; });
}
