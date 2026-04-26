/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: WebRTC public-IPv4 spoof.
 *
 * Calls window.setWebRTCIPv4(<current public IPv4>) on every
 * DOMDocElementInserted. The value comes from CloakfoxWebRTCSync
 * (parent-side), which detected it via HTTP IP-echo and published
 * to sharedData. Result: WebRTC's ICE candidates report the same
 * public IP that HTTP traffic shows, regardless of how WebRTC's
 * interface enumeration would have gathered it. Closes the leak
 * windows that media.peerconnection.ice.default_address_only=true
 * doesn't cover (IPv6 leaks, split tunnels, transient VPN drops).
 *
 * Self-destructing setter: like setTimezone, the C++ WebIDL function
 * (patches/webrtc-ip-spoofing.patch) disables itself per
 * userContextId after the first call. Once called for a container,
 * the function is undefined on all subsequent windows in that
 * container — but the value persists in WebRTCIPManager. Multi-
 * call attempts are guarded with a typeof check.
 *
 * If the parent hasn't published a public IP yet (very first page
 * after launch races the ipify fetch), the actor silently no-ops.
 * Subsequent pages pick it up.
 */

export class CloakfoxWebRTCChild extends JSWindowActorChild {
  handleEvent(event) {
    if (event.type !== "DOMDocElementInserted") return;
    try { this.#install(); } catch (_e) { /* never leak chrome:// */ }
  }

  #install() {
    const win = this.contentWindow;
    if (!win) return;
    if (!Services.prefs.getBoolPref("cloakfox.enabled", false)) return;

    const pageWin = win.wrappedJSObject;

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
