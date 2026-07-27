/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: navigator.getGamepads() stub per userContextId.
 *
 * Connected gamepads are enumerable via `navigator.getGamepads()` and
 * their IDs leak driver/hardware info. Replace the return with a
 * no-gamepad array (4 nulls — the standard MDN shape). Most pages
 * don't use the gamepad API at all; the handful that do will just
 * see "no gamepad connected," which is indistinguishable from
 * reality for the vast majority of users.
 *
 * Phase 2 port of inject/spoofers/devices/gamepad.ts. Must-stay-JS
 * per inventory.md: the C++ gamepad service is complex and per-
 * process; instrumenting it would add risk. JS override is simpler.
 */

// Cu.exportFunction yields a page-side function with name:"" and length:0.
// Native methods report their own name + arity, so a probe reading
// fn.name / fn.length can spot the wrapper. Set both on the page object
// (Xray-waived) with native function-property flags.
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

export class CloakfoxGamepadChild extends JSWindowActorChild {
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
    if (typeof navProto?.getGamepads !== "function") return;

    // Return a 4-slot array of nulls, matching the standard "no
    // gamepad connected" shape. Real getGamepads() returns a fresh
    // snapshot each call, so clone a NEW page-compartment array per
    // invocation rather than sharing one mutable reference (a page
    // could otherwise mutate the shared array and observe it later).
    const orig = navProto.getGamepads;
    const wrapped = Cu.exportFunction(function () {
      return Cu.cloneInto([null, null, null, null], pageWin);
    }, pageWin);
    setNativeIdentity(wrapped, orig.name, orig.length);
    // Define on the PROTOTYPE with native flags (methods are enumerable
    // on Navigator.prototype), not the instance. Instance assignment
    // would add an own enumerable property, leaking it via
    // Object.keys(navigator) — stock Firefox returns []. On the prototype
    // the method stays inherited and the tamper is invisible.
    Object.defineProperty(navProto, "getGamepads", {
      value: wrapped, writable: true, enumerable: true, configurable: true,
    });
  }
}
