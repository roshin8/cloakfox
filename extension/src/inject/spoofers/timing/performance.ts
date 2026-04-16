/**
 * Performance Timing Spoofer - Reduces precision of performance.now()
 * High-resolution timing can be used for:
 * - Spectre/Meltdown side-channel attacks
 * - Timing-based fingerprinting
 * - Clock skew fingerprinting
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize performance timing spoofing
 */
export function initPerformanceSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Store original performance.now
  const originalNow = performance.now.bind(performance);

  // Determine precision reduction
  // Firefox already reduces to 1ms, we can reduce further
  let precision: number;

  if (mode === 'block') {
    precision = 100; // Round to nearest 100ms
  } else {
    // Noise mode - add jitter and reduce precision
    precision = prng.pick([1, 2, 5, 10]); // Random precision level
  }

  // Add consistent offset for this container+domain
  const offset = prng.nextFloatRange(-50, 50);

  let perfLogged = false;
  // Wrap performance.now() with stealth
  overrideMethod(Performance.prototype, 'now', () => {
    if (!perfLogged) {
      logAccess('performance.now', { spoofed: true, value: `${precision}ms precision` });
      perfLogged = true;
    }
    const now = originalNow();
    if (mode === 'block') {
      return Math.round(now / precision) * precision;
    }
    const jitter = prng.nextNoise(0.5);
    const modified = now + offset + jitter;
    return Math.round(modified / precision) * precision;
  });

  // Also wrap Date.now() for consistency
  overrideMethod(Date, 'now', (original, _thisArg, _args) => {
    const now = original.call(Date) as number;

    if (mode === 'block') {
      return Math.round(now / precision) * precision;
    }

    const jitter = prng.nextNoise(1);
    return Math.round((now + jitter) / precision) * precision;
  });

  // Wrap performance.timeOrigin (read-only, so we use getter)
  const originalTimeOrigin = performance.timeOrigin;
  const fakeTimeOrigin = originalTimeOrigin + offset;

  Object.defineProperty(performance, 'timeOrigin', {
    get: function () {
      if (mode === 'block') {
        return Math.round(originalTimeOrigin / 100) * 100;
      }
      return fakeTimeOrigin;
    },
    configurable: true,
  });

  // Wrap performance.timing (deprecated but still used)
  if (performance.timing) {
    const originalTiming = performance.timing;

    const timingProxy = new Proxy(originalTiming, {
      get(target, prop) {
        const value = (target as any)[prop];

        if (typeof value === 'number' && value > 0) {
          if (mode === 'block') {
            return Math.round(value / 100) * 100;
          }
          return Math.round((value + offset) / precision) * precision;
        }

        return value;
      },
    });

    Object.defineProperty(performance, 'timing', {
      get: function () {
        return timingProxy;
      },
      configurable: true,
    });
  }

  // Wrap performance.getEntries and related methods
  const wrapEntries = (entries: PerformanceEntryList): PerformanceEntryList => {
    return entries.map((entry) => {
      return new Proxy(entry, {
        get(target, prop) {
          const value = (target as any)[prop];

          // Reduce precision of timing values
          if (
            typeof value === 'number' &&
            ['startTime', 'duration', 'responseEnd', 'fetchStart'].includes(
              prop as string
            )
          ) {
            if (mode === 'block') {
              return Math.round(value / 100) * 100;
            }
            return Math.round((value + offset) / precision) * precision;
          }

          if (typeof value === 'function') {
            return value.bind(target);
          }

          return value;
        },
      });
    });
  };

  const originalGetEntries = performance.getEntries.bind(performance);
  performance.getEntries = function (): PerformanceEntryList {
    return wrapEntries(originalGetEntries());
  };

  const originalGetEntriesByType = performance.getEntriesByType.bind(performance);
  performance.getEntriesByType = function (type: string): PerformanceEntryList {
    return wrapEntries(originalGetEntriesByType(type));
  };

  const originalGetEntriesByName = performance.getEntriesByName.bind(performance);
  performance.getEntriesByName = function (
    name: string,
    type?: string
  ): PerformanceEntryList {
    return wrapEntries(originalGetEntriesByName(name, type));
  };

  // Add timing noise to WebAssembly compilation/instantiation
  // Fingerprinters compare JS vs WASM execution timing to profile hardware
  if (typeof WebAssembly !== 'undefined') {
    const origCompile = WebAssembly.compile;
    WebAssembly.compile = async function(bytes: BufferSource): Promise<WebAssembly.Module> {
      logAccess('WebAssembly.compile', { spoofed: true });
      const jitterMs = prng.nextFloat() * 5;
      await new Promise(r => setTimeout(r, jitterMs));
      return origCompile(bytes);
    };

    const origInstantiate = WebAssembly.instantiate;
    WebAssembly.instantiate = async function(
      source: BufferSource | WebAssembly.Module,
      imports?: WebAssembly.Imports
    ): Promise<any> {
      logAccess('WebAssembly.instantiate', { spoofed: true });
      const jitterMs = prng.nextFloat() * 5;
      await new Promise(r => setTimeout(r, jitterMs));
      return origInstantiate(source as any, imports);
    };
  }

}
