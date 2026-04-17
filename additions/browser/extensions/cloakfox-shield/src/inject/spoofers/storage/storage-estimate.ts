/**
 * Storage Estimate Spoofer
 *
 * The StorageManager.estimate() API reveals disk space information
 * which can be used for fingerprinting.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { logAccess } from '../../monitor/fingerprint-monitor';

// Common quota values (in bytes) - 50% of disk space is typical
const COMMON_QUOTAS = [
  50 * 1024 * 1024 * 1024, // 50 GB
  100 * 1024 * 1024 * 1024, // 100 GB
  150 * 1024 * 1024 * 1024, // 150 GB
  200 * 1024 * 1024 * 1024, // 200 GB
  250 * 1024 * 1024 * 1024, // 250 GB
];

/**
 * Initialize Storage estimate spoofing
 */
export function initStorageSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  if (!('storage' in navigator) || !navigator.storage.estimate) return;

  const originalEstimate = navigator.storage.estimate.bind(navigator.storage);

  navigator.storage.estimate = async function (): Promise<StorageEstimate> {
    logAccess('navigator.storage.estimate', { spoofed: true, value: 'randomized' });

    if (mode === 'block') {
      // Return zeros to block the API
      return {
        quota: 0,
        usage: 0,
      };
    }

    // Get real estimate to base our fake on
    let realEstimate: StorageEstimate;
    try {
      realEstimate = await originalEstimate();
    } catch {
      realEstimate = { quota: 0, usage: 0 };
    }

    // Pick a common quota value
    const fakeQuota = prng.pick(COMMON_QUOTAS);

    // Fake usage - small percentage of quota
    const usagePercent = prng.nextFloat() * 0.05; // 0-5% used
    const fakeUsage = Math.floor(fakeQuota * usagePercent);

    return {
      quota: fakeQuota,
      usage: fakeUsage,
    };
  };

  // Also spoof navigator.storage.persisted
  if (navigator.storage.persisted) {
    navigator.storage.persisted = async function (): Promise<boolean> {
      logAccess('navigator.storage.persisted', { spoofed: true, value: 'randomized' });
      return false; // Most sites don't have persistent storage
    };
  }

}
