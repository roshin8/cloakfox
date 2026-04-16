/**
 * WebGL Shader Spoofer
 *
 * Shader compilation and precision can be used for fingerprinting.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize WebGL shader spoofing
 */
export function initWebGLShaderSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  const contexts: Array<{ name: string; proto: any }> = [];

  if (typeof WebGLRenderingContext !== 'undefined') {
    contexts.push({ name: 'WebGLRenderingContext', proto: WebGLRenderingContext.prototype });
  }
  if (typeof WebGL2RenderingContext !== 'undefined') {
    contexts.push({ name: 'WebGL2RenderingContext', proto: WebGL2RenderingContext.prototype });
  }

  for (const { name: ctxName, proto } of contexts) {
    // Spoof getShaderPrecisionFormat
    if (proto.getShaderPrecisionFormat) {
      overrideMethod(proto, 'getShaderPrecisionFormat', (original, thisArg, args) => {
        logAccess(`${ctxName}.getShaderPrecisionFormat`, { spoofed: true });

        if (mode === 'block') {
          return {
            rangeMin: 127,
            rangeMax: 127,
            precision: 23,
          } as WebGLShaderPrecisionFormat;
        }

        const result = original.call(thisArg, ...args);

        if (result && mode === 'noise') {
          return {
            rangeMin: result.rangeMin,
            rangeMax: result.rangeMax,
            precision: Math.max(0, result.precision + prng.nextInt(-1, 1)),
          } as WebGLShaderPrecisionFormat;
        }

        return result;
      });
    }

    // Spoof getShaderInfoLog (can reveal compiler info)
    if (proto.getShaderInfoLog) {
      overrideMethod(proto, 'getShaderInfoLog', (original, thisArg, args) => {
        logAccess(`${ctxName}.getShaderInfoLog`, { spoofed: true });

        if (mode === 'block') {
          return '';
        }

        return original.call(thisArg, ...args);
      });
    }

    // Spoof getProgramInfoLog
    if (proto.getProgramInfoLog) {
      overrideMethod(proto, 'getProgramInfoLog', (original, thisArg, args) => {
        logAccess(`${ctxName}.getProgramInfoLog`, { spoofed: true });

        if (mode === 'block') {
          return '';
        }

        return original.call(thisArg, ...args);
      });
    }
  }

}
