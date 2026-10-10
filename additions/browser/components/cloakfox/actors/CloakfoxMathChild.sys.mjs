/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: Math constants + trig noise per userContextId.
 *
 * Runs as a JSWindowActor child (chrome principal, content process,
 * invoked on every DOMDocElementInserted). Reads a per-container seed from
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

// SharedMap.get deserializes a new copy on every read. Animation loops can
// make tens of thousands of Math calls per frame, so share one snapshot across
// this process's actors and discard it only when the parent publishes changes.
// This listener captures no actor or window and lives with the module.
const SHARED_KEY = "cloakfox-seeds";
const sharedData = Services.cpmm.sharedData;
let cachedSeeds;
sharedData.addEventListener("change", event => {
  if (event.changedKeys.includes(SHARED_KEY)) cachedSeeds = undefined;
});
function currentSeeds() {
  return cachedSeeds ??= sharedData.get(SHARED_KEY) || {};
}

let mathEnabled = Services.prefs.getBoolPref("cloakfox.enabled", false);
Services.prefs.addObserver("cloakfox.enabled", {
  observe() {
    mathEnabled = Services.prefs.getBoolPref("cloakfox.enabled", false);
  },
});
// With the global policy off, private/FPP page realms can still select fdlibm
// for these three intrinsics while the chrome realm uses the platform library.
// Keep their page-realm path in that case, including after a live pref change.
const FDLIBM_PREF = "javascript.options.use_fdlibm_for_sin_cos_tan";
let useFdlibm = Services.prefs.getBoolPref(FDLIBM_PREF, false);
Services.prefs.addObserver(FDLIBM_PREF, {
  observe() {
    useFdlibm = Services.prefs.getBoolPref(FDLIBM_PREF, false);
  },
});
const isNumber = value => typeof value === "number";

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

// Cu.exportFunction yields a page-side function with name:"" and length:0.
// Native methods report their own name + arity, so a probe reading
// fn.name / fn.length can spot the wrapper. Set both on the page object
// (Xray-waived so the page sees them) with native function-property flags
// {writable:false, enumerable:false, configurable:true}.
function setNativeIdentity(exportedFn, name, length) {
  const waived = Cu.waiveXrays(exportedFn);
  try {
    Object.defineProperty(waived, "name", {
      value: name, writable: false, enumerable: false, configurable: true,
    });
    Object.defineProperty(waived, "length", {
      value: length, writable: false, enumerable: false, configurable: true,
    });
  } catch (_e) { /* best effort — identity match is defense in depth */ }
  return exportedFn;
}

export class CloakfoxMathChild extends JSWindowActorChild {
  handleEvent(event) {
    // DOMDocElementInserted fires when <html> is inserted — before any
    // page <script> runs but after the inner window global exists.
    // DOMWindowCreated does NOT work as a JSWindowActor trigger
    // (silently never fires); verified empirically, matches the
    // pattern every Firefox builtin actor uses.
    if (event.type !== "DOMDocElementInserted") return;
    try {
      this.#installMathSpoofer();
    } catch (_e) {
      // Never leak chrome:// paths in page stacks. Silently fail.
    }
  }

  #installMathSpoofer() {
    const win = this.contentWindow;
    if (!win) return;

    // Install pass-through wrappers before page scripts even when the master
    // is off. Calls consult the live switch/overlay; enabling later preserves
    // this page and the function references its scripts already captured.

    // Per-container seeds live in cloakfox.container.<ucid>.* prefs
    // which DON'T auto-sync to content processes. Read from
    // Services.cpmm.sharedData where CloakfoxSeedSync (parent-side)
    // keeps a live snapshot.
    const seeds = currentSeeds();
    const ucid = win.docShell?.browsingContext?.originAttributes?.userContextId ?? 0;
    const seedB64 = seeds[`cloakfox.container.${ucid}.math_seed`] || "";

    const prng = makePRNG(seedB64 ? b64ToBytes(seedB64) : new Uint8Array(32));
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

