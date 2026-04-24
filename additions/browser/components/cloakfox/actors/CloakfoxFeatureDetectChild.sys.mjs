/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: small navigator-property fakes for feature-detection
 * fingerprinting (webdriver, doNotTrack, globalPrivacyControl,
 * pdfViewerEnabled, javaEnabled). Most of these are 1-bit signals
 * that anti-bot scripts read; pinning them to "human-realistic"
 * values is independent of container, so no per-container seed.
 *
 * Phase 2 port of inject/spoofers/features/feature-detection.ts.
 * Skipped CSS.supports() and document.implementation.hasFeature()
 * portions — they're noisy with no measurable fingerprint impact.
 */

const FAKES = [
  ["webdriver", false],          // bot detection — must look like a real human session
  ["doNotTrack", "1"],           // DNT enabled
  ["globalPrivacyControl", true],// GPC enabled
  ["pdfViewerEnabled", true],    // common
  ["onLine", true],              // pinned online
  ["cookieEnabled", true],       // pinned enabled
];

export class CloakfoxFeatureDetectChild extends JSWindowActorChild {
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
    if (!navProto) return;

    for (const [prop, value] of FAKES) {
      try {
        Object.defineProperty(navProto, prop, {
          get: Cu.exportFunction(function () { return value; }, pageWin),
          configurable: true,
          enumerable: true,
        });
      } catch (_e) { /* property might be non-configurable */ }
    }

    // navigator.javaEnabled() — spec-deprecated, returns false today.
    if (typeof pageWin.navigator?.javaEnabled === "function") {
      pageWin.navigator.javaEnabled = Cu.exportFunction(function () {
        return false;
      }, pageWin, { defineAs: "javaEnabled" });
    }
  }
}
