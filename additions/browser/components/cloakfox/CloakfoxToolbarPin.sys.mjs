/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: auto-pin the cloakfox-shield browser_action button to the
 * navbar on first launch so the user actually sees it. Firefox's
 * default for newly-loaded WebExtension actions is to hide them in
 * the unified-extensions overflow panel; users have to right-click
 * → "Pin to toolbar" to get the icon out. For a built-in addon
 * that's the user's primary entry point, we want it visible by
 * default.
 *
 * Idempotent — `cloakfox.toolbar.pinned.v1` pref tracks whether we've
 * already pinned. After first launch the user can unpin freely; we
 * won't re-pin on subsequent starts.
 */

const ADDON_ID = "cloakfox-shield@cloakfox";
const PINNED_PREF = "cloakfox.toolbar.pinned.v1";

// Firefox's makeWidgetId convention: lowercase, replace non-[a-z0-9_-]
// with "_", then suffix "_-browser-action" for browser_action widgets.
function widgetId() {
  const encoded = ADDON_ID.toLowerCase().replace(/[^a-z0-9_-]/g, "_");
  return `${encoded}-browser-action`;
}

export function ensureCloakfoxPinned() {
  // Already pinned once — let the user's customization stick.
  if (Services.prefs.getBoolPref(PINNED_PREF, false)) return;

  const wid = widgetId();
  const { CustomizableUI } = ChromeUtils.importESModule(
    "resource:///modules/CustomizableUI.sys.mjs"
  );

  // The widget may not exist yet if the extension hasn't finished
  // loading. CustomizableUI.addListener fires onWidgetAdded for any
  // widget — we listen until ours appears, then place it.
  //
  // Returns true on any *terminal* outcome (placed, or already placed),
  // false only when the widget isn't registered yet and we should keep
  // waiting. Terminal outcomes set PINNED_PREF so we never re-run.
  const tryPin = () => {
    // Already has a placement (user moved it, or a prior run pinned it):
    // treat as done — record it and stop, don't leave the pref unset.
    if (CustomizableUI.getPlacementOfWidget(wid)) {
      Services.prefs.setBoolPref(PINNED_PREF, true);
      return true;
    }
    try {
      CustomizableUI.addWidgetToArea(wid, CustomizableUI.AREA_NAVBAR);
      Services.prefs.setBoolPref(PINNED_PREF, true);
      return true;
    } catch (_e) {
      return false;   // widget not registered yet
    }
  };

  if (tryPin()) return;

  const listener = {
    onWidgetAdded(addedId) {
      if (addedId !== wid) return;
      // Remove the listener on every terminal outcome so it can't leak
      // for the session; only a not-yet-registered widget keeps it live.
      if (tryPin()) {
        CustomizableUI.removeListener(listener);
      }
    },
  };
  CustomizableUI.addListener(listener);
}
