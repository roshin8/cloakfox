/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// Presentation is a trusted UI preference, never an engine capability or a
// privacy opt-out. The controller must apply the same release gate in either
// mode. Existing pages keep their mode until an explicit switch commits.
function presentationPref(userContextId) {
  if (!Number.isInteger(userContextId) || userContextId < 0 || userContextId >= 2147483647) {
    throw new Error("Invalid engine preference container");
  }
  return `cloakfox.container.${userContextId}.chromium_presentation`;
}

export function getChromiumPresentation(userContextId) {
  const value = Services.prefs.getStringPref(presentationPref(userContextId), "same-window");
  return value === "separate-window" ? value : "same-window";
}

export function setChromiumPresentation(userContextId, value) {
  const pref = presentationPref(userContextId);
  if (value !== "same-window" && value !== "separate-window") {
    throw new Error("Invalid Chromium presentation preference");
  }
  Services.prefs.setStringPref(pref, value);
}
