/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: hide navigator.gpu / WebGPU support.
 *
 * WebGPU exposes detailed GPU adapter info (vendor, architecture,
 * device, dozens of limits + features) — a strong fingerprint. The
 * existing extension implementation faked the values with a curated
 * GPU profile list (~370 lines). For the chrome-actor port, we go
 * with the simpler approach: claim WebGPU isn't supported by
 * setting navigator.gpu = undefined.
 *
 * Most fingerprinters expect WebGPU to be unavailable on non-Chrome
 * browsers and only use it as a "yes/no" signal — so claiming "no"
 * is plausible. Sites that actually need WebGPU (rare in 2026:
 * niche graphics demos) get a feature-detect failure and either
 * fall back to WebGL or skip the feature entirely.
 *
 * Future enhancement: port the full GPU-profile spoofer for users
 * who actually want WebGPU functional but obfuscated.
 *
 * Phase 2 port of inject/spoofers/graphics/webgpu.ts (simplified).
 */

// A native WebIDL getter reports name "get <prop>" and length 0; an
// exportFunction getter reports name:"" length:0 and leaks the wrapper. Copy
// the native identity onto the page-side getter (Xray-waived).
function setGetterIdentity(getterFn, prop) {
  const waived = Cu.waiveXrays(getterFn);
  try {
    Object.defineProperty(waived, "name", {
      value: `get ${prop}`, writable: false, enumerable: false, configurable: true,
    });
    Object.defineProperty(waived, "length", {
      value: 0, writable: false, enumerable: false, configurable: true,
    });
  } catch (_e) { /* best effort — identity match is defense in depth */ }
  return getterFn;
}

export class CloakfoxWebGPUChild extends JSWindowActorChild {
  handleEvent(event) {
    if (event.type !== "DOMDocElementInserted") return;
    try { this.#install(); } catch (_e) { /* never leak chrome:// */ }
  }

  #install() {
    const win = this.contentWindow;
    if (!win) return;
    if (!Services.prefs.getBoolPref("cloakfox.enabled", false)) return;

    const pageWin = win.wrappedJSObject;
    const navProto = pageWin.Navigator?.prototype;
    if (!navProto || !("gpu" in navProto)) return;

    // Replace the navigator.gpu getter with one that returns undefined.
    // Pages that feature-detect via `'gpu' in navigator` still see true,
    // but `navigator.gpu` evaluates to undefined → adapter requests fail
    // with the same shape as a non-WebGPU browser.
    //
    // Define on the PROTOTYPE (where the native gpu getter lives), not the
    // instance — an own accessor on navigator would leak via
    // Object.keys(navigator) (stock Firefox returns []). Native prototype
    // flags are {enumerable:true, configurable:true}.
    try {
      const getter = Cu.exportFunction(function () { return undefined; }, pageWin);
      setGetterIdentity(getter, "gpu");
      Object.defineProperty(navProto, "gpu", {
        get: getter,
        configurable: true,
        enumerable: true,
      });
    } catch (_e) { /* property may be non-configurable on some builds */ }
  }
}
