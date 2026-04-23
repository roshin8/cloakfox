/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: keyboard-cadence spoofing per userContextId.
 *
 * Typing rhythm (inter-keystroke timing) is a behavioral fingerprint
 * that survives most spoofing because it's measured from page scripts
 * listening for keydown/keyup/keypress. This actor normalizes the
 * timestamps a page sees: events that arrive faster than a minimum
 * delay (30ms) get their .timeStamp nudged up so the reported cadence
 * is closer to a stable rhythm than the user's natural variation.
 *
 * Runs chrome-principal in the content process on DOMDocElementInserted.
 * Hooks EventTarget.prototype.addEventListener — specifically the key
 * event types — and wraps the listener with a timestamp-normalizer
 * derived from the per-container keyboard seed.
 *
 * Phase 2 of the cpp-first migration (see docs/cpp-first/MIGRATION-
 * RFC.md). Ported from the existing MAIN-world spoofer
 * additions/.../cloakfox-shield/src/inject/spoofers/keyboard/
 * cadence.ts. Port preserves the 30ms + 15ms-jitter defaults.
 */

const MIN_DELAY_MS = 30;
const MAX_JITTER_MS = 15;
const KEY_EVENTS = new Set(["keydown", "keyup", "keypress"]);

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

export class CloakfoxKeyboardChild extends JSWindowActorChild {
  handleEvent(event) {
    if (event.type !== "DOMDocElementInserted") return;
    try { this.#install(); } catch (_e) { /* never leak chrome:// */ }
  }

  #install() {
    const win = this.contentWindow;
    if (!win) return;
    if (!Services.prefs.getBoolPref("cloakfox.enabled", false)) return;

    // Each container gets its own seed. Derive from the master
    // keyboard_seed pref (base64 32 bytes) or fall back to
    // cloakfox.container.<ucid>.keyboard_seed specifically.
    const ucid = win.docShell?.browsingContext?.originAttributes?.userContextId ?? 0;
    const seedB64 = Services.prefs.getStringPref(
      `cloakfox.container.${ucid}.keyboard_seed`, ""
    );
    if (!seedB64) return;

    const prng = makePRNG(b64ToBytes(seedB64));
    const pageWin = win.wrappedJSObject;

    // Shared mutable state between all wrapped listeners.
    // Kept in chrome scope so page code can't observe / tamper.
    let lastEventTime = 0;

    // The cadence-normalizer. Runs per keyboard event before
    // delegating to the page's original listener.
    const normalize = (event) => {
      const now = pageWin.performance?.now?.() ?? Date.now();
      const elapsed = now - lastEventTime;
      if (elapsed < MIN_DELAY_MS && lastEventTime > 0) {
        // Nudge timeStamp so the page sees a minimum-delay cadence.
        try {
          Object.defineProperty(event, "timeStamp", {
            value: lastEventTime + MIN_DELAY_MS + prng() * MAX_JITTER_MS,
            writable: false,
            configurable: false,
          });
        } catch (_e) { /* event already has non-configurable timeStamp — best effort */ }
      }
      lastEventTime = now;
    };

    // Patch EventTarget.prototype.addEventListener via exportFunction
    // so the replacement stringifies as native code. Wrap the page's
    // listener with our normalizer only if it's a keyboard event.
    const origAdd = pageWin.EventTarget.prototype.addEventListener;
    const wrapped = Cu.exportFunction(function (type, listener, options) {
      if (KEY_EVENTS.has(String(type)) && typeof listener === "function") {
        const origListener = listener;
        // New listener function, exported back into the page
        // compartment so it appears native from the page's POV.
        const newListener = Cu.exportFunction(function (event) {
          normalize(event);
          return origListener.apply(this, arguments);
        }, pageWin);
        return origAdd.call(this, type, newListener, options);
      }
      return origAdd.call(this, type, listener, options);
    }, pageWin, { defineAs: "addEventListener" });

    // Known limitation (same as CloakfoxMath): descriptor flags on
    // pageWin.EventTarget.prototype don't fully lock across the Xray
    // boundary. Setting wrapped as the property value still works;
    // descriptor-probe detection is documented as future work.
    pageWin.EventTarget.prototype.addEventListener = wrapped;
  }
}
