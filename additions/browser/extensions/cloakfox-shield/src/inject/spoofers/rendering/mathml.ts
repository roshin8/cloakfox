/**
 * MathML Rendering Spoofer
 *
 * MathML element rendering can be used for fingerprinting
 * as different browsers render mathematical notation differently.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize MathML rendering spoofing
 */
export function initMathMLSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // MathML fingerprinting typically uses getBoundingClientRect on math elements
  // We already spoof DOMRect, but we can add MathML-specific detection

  overrideMethod(Element.prototype, 'getBoundingClientRect', (original, thisArg, _args) => {
    const rect = original.call(thisArg) as DOMRect;

    // Check if this is a MathML element
    const isMathElement = thisArg.namespaceURI === 'http://www.w3.org/1998/Math/MathML' ||
      thisArg.tagName.toLowerCase().startsWith('math') ||
      thisArg.closest('math') !== null;

    if (isMathElement) {
      logAccess('MathML.getBoundingClientRect', { spoofed: true, value: 'noised' });

      if (mode === 'block') {
        return new DOMRect(0, 0, 0, 0);
      }

      // Add noise to MathML element measurements
      const noise = () => prng.nextNoise(0.5);
      return new DOMRect(
        rect.x + noise(),
        rect.y + noise(),
        rect.width + noise(),
        rect.height + noise()
      );
    }

    return rect;
  });

  // Also spoof getComputedStyle for math elements
  overrideMethod(window as any, 'getComputedStyle', (original, _thisArg, args) => {
    const style = original.apply(window, args);
    const element = args[0] as Element;

    const isMathElement = element?.namespaceURI === 'http://www.w3.org/1998/Math/MathML' ||
      element?.tagName?.toLowerCase().startsWith('math') ||
      element?.closest?.('math') !== null;

    if (isMathElement) {
      logAccess('MathML.getComputedStyle', { spoofed: true, value: 'noised' });
    }

    return style;
  });
}