    // Descriptor fidelity: Object.defineProperty across the Xray boundary
    // DOES preserve flags (verified empirically — copied constants read
    // {writable:false, configurable:false, enumerable:false}, matching
    // native Math.PI). So both the constant copy below and the trig-method
    // definitions further down use defineProperty with native flags, and a
    // descriptor probe / Object.keys(Math) reads identical to native.
    //
    // Math constants (PI, E, etc.) are IEEE 754 spec-defined values —
    // every real browser produces them bit-exact. Perturbing them is a
    // self-flagging signal: Math.PI === 3.141592653589793 returning
    // false unambiguously means anti-fingerprinting is active.
    //
    // The trig FUNCTIONS below are different — sin/cos/exp/log results
    // genuinely vary in last bits across CPUs and libm implementations,
    // so noise-wrapping them is plausibly invisible.
    //
    // Default: only wrap the functions, leave constants bit-exact. Power
    // users who want Spectre-style timing-attack defense via constant
    // perturbation can flip cloakfox.opt.math_constants_noise = true.
    const noiseConstants = Services.prefs.getBoolPref("cloakfox.enabled", false) &&
      Services.prefs.getBoolPref("cloakfox.opt.math_constants_noise", false);

    for (const key of Object.getOwnPropertyNames(origMath)) {
      // Skip constants only when we plan to override them with
      // perturbed values (descriptor copy would lock them in first
      // and the assignment below would silently fail). When NOT
      // perturbing, copy them normally so spoofedMath has all the
      // constants the page expects, bit-exact.
      if (noiseConstants && CONSTANTS.has(key)) continue;
      const d = Object.getOwnPropertyDescriptor(origMath, key);
      if (!d) continue;
      try { Object.defineProperty(spoofedMath, key, d); } catch (_e) {}
    }

    if (noiseConstants) {
      spoofedMath.PI      = origMath.PI + piOffset;
      spoofedMath.E       = origMath.E + eOffset;
      spoofedMath.LN2     = origMath.LN2  + (prng() - 0.5) * NOISE_MAG_CONST;
      spoofedMath.LN10    = origMath.LN10 + (prng() - 0.5) * NOISE_MAG_CONST;
      spoofedMath.LOG2E   = 1 / spoofedMath.LN2;
      spoofedMath.LOG10E  = 1 / spoofedMath.LN10;
      spoofedMath.SQRT2   = origMath.SQRT2 + (prng() - 0.5) * NOISE_MAG_CONST;
      spoofedMath.SQRT1_2 = 1 / spoofedMath.SQRT2;
    }

