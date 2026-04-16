/**
 * SVG Spoofer - Adds noise to SVG-based fingerprinting
 * SVG can be used for fingerprinting via:
 * - SVG filters (feConvolveMatrix, feTurbulence)
 * - SVG path rendering differences
 * - SVG text metrics
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { farbleDOMRect } from '@/lib/farbling';
import { overrideMethod } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize SVG spoofing
 */
export function initSVGSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  const maxNoise = mode === 'noise' ? 0.3 : 0;

  // Wrap SVGGraphicsElement methods
  if (typeof SVGGraphicsElement !== 'undefined') {
    // getBBox
    overrideMethod(SVGGraphicsElement.prototype, 'getBBox', (original, thisArg, args) => {
      logAccess('SVGGraphicsElement.getBBox', { spoofed: true, value: 'noised' });
      const bbox = original.call(thisArg, ...args) as DOMRect;

      if (mode === 'block') {
        return new DOMRect(0, 0, 0, 0);
      }

      const noisy = farbleDOMRect(bbox, prng, maxNoise);
      return new DOMRect(noisy.x, noisy.y, noisy.width, noisy.height);
    });

    // getCTM (Current Transformation Matrix)
    overrideMethod(SVGGraphicsElement.prototype, 'getCTM', (original, thisArg, _args) => {
      logAccess('SVGGraphicsElement.getCTM', { spoofed: true, value: 'noised' });
      const ctm = original.call(thisArg) as DOMMatrix | null;

      if (!ctm || mode === 'block') {
        return ctm;
      }

      const noise = () => prng.nextNoise(0.0001);

      return new DOMMatrix([
        ctm.a + noise(),
        ctm.b + noise(),
        ctm.c + noise(),
        ctm.d + noise(),
        ctm.e + noise(),
        ctm.f + noise(),
      ]);
    });

    // getScreenCTM
    overrideMethod(SVGGraphicsElement.prototype, 'getScreenCTM', (original, thisArg, _args) => {
      logAccess('SVGGraphicsElement.getScreenCTM', { spoofed: true, value: 'noised' });
      const ctm = original.call(thisArg) as DOMMatrix | null;

      if (!ctm || mode === 'block') {
        return ctm;
      }

      const noise = () => prng.nextNoise(0.0001);

      return new DOMMatrix([
        ctm.a + noise(),
        ctm.b + noise(),
        ctm.c + noise(),
        ctm.d + noise(),
        ctm.e + noise(),
        ctm.f + noise(),
      ]);
    });
  }

  // Wrap SVGTextContentElement methods
  if (typeof SVGTextContentElement !== 'undefined') {
    // getComputedTextLength
    overrideMethod(SVGTextContentElement.prototype, 'getComputedTextLength', (original, thisArg, _args) => {
      logAccess('SVGTextContentElement.getComputedTextLength', { spoofed: true, value: 'noised' });
      const length = original.call(thisArg) as number;

      if (mode === 'block') {
        return 0;
      }

      return length + prng.nextNoise(maxNoise);
    });

    // getSubStringLength
    overrideMethod(SVGTextContentElement.prototype, 'getSubStringLength', (original, thisArg, args) => {
      logAccess('SVGTextContentElement.getSubStringLength', { spoofed: true, value: 'noised' });
      const length = original.call(thisArg, ...args) as number;

      if (mode === 'block') {
        return 0;
      }

      return length + prng.nextNoise(maxNoise);
    });

    // getStartPositionOfChar
    overrideMethod(SVGTextContentElement.prototype, 'getStartPositionOfChar', (original, thisArg, args) => {
      logAccess('SVGTextContentElement.getStartPositionOfChar', { spoofed: true, value: 'noised' });
      const point = original.call(thisArg, ...args) as DOMPoint;

      if (mode === 'block') {
        return new DOMPoint(0, 0);
      }

      return new DOMPoint(
        point.x + prng.nextNoise(maxNoise),
        point.y + prng.nextNoise(maxNoise)
      );
    });

    // getEndPositionOfChar
    overrideMethod(SVGTextContentElement.prototype, 'getEndPositionOfChar', (original, thisArg, args) => {
      logAccess('SVGTextContentElement.getEndPositionOfChar', { spoofed: true, value: 'noised' });
      const point = original.call(thisArg, ...args) as DOMPoint;

      if (mode === 'block') {
        return new DOMPoint(0, 0);
      }

      return new DOMPoint(
        point.x + prng.nextNoise(maxNoise),
        point.y + prng.nextNoise(maxNoise)
      );
    });

    // getExtentOfChar
    overrideMethod(SVGTextContentElement.prototype, 'getExtentOfChar', (original, thisArg, args) => {
      logAccess('SVGTextContentElement.getExtentOfChar', { spoofed: true, value: 'noised' });
      const rect = original.call(thisArg, ...args) as DOMRect;

      if (mode === 'block') {
        return new DOMRect(0, 0, 0, 0);
      }

      const noisy = farbleDOMRect(rect, prng, maxNoise);
      return new DOMRect(noisy.x, noisy.y, noisy.width, noisy.height);
    });
  }

  // Wrap SVGGeometryElement methods
  if (typeof SVGGeometryElement !== 'undefined') {
    // getTotalLength
    overrideMethod(SVGGeometryElement.prototype, 'getTotalLength', (original, thisArg, _args) => {
      logAccess('SVGGeometryElement.getTotalLength', { spoofed: true, value: 'noised' });
      const length = original.call(thisArg) as number;

      if (mode === 'block') {
        return 0;
      }

      return length + prng.nextNoise(maxNoise);
    });

    // getPointAtLength
    overrideMethod(SVGGeometryElement.prototype, 'getPointAtLength', (original, thisArg, args) => {
      logAccess('SVGGeometryElement.getPointAtLength', { spoofed: true, value: 'noised' });
      const point = original.call(thisArg, ...args) as DOMPoint;

      if (mode === 'block') {
        return new DOMPoint(0, 0);
      }

      return new DOMPoint(
        point.x + prng.nextNoise(maxNoise),
        point.y + prng.nextNoise(maxNoise)
      );
    });
  }

}
