/**
 * DOMRect Spoofer - Adds noise to getBoundingClientRect and getClientRects
 * These APIs are used for font fingerprinting and layout-based fingerprinting
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { farbleDOMRect } from '@/lib/farbling';
import { overrideMethod } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize DOMRect spoofing
 */
export function initDOMRectSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  const maxNoise = mode === 'noise' ? 0.5 : 0;

  // Wrap Element.prototype.getBoundingClientRect
  overrideMethod(Element.prototype, 'getBoundingClientRect', (original, thisArg, _args) => {
    const rect = original.call(thisArg) as DOMRect;

    if (mode === 'block') {
      logAccess('Element.getBoundingClientRect', { spoofed: true, value: 'blocked' });
      return new DOMRect(0, 0, 0, 0);
    }

    const noisy = farbleDOMRect(rect, prng, maxNoise);
    const result = new DOMRect(noisy.x, noisy.y, noisy.width, noisy.height);
    logAccess('Element.getBoundingClientRect', { spoofed: true, value: `${result.width.toFixed(2)}x${result.height.toFixed(2)}` });
    return result;
  });

  // Wrap Element.prototype.getClientRects
  overrideMethod(Element.prototype, 'getClientRects', (original, thisArg, _args) => {
    logAccess('Element.getClientRects', { spoofed: true, value: `\u00b1${maxNoise} noise` });
    const rects = original.call(thisArg) as DOMRectList;

    if (mode === 'block') {
      const emptyList = {
        length: 0,
        item: () => null,
        [Symbol.iterator]: function* () {},
      } as unknown as DOMRectList;
      return emptyList;
    }

    const noisyRects: DOMRect[] = [];
    for (let i = 0; i < rects.length; i++) {
      const rect = rects[i];
      const noisy = farbleDOMRect(rect, prng, maxNoise);
      noisyRects.push(new DOMRect(noisy.x, noisy.y, noisy.width, noisy.height));
    }

    const result = {
      length: noisyRects.length,
      item: (index: number) => noisyRects[index] || null,
      [Symbol.iterator]: function* () {
        for (const rect of noisyRects) {
          yield rect;
        }
      },
    };

    for (let i = 0; i < noisyRects.length; i++) {
      (result as any)[i] = noisyRects[i];
    }

    return result as unknown as DOMRectList;
  });

  // Wrap Range.prototype.getBoundingClientRect
  overrideMethod(Range.prototype, 'getBoundingClientRect', (original, thisArg, _args) => {
    logAccess('Range.getBoundingClientRect', { spoofed: true, value: `\u00b1${maxNoise} noise` });
    const rect = original.call(thisArg) as DOMRect;

    if (mode === 'block') {
      return new DOMRect(0, 0, 0, 0);
    }

    const noisy = farbleDOMRect(rect, prng, maxNoise);
    return new DOMRect(noisy.x, noisy.y, noisy.width, noisy.height);
  });

  // Wrap Range.prototype.getClientRects
  overrideMethod(Range.prototype, 'getClientRects', (original, thisArg, _args) => {
    logAccess('Range.getClientRects', { spoofed: true, value: `\u00b1${maxNoise} noise` });
    const rects = original.call(thisArg) as DOMRectList;

    if (mode === 'block') {
      const emptyList = {
        length: 0,
        item: () => null,
        [Symbol.iterator]: function* () {},
      } as unknown as DOMRectList;
      return emptyList;
    }

    const noisyRects: DOMRect[] = [];
    for (let i = 0; i < rects.length; i++) {
      const rect = rects[i];
      const noisy = farbleDOMRect(rect, prng, maxNoise);
      noisyRects.push(new DOMRect(noisy.x, noisy.y, noisy.width, noisy.height));
    }

    const result = {
      length: noisyRects.length,
      item: (index: number) => noisyRects[index] || null,
      [Symbol.iterator]: function* () {
        for (const rect of noisyRects) {
          yield rect;
        }
      },
    };

    for (let i = 0; i < noisyRects.length; i++) {
      (result as any)[i] = noisyRects[i];
    }

    return result as unknown as DOMRectList;
  });

}
