/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: Error.stack and Error.stackTraceLimit normalization.
 *
 * Stack traces leak browser version, OS, and extension paths via
 * the file:line:col format. We don't go as far as the original
 * extension (which replaced window.Error entirely — risky because
 * `err instanceof Error` breaks if the prototype chain isn't wired
 * back) — instead we just:
 *
 *   1. Pin Error.stackTraceLimit to 10 (a common value).
 *   2. Wrap Error.captureStackTrace if present (V8-style — defined
 *      in JS engines that mimic Chrome).
 *
 * Skipped (deferred): replacing the Error constructor for stack
 * format normalization. That's where the Firefox-vs-Chrome stack
 * format difference shows up, but it requires careful prototype
 * surgery to avoid breaking error-handling code on real pages.
 *
 * Phase 2 partial port of inject/spoofers/errors/stack-trace.ts.
 */

export class CloakfoxErrorsChild extends JSWindowActorChild {
  handleEvent(event) {
    if (event.type !== "DOMDocElementInserted") return;
    try { this.#install(); } catch (_e) { /* never leak chrome:// */ }
  }

  #install() {
    const win = this.contentWindow;
    if (!win) return;
    if (!Services.prefs.getBoolPref("cloakfox.enabled", false)) return;

    const pageWin = win.wrappedJSObject;

    // Pin stackTraceLimit. Pages that read `Error.stackTraceLimit` see
    // a stable, common value rather than the engine default.
    try {
      Object.defineProperty(pageWin.Error, "stackTraceLimit", {
        value: 10,
        writable: true,
        configurable: true,
      });
    } catch (_e) { /* best effort */ }

    // captureStackTrace: present on V8/Chrome (and SpiderMonkey too in
    // recent Firefox). When present, normalize whatever it produces by
    // calling the original then truncating to 10 lines.
    if (typeof pageWin.Error?.captureStackTrace === "function") {
      const origCapture = pageWin.Error.captureStackTrace;
      pageWin.Error.captureStackTrace = Cu.exportFunction(function (target, ctor) {
        origCapture.call(this, target, ctor);
        try {
          if (typeof target.stack === "string") {
            const lines = target.stack.split("\n");
            if (lines.length > 11) {
              target.stack = lines.slice(0, 11).join("\n");
            }
          }
        } catch (_e) { /* best effort */ }
      }, pageWin, { defineAs: "captureStackTrace" });
    }
  }
}
