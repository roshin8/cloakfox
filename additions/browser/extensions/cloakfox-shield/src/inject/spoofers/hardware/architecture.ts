/**
 * Architecture Spoofer
 *
 * FingerprintJS detects 32-bit vs 64-bit architecture via:
 * - Float32Array: f32[0] = 1e308 then read back
 * - Math.fround() precision differences
 * - ArrayBuffer behavior
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod } from '@/lib/stealth';

export function initArchitectureSpoofer(mode: ProtectionMode, _prng: PRNG): void {
  if (mode === 'off') return;

  // Ensure Math.fround always behaves like 64-bit
  const originalFround = Math.fround;
  overrideMethod(Math as any, 'fround', (original, _thisArg, args) => {
    return original.apply(Math, args);
  });
}
