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
  // doNotTrack / globalPrivacyControl are deliberately NOT faked here. Pinning
  // them in JS created contradictions a server or a worker can see: the page
  // was told DNT=1 / GPC=true while no DNT or Sec-GPC header was sent (their
  // prefs default off) and workers — which actors cannot reach — still reported
  // the real values. GPC is now enabled natively via prefs in cloakfox.cfg so
  // window, worker and header agree; DNT stays at Firefox's default
  // "unspecified", which is both the majority value and header-consistent.
  ["pdfViewerEnabled", true],    // common
  ["onLine", true],              // pinned online
  ["cookieEnabled", true],       // pinned enabled
];

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
        // Native WebIDL getter reports name "get <prop>" length 0; match it so
        // a getOwnPropertyDescriptor(...).get.name probe can't spot the wrapper.
        const getter = Cu.exportFunction(function () { return value; }, pageWin);
        setNativeIdentity(getter, `get ${prop}`, 0);
        Object.defineProperty(navProto, prop, {
          get: getter,
          configurable: true,
          enumerable: true,
        });
      } catch (_e) { /* property might be non-configurable */ }
    }

    // navigator.javaEnabled() — spec-deprecated, returns false today.
    // Define on the prototype (like the FAKES above), not the instance —
    // instance assignment leaks an own enumerable prop via
    // Object.keys(navigator) (stock Firefox returns []).
    if (typeof navProto.javaEnabled === "function") {
      const orig = navProto.javaEnabled;
      const wrapped = Cu.exportFunction(function () { return false; }, pageWin);
      setNativeIdentity(wrapped, orig.name, orig.length);
      Object.defineProperty(navProto, "javaEnabled", {
        value: wrapped, writable: true, enumerable: true, configurable: true,
      });
    }
  }
}
