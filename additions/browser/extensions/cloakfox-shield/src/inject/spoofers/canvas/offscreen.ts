/**
 * OffscreenCanvas Spoofer
 *
 * OffscreenCanvas can be used in workers for fingerprinting,
 * bypassing main-thread canvas protections.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';
import { farbleImageData } from '@/lib/farbling';

/**
 * Initialize OffscreenCanvas spoofing
 */
export function initOffscreenCanvasSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  if (typeof OffscreenCanvas === 'undefined') return;

  // Spoof OffscreenCanvas.convertToBlob
  if ('convertToBlob' in OffscreenCanvas.prototype) {
    overrideMethod(OffscreenCanvas.prototype, 'convertToBlob', async (original, thisArg, args) => {
      const options = args[0] as ImageEncodeOptions | undefined;
      logAccess('OffscreenCanvas.convertToBlob', { spoofed: mode !== 'block', value: 'noised' });

      if (mode === 'block') {
        return new Blob([], { type: options?.type || 'image/png' });
      }

      // Get 2D context and add noise
      const ctx = thisArg.getContext('2d');
      if (ctx) {
        const imageData = ctx.getImageData(0, 0, thisArg.width, thisArg.height);
        farbleImageData(imageData.data, prng, 3);
        ctx.putImageData(imageData, 0, 0);
      }

      return original.call(thisArg, ...args);
    });
  }

  // Spoof getContext to track WebGL usage
  overrideMethod(OffscreenCanvas.prototype, 'getContext', (original, thisArg, args) => {
    const contextType = args[0] as string;
    logAccess(`OffscreenCanvas.getContext(${contextType})`, { spoofed: true, value: 'noised' });
    return original.call(thisArg, ...args);
  });

}
