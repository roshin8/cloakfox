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
    if (typeof pageWin.navigator?.getGamepads !== "function") return;

    // Return a 4-slot array of nulls, matching the standard "no
    // gamepad connected" shape. Must be cloneInto'd so the page
    // sees a page-compartment array, not an Xray-wrapped chrome one.
    const emptyGamepads = Cu.cloneInto([null, null, null, null], pageWin);

    pageWin.navigator.getGamepads = Cu.exportFunction(function () {
      return emptyGamepads;
    }, pageWin, { defineAs: "getGamepads" });
  }
}
