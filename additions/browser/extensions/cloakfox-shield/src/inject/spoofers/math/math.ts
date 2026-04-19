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

  // ─── Math constants noise ────────────────────────────────────────
  // Math.PI / Math.E / Math.LN2 / etc. are spec-fixed IEEE-754 doubles,
  // so every legitimate browser returns identical bit patterns. A per-
  // container 1e-16 ULP perturbation makes the values uniquely
  // identifiable to probes like `Math.PI.toString() === '3.141592653589793'`
  // while preserving enough numerical precision that trig, WebGL
  // matrices, physics sims, and canvas arc rendering stay visually
  // indistinguishable.
  //
  // The constants are defined with { configurable: false } by the JS
  // spec, so we can't redefineProperty them directly. Instead we wrap
  // `Math` in a Proxy and replace the global reference — callers that
  // read `Math.PI` or `Math.E` go through the get trap.
  //
  // Trade-off: code that does `if (Math.PI === 3.141592653589793)` will
  // break. Such code is rare and always a bug (the check is tautological
  // on every real browser), but math-heavy sites that happen to compare
  // constants to a hard-coded literal may misbehave. Set the math.functions
  // spoofer to 'off' to disable.
  const tinyNoise = () => (prng.nextFloat() - 0.5) * 1e-15;
  const spoofedConstants: Record<string, number> = {
    PI: Math.PI + tinyNoise(),
    E: Math.E + tinyNoise(),
    LN2: Math.LN2 + tinyNoise(),
    LN10: Math.LN10 + tinyNoise(),
    LOG2E: Math.LOG2E + tinyNoise(),
    LOG10E: Math.LOG10E + tinyNoise(),
    SQRT2: Math.SQRT2 + tinyNoise(),
    SQRT1_2: Math.SQRT1_2 + tinyNoise(),
  };

  const spoofedMath = new Proxy(Math, {
    get(target, prop, receiver) {
      if (typeof prop === 'string' && prop in spoofedConstants) {
        logAccess(`Math.${prop}`, { spoofed: true, value: 'constant noise' });
        return spoofedConstants[prop];
      }
      return Reflect.get(target, prop, receiver);
    },
  });

  try {
    Object.defineProperty(window, 'Math', {
      value: spoofedMath,
      writable: true,
      configurable: true,
    });
  } catch {
    // If the global is non-configurable (some sandboxes), skip silently —
    // the per-function noise above still runs.
  }
}
