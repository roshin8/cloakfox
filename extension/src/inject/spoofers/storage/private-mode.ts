/**
 * Private Mode Detection Prevention
 *
 * Fingerprinters detect private/incognito mode via:
 * 1. Storage quota differences (private = lower quota)
 * 2. IndexedDB behavior in private mode
 * 3. navigator.storage.estimate() returns lower values
 *
 * Normalize these to match regular browsing mode.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

export function initPrivateModeProtection(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Normalize storage.estimate() to return consistent values
  // Private mode typically reports much lower quota
  if (navigator.storage?.estimate) {
    const origEstimate = navigator.storage.estimate.bind(navigator.storage);
    navigator.storage.estimate = async function(): Promise<StorageEstimate> {
      logAccess('navigator.storage.estimate', { spoofed: true });
      const real = await origEstimate();
      // Return a "normal" looking quota (~50GB) regardless of actual mode
      const normalQuota = 53687091200; // ~50GB
      return {
        quota: normalQuota,
        usage: real.usage || 0,
      };
    };
  }

  // Normalize StorageManager.persisted() — private mode returns false
  if (navigator.storage?.persisted) {
    const origPersisted = navigator.storage.persisted.bind(navigator.storage);
    navigator.storage.persisted = async function(): Promise<boolean> {
      logAccess('navigator.storage.persisted', { spoofed: true });
      return false; // Consistent: regular mode also returns false by default
    };
  }
}
