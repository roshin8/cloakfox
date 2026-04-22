/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: Math constants + trig noise per userContextId.
 *
 * Runs as a JSWindowActor child (chrome principal, content process,
 * invoked on every DOMWindowCreated). Reads a per-container seed from
 * prefs, derives an xorshift state, perturbs Math.PI / Math.E and
 * noise-wraps the trig/log family. Page MAIN sees what looks like a
 * native Math object. No extension involved; no WebIDL setter round
 * trip; no [Func=...] gates; no MAIN-world extension code.
 *
 * This is the cpp-first proof-of-concept for the "must-stay JS" class
 * of signals — the things C++ can't touch without instrumenting
 * thousands of call sites. See docs/cpp-first/inventory.md for the
 * full list.
 */

const NOISE_MAG_CONST = 1e-13;  // above float64 ULP at ~3.14 (~4.44e-16)
const NOISE_MAG_TRIG  = 1e-12;

function makePRNG(seedBytes) {
  // xorshift128+ seeded from 32 bytes of seed material. Inline so we
  // don't carry the extension's lib/crypto.ts.
  let s0 = 0n, s1 = 0n;
  for (let i = 0; i < 16; i++) s0 = (s0 << 8n) | BigInt(seedBytes[i]);
  for (let i = 16; i < 32; i++) s1 = (s1 << 8n) | BigInt(seedBytes[i]);
  const MASK = (1n << 64n) - 1n;
  return function next() {
    let x = s0; const y = s1;
    s0 = y;
    x = (x ^ (x << 23n)) & MASK;
    s1 = (x ^ y ^ (x >> 17n) ^ (y >> 26n)) & MASK;
    const combined = Number((s1 + y) & ((1n << 53n) - 1n));
    return combined / Number(1n << 53n);
  };
}

function b64ToBytes(b64) {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export class CloakfoxMathChild extends JSWindowActorChild {
  handleEvent(event) {
    if (event.type !== "DOMWindowCreated") return;
    try {
      this.#installMathSpoofer();
    } catch (_e) {
      // Never leak chrome:// paths in page stacks. Silently fail.
    }
  }

  #installMathSpoofer() {
    const win = this.contentWindow;
    if (!win) return;

    // Master enable check — one pref guards the whole cpp-first math layer.
    if (!Services.prefs.getBoolPref("cloakfox.enabled", false)) return;

    const ucid = win.docShell?.browsingContext?.originAttributes?.userContextId ?? 0;
    const seedB64 = Services.prefs.getStringPref(`cloakfox.container.${ucid}.math_seed`, "");
    if (!seedB64) return;  // No seed => no spoofing for this container.

    const prng = makePRNG(b64ToBytes(seedB64));
    const piOffset = (prng() - 0.5) * NOISE_MAG_CONST;
    const eOffset  = (prng() - 0.5) * NOISE_MAG_CONST;

    // Math.PI / Math.E are non-configurable per spec, so we cannot
    // defineProperty them directly. Replace Math with a fresh object
    // that copies all other descriptors and carries our spoofed
    // constants as own data properties.
    //
    // CRITICAL: the copy loop must skip the constants we're about to
    // override, otherwise Object.defineProperty copies the non-
    // configurable descriptor first and our override silently fails.
    // (The pre-cpp-first MAIN-world math spoofer hit this exact bug
    // in live testing.)
    const pageWin = win.wrappedJSObject;
    const origMath = pageWin.Math;
    const spoofedMath = Cu.cloneInto({}, pageWin);
    const CONSTANTS = new Set([
      "PI", "E", "LN2", "LN10", "LOG2E", "LOG10E", "SQRT2", "SQRT1_2",
    ]);

    for (const key of Object.getOwnPropertyNames(origMath)) {
      if (CONSTANTS.has(key)) continue;
      const d = Object.getOwnPropertyDescriptor(origMath, key);
      if (!d) continue;
      try {
        Object.defineProperty(spoofedMath, key, d);
      } catch (_e) { /* best effort */ }
    }

    spoofedMath.PI      = origMath.PI + piOffset;
    spoofedMath.E       = origMath.E + eOffset;
    spoofedMath.LN2     = origMath.LN2 + (prng() - 0.5) * NOISE_MAG_CONST;
    spoofedMath.LN10    = origMath.LN10 + (prng() - 0.5) * NOISE_MAG_CONST;
    spoofedMath.LOG2E   = 1 / spoofedMath.LN2;
    spoofedMath.LOG10E  = 1 / spoofedMath.LN10;
    spoofedMath.SQRT2   = origMath.SQRT2 + (prng() - 0.5) * NOISE_MAG_CONST;
    spoofedMath.SQRT1_2 = 1 / spoofedMath.SQRT2;

    // Trig / log / sqrt / pow family: exportFunction so the page sees
    // `function <name>() { [native code] }` when it introspects.
    const TRIG_FNS = [
      "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
      "sinh", "cosh", "tanh", "asinh", "acosh", "atanh",
      "exp", "expm1", "log", "log2", "log10", "log1p",
      "sqrt", "cbrt", "hypot", "pow",
    ];
    for (const fn of TRIG_FNS) {
      const orig = origMath[fn];
      if (typeof orig !== "function") continue;
      spoofedMath[fn] = Cu.exportFunction(function (...args) {
        const r = orig.apply(origMath, args);
        return Number.isFinite(r) && !Number.isInteger(r)
          ? r + (prng() - 0.5) * NOISE_MAG_TRIG
          : r;
      }, pageWin, { defineAs: fn });
    }

    pageWin.Math = spoofedMath;
  }
}
