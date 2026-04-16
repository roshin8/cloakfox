/**
 * TextMetrics Spoofer - Adds noise to canvas measureText
 * Used for font fingerprinting via text width measurements
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize TextMetrics spoofing
 */
export function initTextMetricsSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  const maxNoise = mode === 'noise' ? 0.3 : 0;

  // Wrap CanvasRenderingContext2D.measureText
  overrideMethod(CanvasRenderingContext2D.prototype, 'measureText', (original, thisArg, args) => {
    logAccess('CanvasRenderingContext2D.measureText', { spoofed: true, value: 'noised' });
    const metrics = original.call(thisArg, ...args) as TextMetrics;

    if (mode === 'block') {
      return createFakeTextMetrics(0);
    }

    const noise = () => prng.nextNoise(maxNoise);

    return new Proxy(metrics, {
      get(target, prop) {
        const value = (target as any)[prop];

        if (typeof value === 'number') {
          return value + noise();
        }

        return value;
      },
    });
  });

  // Also wrap OffscreenCanvasRenderingContext2D if available
  if (typeof OffscreenCanvasRenderingContext2D !== 'undefined') {
    overrideMethod(OffscreenCanvasRenderingContext2D.prototype, 'measureText', (original, thisArg, args) => {
      logAccess('OffscreenCanvasRenderingContext2D.measureText', { spoofed: true, value: 'noised' });
      const metrics = original.call(thisArg, ...args) as TextMetrics;

      if (mode === 'block') {
        return createFakeTextMetrics(0);
      }

      const noise = () => prng.nextNoise(maxNoise);

      return new Proxy(metrics, {
        get(target, prop) {
          const value = (target as any)[prop];
          if (typeof value === 'number') {
            return value + noise();
          }
          return value;
        },
      });
    });
  }

}

/**
 * Create a fake TextMetrics object with specified width
 */
function createFakeTextMetrics(width: number): TextMetrics {
  return {
    width,
    actualBoundingBoxLeft: 0,
    actualBoundingBoxRight: width,
    actualBoundingBoxAscent: 0,
    actualBoundingBoxDescent: 0,
    fontBoundingBoxAscent: 0,
    fontBoundingBoxDescent: 0,
    emHeightAscent: 0,
    emHeightDescent: 0,
    hangingBaseline: 0,
    alphabeticBaseline: 0,
    ideographicBaseline: 0,
  } as TextMetrics;
}
