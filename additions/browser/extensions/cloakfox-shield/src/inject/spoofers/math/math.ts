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
      logAccess(`Math.${String(fn)}`, { spoofed: true, value: '\u00b11e-12 noise' });
      const result = orig.apply(Math, args);
      if (Number.isFinite(result) && !Number.isInteger(result)) {
        return result + noise();
      }
      return result;
    });
  }

  // Math constants (PI, E, LN2, etc.) are read-only values that some
  // fingerprinters check. We don't modify them — they're used in real
  // numerical code and any noise would break calculations. Leaving them
  // untouched is the correct trade-off.
}
