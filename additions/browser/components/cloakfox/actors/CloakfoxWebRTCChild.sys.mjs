/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Optional reported-address alignment from parent-side IP lookup.
 * This is not network routing or a VPN kill switch. Explicit native
 * configuration still works independently of this optional actor path.
 */

export class CloakfoxWebRTCChild extends JSWindowActorChild {
  handleEvent(event) {
    if (event.type !== "DOMDocElementInserted") return;
    try { this.#install(); } catch (_e) { /* never leak chrome:// */ }
  }

  #install() {
    const win = this.contentWindow;
    if (!win) return;
    if (!Services.prefs.getBoolPref("cloakfox.enabled", false) ||
        !Services.prefs.getBoolPref("cloakfox.webrtc.ip_lookup.enabled", false)) return;

    // Chrome-only WebIDL setters are available through the Xray view.
    const pageWin = win;

    const ipv4 = Services.cpmm.sharedData.get("cloakfox-public-ipv4");
    if (ipv4 && typeof pageWin.setWebRTCIPv4 === "function") {
      try { pageWin.setWebRTCIPv4(ipv4); } catch (_e) { /* best effort */ }
    }

    const ipv6 = Services.cpmm.sharedData.get("cloakfox-public-ipv6");
    if (ipv6 && typeof pageWin.setWebRTCIPv6 === "function") {
      try { pageWin.setWebRTCIPv6(ipv6); } catch (_e) { /* best effort */ }
    }
  }
}
