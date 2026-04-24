/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: navigator.requestMIDIAccess always rejects.
 *
 * MIDI device enumeration leaks attached hardware/driver names. The
 * vast majority of users have zero MIDI devices, so a permission-
 * denied rejection is indistinguishable from reality. Pages that
 * legitimately need MIDI (rare: web-MIDI controllers in browser-
 * based DAWs) get a clear error.
 *
 * Phase 2 port of inject/spoofers/devices/midi.ts.
 */

export class CloakfoxMidiChild extends JSWindowActorChild {
  handleEvent(event) {
    if (event.type !== "DOMDocElementInserted") return;
    try { this.#install(); } catch (_e) { /* never leak chrome:// */ }
  }

  #install() {
    const win = this.contentWindow;
    if (!win) return;
    if (!Services.prefs.getBoolPref("cloakfox.enabled", false)) return;

    const pageWin = win.wrappedJSObject;
    if (typeof pageWin.navigator?.requestMIDIAccess !== "function") return;

    pageWin.navigator.requestMIDIAccess = Cu.exportFunction(function () {
      return pageWin.Promise.reject(
        new pageWin.DOMException("Permission denied", "NotAllowedError")
      );
    }, pageWin, { defineAs: "requestMIDIAccess" });
  }
}
