/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: per-container timezone spoof.
 *
 * Calls window.setTimezone(<IANA>) at every DOMDocElementInserted.
 * The setter is a self-destructing C++ WebIDL function from
 * patches/timezone-spoofing.patch — exposed once per userContextId,
 * stored in RoverfoxStorageManager, then disabled. Subsequent
 * windows in the same userContextId see the persisted timezone
 * (Date / Intl.DateTimeFormat / getTimezoneOffset all read from it)
 * without any per-window JS work.
 *
 * Default value: UTC for every container without explicit config.
 * UTC is the privacy-browser standard (matches Tor / Brave strict)
 * — accepts the "I'm hiding my timezone" signal in exchange for
 * not leaking real OS timezone, which is a stable per-user signal
 * that survives VPNs, container isolation, and cookie clears.
 *
 * Per-container override: set cloakfox.container.<ucid>.timezone to
 * any IANA string (e.g. "America/New_York", "Europe/Berlin"). Read
 * from sharedData (CloakfoxSeedSync). The about:cloakfox UI is the
 * intended place to write this.
 *
 * Note: Firefox has no built-in pref equivalent — `intl.timezone.
 * override` doesn't exist; tested empirically and confirmed via grep
 * in modules/libpref/init/all.js. The setTimezone WebIDL setter is
 * the only way to override timezone without resistFingerprinting.
 */

const DEFAULT_TIMEZONE = "UTC";

export class CloakfoxTimezoneChild extends JSWindowActorChild {
  handleEvent(event) {
    if (event.type !== "DOMDocElementInserted") return;
    try { this.#install(); } catch (_e) { /* never leak chrome:// */ }
  }

  #install() {
    const win = this.contentWindow;
    if (!win) return;
    if (!Services.prefs.getBoolPref("cloakfox.enabled", false)) return;

    const seeds = Services.cpmm.sharedData.get("cloakfox-seeds") || {};
    const ucid = win.docShell?.browsingContext?.originAttributes?.userContextId ?? 0;
    const tz = seeds[`cloakfox.container.${ucid}.timezone`] || DEFAULT_TIMEZONE;

    const pageWin = win.wrappedJSObject;
    // setTimezone is exposed by patches/timezone-spoofing.patch as a
    // [Func=...] gated WebIDL method on Window. Once called, the C++
    // TimezoneManager marks it disabled for this userContextId, so on
    // subsequent windows in the same container the function evaluates
    // to undefined. That's the expected pattern — typeof check guards.
    if (typeof pageWin.setTimezone !== "function") return;

    try {
      pageWin.setTimezone(tz);
    } catch (_e) { /* function may have been disabled mid-flight */ }
  }
}
