/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: event-loop timing jitter per userContextId.
 *
 * Amazon and advanced fingerprinters measure the delay between
 * scheduling a setTimeout / setInterval / requestAnimationFrame
 * callback and the callback firing — that delay reflects CPU
 * performance and system load and is a stable fingerprint across
 * sessions.
 *
 * Adds small jitter (up to 2ms) to the scheduled delay, plus sub-ms
 * noise to rAF timestamps, to break determinism without breaking
 * functionality.
 *
 * Phase 2 port of inject/spoofers/timing/event-loop.ts. Must stay JS
 * (inventory.md): the C++ timer code lives in nsITimer/nsIEventTarget
 * which is too low-level to instrument per-origin.
 */

const MAX_JITTER_MS = 2;
const RAF_NOISE_MS = 0.1;

function makePRNG(seedBytes) {
  let s0 = 0n, s1 = 0n;
  for (let i = 0; i < 16; i++) s0 = (s0 << 8n) | BigInt(seedBytes[i] || 0);
  for (let i = 16; i < 32; i++) s1 = (s1 << 8n) | BigInt(seedBytes[i] || 0);
  const MASK = (1n << 64n) - 1n;
  return function next() {
    let x = s0; const y = s1;
    s0 = y;
    x = (x ^ (x << 23n)) & MASK;
    s1 = (x ^ y ^ (x >> 17n) ^ (y >> 26n)) & MASK;
    return Number((s1 + y) & ((1n << 53n) - 1n)) / Number(1n << 53n);
  };
}

function b64ToBytes(b64) {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export class CloakfoxTimingChild extends JSWindowActorChild {
  handleEvent(event) {
    if (event.type !== "DOMDocElementInserted") return;
    try { this.#install(); } catch (_e) { /* never leak chrome:// */ }
  }

  #install() {
    const win = this.contentWindow;
    if (!win) return;
    if (!Services.prefs.getBoolPref("cloakfox.enabled", false)) return;

    // Per-container seed from sharedData (parent-published — see
    // CloakfoxSeedSync). cloakfox.container.* prefs don't auto-sync.
    const seeds = Services.cpmm.sharedData.get("cloakfox-seeds") || {};
    const ucid = win.docShell?.browsingContext?.originAttributes?.userContextId ?? 0;
    const seedB64 = seeds[`cloakfox.container.${ucid}.timing_seed`] || "";
    if (!seedB64) return;

    const prng = makePRNG(b64ToBytes(seedB64));
    const pageWin = win.wrappedJSObject;

    // Wrap setTimeout — add 0..MAX_JITTER_MS (inclusive) to the
    // scheduled delay. Math.floor(prng() * (N+1)) yields 0..N inclusive
    // since prng() ∈ [0,1). The previous form (* MAX_JITTER_MS) was an
    // off-by-one and capped jitter at MAX_JITTER_MS - 1, which with
    // MAX_JITTER_MS = 2 meant only {0, 1}.
    const origSetTimeout = pageWin.setTimeout;
    pageWin.setTimeout = Cu.exportFunction(function (handler, timeout, ...args) {
      const jitter = Math.floor(prng() * (MAX_JITTER_MS + 1));
      return origSetTimeout.call(this, handler, (timeout || 0) + jitter, ...args);
    }, pageWin, { defineAs: "setTimeout" });

    // Wrap setInterval — same treatment.
    const origSetInterval = pageWin.setInterval;
    pageWin.setInterval = Cu.exportFunction(function (handler, timeout, ...args) {
      const jitter = Math.floor(prng() * (MAX_JITTER_MS + 1));
      return origSetInterval.call(this, handler, (timeout || 0) + jitter, ...args);
    }, pageWin, { defineAs: "setInterval" });

    // Wrap requestAnimationFrame — add sub-ms noise to the callback's
    // timestamp argument without delaying the actual frame.
    const origRAF = pageWin.requestAnimationFrame;
    if (typeof origRAF === "function") {
      pageWin.requestAnimationFrame = Cu.exportFunction(function (callback) {
        return origRAF.call(this, Cu.exportFunction(function (ts) {
          return callback.call(this, ts + prng() * RAF_NOISE_MS);
        }, pageWin));
      }, pageWin, { defineAs: "requestAnimationFrame" });
    }

    // Wrap performance.now — add deterministic per-ms-bucket fractional
    // jitter so the JS-visible reading looks high-resolution despite
    // Firefox's underlying 1ms quantization (privacy.reduceTimerPrecision).
    //
    // Why deterministic per bucket: performance.now is required by spec
    // to be monotonic-non-decreasing. Using a hash of the bucket id
    // makes repeated calls in the same 1ms bucket return the same
    // jittered value. That alone only preserves monotonicity when the
    // raw reading is whole-ms (privacy.reduceTimerPrecision ON). When
    // that pref is OFF the raw reading is sub-ms, so a high-jitter
    // bucket followed by a low-jitter bucket could go backwards across
    // a bucket boundary. To guarantee non-decreasing output regardless
    // of the pref, we additionally clamp each return to be ≥ the last
    // value we returned (tracked in the closure below).
    //
    // Default ON. Power users wanting visibly Tor-style coarse precision
    // (the "I'm a privacy browser" signal as deterrent) can flip
    // cloakfox.opt.timer_high_precision_jitter = false.
    if (Services.prefs.getBoolPref("cloakfox.opt.timer_high_precision_jitter", true)) {
      const origPerfNow = pageWin.performance.now;
      // Knuth multiplicative hash — fast deterministic 32-bit mix.
      const bucketJitter = (ms) => {
        const x = (Math.imul(ms | 0, 2654435761) ^ 0xdeadbeef) >>> 0;
        return (x % 1000) / 1000;  // 0..0.999
      };
      let lastReturned = -Infinity;
      const wrapped = Cu.exportFunction(function () {
        const orig = origPerfNow.call(this);
        let val = orig + bucketJitter(orig);
        // Clamp to keep the sequence monotonically non-decreasing even
        // when the raw reading is sub-ms (reduceTimerPrecision OFF).
        if (val < lastReturned) val = lastReturned;
        lastReturned = val;
        return val;
      }, pageWin);
      // Define on Performance.PROTOTYPE (where native now() lives), not the
      // instance — an own `now` on the performance object would leak via
      // Object.keys(performance)/hasOwnProperty (native is inherited). Native
      // prototype flags are {writable:true, enumerable:true, configurable:true}.
      Object.defineProperty(pageWin.Performance.prototype, "now", {
        value: wrapped, writable: true, enumerable: true, configurable: true,
      });
    }
  }
}