    // Keep logarithms and powers native by default. Firebase uses log ratios to size
    // trees and powers to encode numbers; tiny noise can drop whole fields
    // or corrupt hashes. Opt-in data math noise applies on realm creation,
    // matching the native worker policy; reload pages after changing it.
    // Trig / sqrt family: exportFunction so the page sees
    // `function <name>() { [native code] }` when it introspects.
    const TRIG_FNS = [
      "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
      "sinh", "cosh", "tanh", "asinh", "acosh", "atanh",
      "exp", "expm1", "sqrt", "cbrt", "hypot",
    ];
    if (Services.prefs.getBoolPref("cloakfox.opt.math_data_noise", false)) {
      TRIG_FNS.push("log", "log2", "log10", "log1p", "pow");
    }
    // The wrapped function is chrome-compartment (Cu.exportFunction). It
    // captures `orig` and `origMath` from the page compartment. When the
    // page calls Math.sin(0.5), the chrome wrapped fn gets `args` as a
    // chrome-side rest-spread Array. Calling `orig.apply(origMath, args)`
    // would invoke page-compartment Function.prototype.apply with a
    // chrome array — apply reads `args.length`, the Xray boundary blocks
    // it, and the page sees "Permission denied to access property
    // 'length'". Using `.call(...args)` instead spreads the args in the
    // chrome scope so each primitive marshals individually across the
    // boundary — works without explicit Cu.cloneInto.
    //
    // PURITY: noise is derived from (result, trigSeed) via Float64-bit
    // hashing — Math.sin(0.5) === Math.sin(0.5) holds. The earlier
    // implementation advanced `prng()` per call, which made repeated
    // calls on the same input return different values — a self-flagging
    // signal since real Math is spec-pure. We keep the master prng()
    // alive only for one-time initialization (constants); the trig
    // wrap uses input-deterministic hashing exclusively.
    // The process snapshot is invalidated when preferences are published. Read
    // the authoritative worker overlay lazily; parse only when its text changes.
    // Missing, invalid or zero seeds leave the native result unchanged.
    let lastCfg;
    let trigSeed = 0;
    const currentTrigSeed = () => {
      const liveSeeds = currentSeeds();
      const raw = liveSeeds[`cloakfox.s.cloak_cfg_${ucid}`] || "";
      if (raw !== lastCfg) {
        lastCfg = raw;
        trigSeed = 0;
        try {
          const configuredSeed = JSON.parse(raw)["math:trig_seed"];
          if (Number.isInteger(configuredSeed) && configuredSeed >= 0 &&
              configuredSeed <= 0xffffffff) {
            trigSeed = configuredSeed;
          }
        } catch (_e) { /* no usable overlay */ }
      }
      return trigSeed;
    };
    const _ab  = new ArrayBuffer(8);
    const _f64 = new Float64Array(_ab);
    const _u32 = new Uint32Array(_ab);
    const noise = (r, seed) => {
      _f64[0] = r;
      let h = (_u32[0] ^ _u32[1] ^ seed) >>> 0;
      h = Math.imul(h ^ (h >>> 16), 2246822507) >>> 0;
      h = Math.imul(h ^ (h >>> 13), 3266489909) >>> 0;
      h = (h ^ (h >>> 16)) >>> 0;
      return (h / 4294967296 - 0.5) * NOISE_MAG_TRIG;
    };
    for (const fn of TRIG_FNS) {
      const orig = origMath[fn];
      if (typeof orig !== "function") continue;
      const numericOrig = Math[fn];
      const realmSensitive = fn === "sin" || fn === "cos" || fn === "tan";
      const wrapped = Cu.exportFunction(function (...args) {
        // Numbers need no coercion and use the same engine intrinsic here.
        // Avoid a second realm crossing for each operation in animation loops.
        // Other inputs retain page-realm coercion and exception behavior.
        const r = (!realmSensitive || useFdlibm) && args.every(isNumber)
          ? numericOrig(...args) : orig.call(origMath, ...args);
        const seed = mathEnabled ? currentTrigSeed() : 0;
        return seed !== 0 && Number.isFinite(r) && !Number.isInteger(r)
          ? r + noise(r, seed) : r;
      }, pageWin, { functionName: fn, allowConstruct: false });
      // exportFunction yields name:"" and length:0; native Math methods
      // report their own name + arity (Math.sin.name==="sin",
      // Math.pow.length===2). Set both on the page-side function (Xray-waived
      // so the page sees them) with native function-descriptor flags, so a
      // name/length probe can't distinguish the wrapper.
      setNativeIdentity(wrapped, orig.name, orig.length);
      // Native Math methods are non-enumerable. A plain `spoofedMath[fn] =`
      // assignment makes them enumerable, so Object.keys(Math) leaks all 23
      // names (native returns []) — a trivial tamper tell. Define with the
      // native method descriptor flags instead (matches the constant copy).
      Object.defineProperty(spoofedMath, fn, {
        value: wrapped, writable: true, enumerable: false, configurable: true,
      });
    }

    // Restore the [object Math] brand. cloneInto({}) + copying own
    // property names omits Symbol.toStringTag, so without this
    // Object.prototype.toString.call(Math) would read "[object Object]"
    // — a tamper tell. spoofedMath lives in the page compartment, so
    // define the tag through a waived Xray to match native.
    try {
      Reflect.defineProperty(Cu.waiveXrays(spoofedMath), Symbol.toStringTag, {
        value: "Math",
        writable: false,
        enumerable: false,
        configurable: true,
      });
    } catch (_e) { /* best effort — brand restore is defense in depth */ }

    pageWin.Math = spoofedMath;
  }
}
