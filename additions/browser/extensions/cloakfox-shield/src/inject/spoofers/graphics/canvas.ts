/**
 * Canvas Spoofer - Adds noise to canvas fingerprinting APIs
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { farbleImageData } from '@/lib/farbling';
import { overrideMethod } from '@/lib/stealth';
import { logAccess, markCanvasSpoofed } from '../../monitor/fingerprint-monitor';

// Fast string hash for generating CreepJS-style fingerprint IDs
function quickHash(str: string): string {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = ((h << 5) - h + str.charCodeAt(i)) | 0;
  return (h >>> 0).toString(16).padStart(8, '0');
}

export function initCanvasSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  markCanvasSpoofed(mode);

  const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;

  overrideMethod(HTMLCanvasElement.prototype, 'toDataURL', (original, thisArg, args) => {
    if (mode === 'block') {
      logAccess('HTMLCanvasElement.toDataURL', { blocked: true, spoofed: false, value: 'blocked' });
      return 'data:image/png;base64,';
    }

    const ctx = thisArg.getContext('2d');
    if (ctx) {
      const imageData = originalGetImageData.call(ctx, 0, 0, thisArg.width, thisArg.height);
      farbleImageData(imageData.data, prng);
      ctx.putImageData(imageData, 0, 0);
    }

    const result = original.apply(thisArg, args);
    logAccess('HTMLCanvasElement.toDataURL', { spoofed: true, value: '#' + quickHash(result) });
    return result;
  });

  overrideMethod(HTMLCanvasElement.prototype, 'toBlob', (original, thisArg, args) => {
    logAccess('HTMLCanvasElement.toBlob', { blocked: mode === 'block', spoofed: mode === 'noise', value: mode === 'block' ? 'blocked' : 'noised' });

    if (mode === 'block') {
      args[0]?.(null);
      return;
    }

    const ctx = thisArg.getContext('2d');
    if (ctx) {
      const imageData = originalGetImageData.call(ctx, 0, 0, thisArg.width, thisArg.height);
      farbleImageData(imageData.data, prng);
      ctx.putImageData(imageData, 0, 0);
    }

    return original.apply(thisArg, args);
  });

  overrideMethod(CanvasRenderingContext2D.prototype, 'getImageData', (original, thisArg, args) => {
    logAccess('CanvasRenderingContext2D.getImageData', { blocked: mode === 'block', spoofed: mode === 'noise', value: mode === 'block' ? 'blocked' : 'noised' });

    const imageData = original.apply(thisArg, args);

    if (mode === 'block') return new ImageData(args[2], args[3]);

    farbleImageData(imageData.data, prng);
    return imageData;
  });

  // OffscreenCanvas
  if (typeof OffscreenCanvas !== 'undefined') {
    overrideMethod(OffscreenCanvas.prototype, 'convertToBlob', (original, thisArg, args) => {
      if (mode === 'block') return Promise.resolve(new Blob([]));

      const ctx = thisArg.getContext('2d') as OffscreenCanvasRenderingContext2D | null;
      if (ctx) {
        const imageData = ctx.getImageData(0, 0, thisArg.width, thisArg.height);
        farbleImageData(imageData.data, prng);
        ctx.putImageData(imageData, 0, 0);
      }

      return original.apply(thisArg, args);
    });
  }

  // Block canvas.captureStream — returns unnoised video stream
  if (HTMLCanvasElement.prototype.captureStream) {
    overrideMethod(HTMLCanvasElement.prototype, 'captureStream', (original, thisArg, args) => {
      logAccess('HTMLCanvasElement.captureStream', { spoofed: true });
      if (mode === 'block') {
        // Return empty MediaStream
        return new MediaStream();
      }
      // Noise mode: add noise to canvas before capturing
      const canvas = thisArg as HTMLCanvasElement;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        try {
          const imageData = ctx.getImageData(0, 0, 1, 1);
          farbleImageData(imageData.data, prng);
          ctx.putImageData(imageData, 0, 0);
        } catch {}
      }
      return original.apply(thisArg, args);
    });
  }
}
