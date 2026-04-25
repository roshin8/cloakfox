/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: fake window.history.length per userContextId.
 *
 * Real browsing sessions have 3–50+ history entries per tab. An
 * automated or freshly-opened tab has 1. Fingerprinters read
 * history.length as a signal of "real browsing session" vs
 * "automation/bot". Replacing the value with a plausible fake
 * breaks that signal without affecting functionality (no page
 * code navigates to history[-N] in practice).
 *
 * Phase 2 port of inject/spoofers/navigator/tab-history.ts.
 * Must-stay-JS per inventory.md: window.history.length is
 * read-only, can only be overridden via JS getter. No C++ path.
 */

const PLAUSIBLE_LENGTHS = [3, 4, 5, 6, 7, 8, 10, 12, 15, 18, 22, 28, 35, 42, 50];

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

export class CloakfoxTabHistoryChild extends JSWindowActorChild {
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
    // TabHistory reuses math_seed since it only needs one stable
    // per-container pick.
    const seeds = Services.cpmm.sharedData.get("cloakfox-seeds") || {};
    const ucid = win.docShell?.browsingContext?.originAttributes?.userContextId ?? 0;
    const seedB64 = seeds[`cloakfox.container.${ucid}.math_seed`] || "";
    if (!seedB64) return;

    const prng = makePRNG(b64ToBytes(seedB64));
    const idx = Math.floor(prng() * PLAUSIBLE_LENGTHS.length);
    const fakeLength = PLAUSIBLE_LENGTHS[idx];

    const pageWin = win.wrappedJSObject;
    // Replace the History.prototype.length getter with an
    // exportFunction'd replacement. Descriptor-leak caveat applies
    // (same as Math and Keyboard actors).
    try {
      const getter = Cu.exportFunction(function () {
        return fakeLength;
      }, pageWin, { defineAs: "get length" });
      Object.defineProperty(pageWin.History.prototype, "length", {
        get: getter,
        configurable: true,
      });
    } catch (_e) { /* best effort */ }
  }
}
