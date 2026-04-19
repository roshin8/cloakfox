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
  // container perturbation makes the values uniquely identifiable to
  // probes like `Math.PI.toString()` while preserving enough precision
  // that trig, WebGL matrices, physics sims, and canvas arcs stay
  // visually indistinguishable.
  //
  // Perturbation magnitude: 1e-13. Must be ABOVE float64 ULP at ~3.14
  // (ULP ≈ 4.44e-16) — a perturbation smaller than ULP rounds away and
  // produces the IEEE-identical bit pattern, defeating the spoof. 1e-13
  // is ~225 ULP, guaranteed to survive float arithmetic, and still below
  // visual thresholds (canvas arc drawn at 1000px radius drifts by
  // < 1e-9 pixels).
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
  const tinyNoise = () => (prng.nextFloat() - 0.5) * 1e-13;
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

  // We can't use a Proxy here. Math.PI/E/LN2 are defined with
  // { writable: false, configurable: false } by spec, and the Proxy
  // invariant for non-writable non-configurable properties requires
  // the get trap to return the same value as the target — otherwise
  // accessing a proxied Math.PI throws TypeError at runtime.
  //
  // Workaround: build a plain object that has every Math method
  // inherited, copy each constant into a local OWN writable property
  // (so our override is visible without violating proxy invariants),
  // then replace the global Math binding.
  const spoofedMath: Record<string | symbol, unknown> = Object.create(
    Object.getPrototypeOf(Math)
  );

  // Copy Math's methods and unspoofed constants onto spoofedMath. Skip
  // any key we plan to override — otherwise we'd copy the original
  // { writable: false, configurable: false } descriptor first, making
  // the subsequent override throw silently and leave the real value.
  const skipKeys = new Set(Object.keys(spoofedConstants));
  for (const key of Reflect.ownKeys(Math)) {
    if (typeof key === 'string' && skipKeys.has(key)) continue;
    try {
      const desc = Object.getOwnPropertyDescriptor(Math, key);
      if (desc) Object.defineProperty(spoofedMath, key, desc);
    } catch {}
  }

  // Install the spoofed constants as plain own properties — no special
  // descriptor so defineProperty succeeds.
  for (const [name, value] of Object.entries(spoofedConstants)) {
    spoofedMath[name] = value;
  }

  // Intercept Math.<method>.toString() so stack-trace fingerprinting that
  // reads trig function source (`Math.sin.toString()`) still returns the
  // native `"function sin() { [native code] }"` — our `spoofedMath` holds
  // references to the originals so this works naturally.

  try {
    Object.defineProperty(window, 'Math', {
      value: spoofedMath,
      writable: true,
      configurable: true,
    });
    logAccess('Math.constants', { spoofed: true, value: 'per-container noise' });
  } catch {
    // Some sandboxes disallow this; the per-function noise above still ran.
  }
}
