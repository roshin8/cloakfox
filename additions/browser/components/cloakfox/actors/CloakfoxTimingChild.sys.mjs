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

    // Wrap setTimeout — add 0..MAX_JITTER_MS to the scheduled delay.
    const origSetTimeout = pageWin.setTimeout;
    pageWin.setTimeout = Cu.exportFunction(function (handler, timeout, ...args) {
      const jitter = Math.floor(prng() * MAX_JITTER_MS);
      return origSetTimeout.call(this, handler, (timeout || 0) + jitter, ...args);
    }, pageWin, { defineAs: "setTimeout" });

    // Wrap setInterval — same treatment.
    const origSetInterval = pageWin.setInterval;
    pageWin.setInterval = Cu.exportFunction(function (handler, timeout, ...args) {
      const jitter = Math.floor(prng() * MAX_JITTER_MS);
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
  }
}
