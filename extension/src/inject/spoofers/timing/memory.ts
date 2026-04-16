/**
 * Memory API Spoofer
 *
 * performance.measureUserAgentSpecificMemory() and performance.memory
 * reveal memory layout that can fingerprint browser build and extensions.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod, overrideGetterWithValue } from '@/lib/stealth';

export function initMemorySpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // performance.measureUserAgentSpecificMemory (Chrome)
  if ('measureUserAgentSpecificMemory' in performance) {
    overrideMethod(performance as any, 'measureUserAgentSpecificMemory', () => {
      const fakeBytes = prng.nextInt(50, 200) * 1024 * 1024;
      return Promise.resolve({
        bytes: fakeBytes,
        breakdown: [{
          bytes: fakeBytes,
          attribution: [{ url: window.location.href, scope: 'Window' }],
          types: ['JS'],
        }],
      });
    });
  }

  // performance.memory (Chrome non-standard)
  if ('memory' in performance) {
    const fakeMemory = {
      jsHeapSizeLimit: 2172649472,
      totalJSHeapSize: prng.nextInt(10, 50) * 1024 * 1024,
      usedJSHeapSize: prng.nextInt(5, 30) * 1024 * 1024,
    };

    try {
      Object.defineProperty(performance, 'memory', {
        get: () => fakeMemory,
        configurable: true,
      });
    } catch {
      // May not be configurable
    }
  }
}
