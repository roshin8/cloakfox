/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// Zoom Video SDK 2.5.0 / media 7.1.0.15306 selects its combined video/share
// worker for Chromium identities. Without a track processor it sends that
// worker yuvVideoFrame messages, which the worker closes as "not implemented".
// Use the SDK's existing canvas sender and render the already-authorized local
// stream directly. No capture starts, permission changes, transport changes,
// browser API replacements, or remote-player modifications occur here.
export class CloakfoxCoderPadMediaChild extends JSWindowActorChild {
  #timer = null;
  #require = null;
  #sdk = null;
  #seen = new WeakSet();
  #preview = null;
  #stopped = false;

  handleEvent(event) {
    if (event.type !== 'DOMDocElementInserted' || this.#timer !== null) return;
    if (!Services.prefs.getBoolPref('cloakfox.compat.coderpad_media', true)) return;
    try {
      this.#timer = this.contentWindow.setInterval(() => this.#tick(), 250);
      this.#tick();
    } catch (_) { this.didDestroy(); }
  }

  #tick() {
    if (this.#stopped) return;
    try {
      const page = this.contentWindow.wrappedJSObject;
      if (page.JsMediaSDK_Instance?.pkgVersion !== '7.1.0.15306') {
        this.#removePreview();
        return;
      }
      if (!this.#require) {
        if (typeof page.webpackChunkcoderpad?.push !== 'function') return;
        const entry = Cu.cloneInto([[-this.browsingContext.id], {}], page);
        entry[2] = Cu.exportFunction(require => {
          this.#require = Cu.waiveXrays(require);
        }, page);
        page.webpackChunkcoderpad.push(entry);
      }
      if (!this.#sdk) this.#discover();
      // Read only an existing client. createClient()/getMediaStream() can
      // initialize services; compatibility must never initialize a call.
      const client = this.#sdk?.videoClient;
      const instance = this.#mediaInstance(client?.stream);
      if (!instance || instance.isSupportVideoShare !== true ||
          instance.isSupportMediaStreamTrackProcessor !== false) {
        this.#removePreview();
        return;
      }
      if (instance.isVideoTagFrameAccessible === true) {
        instance.isVideoTagFrameAccessible = false;
      }
      this.#updatePreview(page, client, instance);
    } catch (_) { /* unsupported or navigating application: leave it alone */ }
  }

  #discover() {
    for (const [id, factory] of Object.entries(this.#require?.m || {})) {
      if (typeof factory !== 'function' || this.#seen.has(factory)) continue;
      this.#seen.add(factory);
      const source = factory.toString();
      if (!source.includes('createLocalVideoTrack') ||
          !source.includes('preloadDependentAssets')) continue;
      for (const value of Object.values(this.#require(id))) {
        if (value?.VERSION === '2.5.0' && typeof value.createClient === 'function') {
          this.#sdk = value;
          return;
        }
      }
    }
  }

  #mediaInstance(stream) {
    if (!stream || (typeof stream !== 'object' && typeof stream !== 'function')) return null;
    // Discover context by capability, without minified module IDs, export
    // names or Symbol descriptions. This is the existing SDK media context.
    for (const key of Object.getOwnPropertySymbols(stream)) {
      const inner = stream[key];
      if (!inner || (typeof inner !== 'object' && typeof inner !== 'function')) continue;
      for (const contextKey of Object.getOwnPropertySymbols(inner)) {
        const instance = inner[contextKey]?.mediaAgent?.instance;
        if (instance && 'isVideoTagFrameAccessible' in instance) return instance;
      }
    }
    return null;
  }

  #updatePreview(page, client, instance) {
    const user = client.getCurrentUserInfo?.();
    const stream = instance.videoCaptureValue?.videoCtrl?.srcObject;
    const player = Number.isSafeInteger(user?.userId) && user.userId > 0 && user.bVideoOn === true
      ? [...page.document.querySelectorAll('video-player')].find(
          node => node.getAttribute('node-id') === String(user.userId)) : null;
    if (!stream || !player) {
      this.#removePreview();
      return;
    }
    if (this.#preview?.parentNode !== player) {
      this.#removePreview();
      const preview = page.document.createElement('video');
      preview.setAttribute('data-cloakfox-camera-preview', '');
      preview.muted = true;
      preview.autoplay = true;
      preview.playsInline = true;
      preview.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:contain;z-index:1;background:black';
      player.append(preview);
      this.#preview = preview;
    }
    if (this.#preview.srcObject !== stream) {
      this.#preview.srcObject = stream;
      // Muted playback retains native autoplay policy. Never manufacture a
      // gesture or change permissions if the browser rejects playback.
      this.#preview.play().catch(() => {});
    }
  }

  #removePreview() {
    if (!this.#preview) return;
    try {
      this.#preview.srcObject = null;
      this.#preview.remove();
    } catch (_) {}
    this.#preview = null;
  }

  didDestroy() {
    this.#stopped = true;
    if (this.#timer !== null) {
      try { this.contentWindow.clearInterval(this.#timer); } catch (_) {}
      this.#timer = null;
    }
    this.#removePreview();
    this.#require = null;
    this.#sdk = null;
  }
}
