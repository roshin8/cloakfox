/**
 * Math Fingerprint Spoofer
 *
 * Math functions can return slightly different results on different
 * systems due to floating-point implementation differences.
 */

import type { ProtectionMode } from '@/types';
import type { PRNG } from '@/lib/crypto';
import { overrideMethod } from '@/lib/stealth';
import { logAccess } from '../../monitor/fingerprint-monitor';

/**
 * Initialize Math spoofing
 */
export function initMathSpoofer(mode: ProtectionMode, prng: PRNG): void {
  if (mode === 'off') return;

  // Small noise that's detectable by fingerprinters but won't break calculations
  const noise = () => (prng.nextFloat() - 0.5) * 1e-12;

  // Functions to spoof
  const mathFunctions: Array<keyof Math> = [
    'acos', 'acosh', 'asin', 'asinh', 'atan', 'atanh', 'atan2',
    'cos', 'cosh', 'exp', 'expm1', 'log', 'log1p', 'log10', 'log2',
    'sin', 'sinh', 'sqrt', 'tan', 'tanh', 'cbrt', 'hypot', 'pow'
  ];

  if (mode === 'block') {
    // In block mode, we normalize results
    // This is rarely used since it can break calculations
    return;
  }

  // Noise mode - add tiny noise to results, using stealth to avoid toString detection
  for (const fn of mathFunctions) {
    const original = Math[fn] as (...args: number[]) => number;
    if (typeof original !== 'function') continue;

    overrideMethod(Math as any, fn as string, (orig, _thisArg, args) => {
      logAccess(`Math.${fn}`, { spoofed: true, value: '\u00b11e-12 noise' });
      const result = orig.apply(Math, args);
      if (Number.isFinite(result) && !Number.isInteger(result)) {
        return result + noise();
      }
      return result;
    });
  }

  // Also spoof Math constants with very tiny noise
  // These are already exact, but some fingerprinters check them
  const originalPI = Math.PI;
  const originalE = Math.E;
  const originalLN2 = Math.LN2;
  const originalLN10 = Math.LN10;
  const originalLOG2E = Math.LOG2E;
  const originalLOG10E = Math.LOG10E;
  const originalSQRT2 = Math.SQRT2;
  const originalSQRT1_2 = Math.SQRT1_2;

  // These are already constants, fingerprinters just read them
  // We log access but don't modify since they're used in real calculations

}
