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

// Cu.exportFunction yields a page-side function with name:"" and length:0.
// Native methods report their own name + arity; set both on the page object
// (Xray-waived) with native function-property flags so a name/length probe
// can't spot the wrapper.
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

    // Per-container seed from sharedData (parent-published — see
    // CloakfoxSeedSync). cloakfox.container.* prefs don't auto-sync.
    const seeds = Services.cpmm.sharedData.get("cloakfox-seeds") || {};
    const ucid = win.docShell?.browsingContext?.originAttributes?.userContextId ?? 0;
    const seedB64 = seeds[`cloakfox.container.${ucid}.keyboard_seed`] || "";
    if (!seedB64) return;

    const prng = makePRNG(b64ToBytes(seedB64));
    const pageWin = win.wrappedJSObject;

    // Per-event nudged timestamps, held chrome-side and surfaced through the
    // INHERITED Event.prototype.timeStamp getter below. Writing the nudged
    // value as an own property on the event instance would leak: native
    // timeStamp is an inherited accessor, so event.hasOwnProperty("timeStamp")
    // is false and getOwnPropertyDescriptor(event, "timeStamp") is undefined —
    // an own data prop flips both, a tell on the very events we touch. Keyed by
    // the Xray-waived event so set/get see the same identity.
    const nudged = new WeakMap();
    const evProto = pageWin.Event.prototype;
    const origTsGetter =
      Object.getOwnPropertyDescriptor(evProto, "timeStamp")?.get;
    if (origTsGetter) {
      const tsGetter = Cu.exportFunction(function () {
        const w = Cu.waiveXrays(this);
        return nudged.has(w) ? nudged.get(w) : origTsGetter.call(this);
      }, pageWin);
      // Native accessor reports name "get timeStamp" length 0; match it.
      setNativeIdentity(tsGetter, "get timeStamp", 0);
      try {
        // Native Event.prototype.timeStamp is {enumerable:true, configurable:true}.
        Object.defineProperty(evProto, "timeStamp", {
          get: tsGetter, enumerable: true, configurable: true,
        });
      } catch (_e) { /* non-configurable on some builds — best effort */ }
    }

    // Shared mutable state between all wrapped listeners.
    // Kept in chrome scope so page code can't observe / tamper.
    let lastEventTime = 0;

    // The cadence-normalizer. Runs per keyboard event before
    // delegating to the page's original listener.
    const normalize = (event) => {
      const now = pageWin.performance?.now?.() ?? Date.now();
      const elapsed = now - lastEventTime;
      if (elapsed < MIN_DELAY_MS && lastEventTime > 0) {
        // Record the nudged cadence value; served via the prototype getter so
        // no own property lands on the event instance.
        nudged.set(Cu.waiveXrays(event),
                   lastEventTime + MIN_DELAY_MS + prng() * MAX_JITTER_MS);
      }
      lastEventTime = now;
    };

    // Registry mapping an original page listener to the wrapper we
    // actually registered, so removeEventListener can find and remove
    // it. Keyed per (target, type, capture) to mirror native semantics:
    // the same listener on different targets — or with different capture
    // flags — is a distinct registration. WeakMaps keep this from
    // retaining targets/listeners past their lifetime.
    const perTarget = new WeakMap();
    const captureFlag = (options) =>
      (typeof options === "object" && options !== null)
        ? !!options.capture
        : !!options;
    const wrapperMapFor = (target, type, capture) => {
      let byKey = perTarget.get(target);
      if (!byKey) { byKey = new Map(); perTarget.set(target, byKey); }
      const key = `${type}|${capture}`;
      let wm = byKey.get(key);
      if (!wm) { wm = new WeakMap(); byKey.set(key, wm); }
      return wm;
    };

    // Patch EventTarget.prototype.addEventListener via exportFunction
    // so the replacement stringifies as native code. Wrap the page's
    // listener with our normalizer only if it's a keyboard event.
    const origAdd = pageWin.EventTarget.prototype.addEventListener;
    const wrapped = Cu.exportFunction(function (type, listener, options) {
      if (KEY_EVENTS.has(String(type)) && typeof listener === "function") {
        const capture = captureFlag(options);
        const wm = wrapperMapFor(this, String(type), capture);
        // Mirror native dedup: adding an identical (target, type,
        // listener, capture) registration is a no-op, so don't stack a
        // second wrapper.
        if (wm.has(listener)) return undefined;
        const origListener = listener;
        // New listener function, exported back into the page
        // compartment so it appears native from the page's POV.
        const newListener = Cu.exportFunction(function (event) {
          normalize(event);
          return origListener.apply(this, arguments);
        }, pageWin);
        wm.set(listener, newListener);
        return origAdd.call(this, type, newListener, options);
      }
      return origAdd.call(this, type, listener, options);
    }, pageWin);

    // Patch removeEventListener to unregister the wrapper we swapped in.
    // Without this the native remove can't match our wrapper, so key
    // listeners leak and identity-dedup breaks.
    const origRemove = pageWin.EventTarget.prototype.removeEventListener;
    const wrappedRemove = Cu.exportFunction(function (type, listener, options) {
      if (KEY_EVENTS.has(String(type)) && typeof listener === "function") {
        const capture = captureFlag(options);
        const wm = wrapperMapFor(this, String(type), capture);
        const newListener = wm.get(listener);
        if (newListener) {
          wm.delete(listener);
          return origRemove.call(this, type, newListener, options);
        }
      }
      return origRemove.call(this, type, listener, options);
    }, pageWin);

    // addEventListener/removeEventListener are existing own writable props
    // of EventTarget.prototype, so assigning the value preserves their
    // (non-enumerable) descriptor flags — no Object.keys leak. But the
    // exported wrappers report name:"" length:0, so copy the native
    // identity (name + arity) onto them first.
    setNativeIdentity(wrapped, origAdd.name, origAdd.length);
    setNativeIdentity(wrappedRemove, origRemove.name, origRemove.length);
    pageWin.EventTarget.prototype.addEventListener = wrapped;
    pageWin.EventTarget.prototype.removeEventListener = wrappedRemove;
  }
}
