/**
 * Phase 3 proof-of-concept: plant a getter into MAIN from ISOLATED using
 * Firefox's `exportFunction` API. The planted function appears native to
 * any page script inspecting it and leaves no `moz-extension://...`
 * references in stack traces.
 *
 * This file exists to document and exercise the pattern — it is NOT
 * wired into content/index.ts by default because every property we'd
 * target here is already handled by C++ (hardwareConcurrency via
 * NavigatorManager, etc.). Phase 3 starts paying off when we move
 * spoofers that *don't* have C++ coverage (Math constants, keyboard
 * cadence, WebRTC SDP munging, DOMRect jitter, storage estimate, etc.)
 * which currently have no choice but to run in MAIN.
 *
 * Usage from content/index.ts (once wired):
 *
 *   import { installNativeGetter } from './spoofers/example-native-getter';
 *   const pageWin = (window as any).wrappedJSObject;
 *   installNativeGetter(
 *     pageWin,
 *     pageWin.Navigator.prototype,
 *     'hardwareConcurrency',
 *     () => 8,
 *   );
 *   handled.add('navigator.hardwareConcurrency');
 *
 * Then MAIN's initializeSpoofers skips hardwareConcurrency because
 * preCoreHandled contains that signal — identical to the C++ skip path.
 */

// `exportFunction` and `cloneInto` are globals in Firefox content-script
// sandboxes. No import; declare the type so TS doesn't complain.
declare const exportFunction: <F extends (...args: any[]) => any>(
  func: F,
  targetScope: object,
  options?: { defineAs?: string; allowCrossOriginArguments?: boolean },
) => F;

/**
 * Plant a getter on a MAIN-world prototype from the ISOLATED caller.
 *
 * @param pageWin      `window.wrappedJSObject` from ISOLATED — the
 *                      MAIN compartment we're exporting INTO.
 * @param targetProto   Prototype object in MAIN to install on
 *                      (e.g. `pageWin.Navigator.prototype`).
 * @param name          Property name.
 * @param valueFn       Getter body. Closes over ISOLATED's scope — do
 *                      not return references to ISOLATED-only objects
 *                      (they'd hit Xray barriers). Return primitives
 *                      or `cloneInto`'d values.
 */
export function installNativeGetter(
  pageWin: any,
  targetProto: any,
  name: string,
  valueFn: () => unknown,
): void {
  // `defineAs` sets the exported function's `.name` — affects what
  // `.toString()` reports. Firefox-exported functions stringify as
  // `function <name>() { [native code] }` which is what real host
  // getters look like.
  const exportedGetter = exportFunction(valueFn, pageWin, { defineAs: `get ${name}` });

  try {
    Object.defineProperty(targetProto, name, {
      get: exportedGetter,
      configurable: true,
      enumerable: true,
    });
  } catch {
    // Some properties are non-configurable on built-in prototypes
    // (especially strict-mode targets like Math constants). The
    // caller has to handle those via alternative paths — either
    // replacing the holder object (the Math approach we took in MAIN)
    // or using a Proxy at a higher level.
  }
}
