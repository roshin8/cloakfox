/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// Site compatibility, not fingerprint masking. HackerRank saves the Zoom
// local participant ID after join(), but does not refresh it after failover.
// This actor is registered only for the top-level HTTPS /pair/ application.
// It changes no browser APIs, capture/permission behavior, media transport,
// editor state, remote participant IDs, or SDK internals.
//
// The application has no public recovery API. Discover the existing store
// and getAV getter by their capabilities, not generated bundle IDs/export
// names. If the site changes these capabilities, leave it untouched.
export class CloakfoxHackerRankMediaChild extends JSWindowActorChild {
  #timer = null;
  #pending = null;
  #require = null;
  #store = null;
  #getAV = null;
  #client = null;
  #handler = null;
  #seen = new WeakSet();
  #stopped = false;

  handleEvent(event) {
    if (event.type !== 'DOMDocElementInserted' || this.#timer !== null) return;
    if (!Services.prefs.getBoolPref('cloakfox.compat.hackerrank_media', true)) return;
    try {
      this.#timer = this.contentWindow.setInterval(() => this.#tick(), 500);
      this.#tick();
    } catch (_) { this.didDestroy(); }
  }

  #tick() {
    if (this.#stopped) return;
    try {
      const page = this.contentWindow.wrappedJSObject;
      if (!this.#require) {
        if (typeof page.webpackChunk_N_E?.push !== 'function') return;
        // Webpack's runtime callback; no script injection, fetch or page global.
        const entry = Cu.cloneInto([[-this.browsingContext.id], {}], page);
        entry[2] = Cu.exportFunction(require => {
          this.#require = Cu.waiveXrays(require);
        }, page);
        page.webpackChunk_N_E.push(entry);
      }
      if (!this.#require) return;
      if (!this.#store || !this.#getAV) this.#discover();
      if (!this.#store || !this.#getAV) return;
      const av = this.#getAV(); // Only reads the already initialized service.
      const client = av?.provider?.zmClient;
      if (client !== this.#client) {
        this.#detach();
        if (typeof client?.on !== 'function' || typeof client.off !== 'function' ||
            typeof client.getCurrentUserInfo !== 'function') return;
        this.#client = client;
        this.#handler = Cu.exportFunction(event => {
          try {
            if (event?.state !== 'Connected' || this.#stopped) return;
            // Let the site's connection handlers and join continuation run first.
            if (this.#pending !== null) return;
            this.#pending = this.contentWindow.setTimeout(() => {
              this.#pending = null;
              this.#reconcile();
            }, 0);
          } catch (_) { /* site compatibility must not escape into SDK callbacks */ }
        }, page);
        client.on('connection-change', this.#handler);
      }
      this.#reconcile(); // Also handles an already connected/replaced client.
    } catch (_) { /* not initialized yet, or an unsupported site version */ }
  }

  #discover() {
    for (const [id, factory] of Object.entries(this.#require.m || {})) {
      if (typeof factory !== 'function' || this.#seen.has(factory)) continue;
      this.#seen.add(factory);
      const source = factory.toString();
      const isStore = !this.#store && source.includes('setLocalZoomUserId') &&
        source.includes('incrementVideoRenderEpoch');
      const isService = !this.#getAV && source.includes('before using getAV()');
      if (!isStore && !isService) continue;
      const exports = this.#require(id);
      for (const value of Object.values(exports)) {
        if (isStore && typeof value?.getState === 'function' &&
            typeof value.subscribe === 'function') {
          const state = value.getState();
          if (typeof state?.setLocalZoomUserId === 'function' &&
              typeof state.incrementVideoRenderEpoch === 'function') this.#store = value;
        }
        if (isService && typeof value === 'function' && value.length === 0 &&
            value.toString().includes('before using getAV()')) this.#getAV = value;
      }
      if (this.#store && this.#getAV) return;
    }
  }

  #reconcile() {
    if (this.#stopped || !this.#client) return;
    try {
      const state = this.#store.getState();
      if (state.callStatus !== 'connected') return;
      const av = this.#getAV();
      if (av?.provider?.zmClient !== this.#client) return;
      const id = av.getLocalParticipantId();
      if (!Number.isSafeInteger(id) || id <= 0 ||
          this.#client.getCurrentUserInfo()?.userId !== id ||
          state.localZoomUserId === id) return;
      state.setLocalZoomUserId(id);
      state.incrementVideoRenderEpoch();
    } catch (_) { /* leave changed/unsupported applications alone */ }
  }

  #detach() {
    if (this.#pending !== null) {
      try { this.contentWindow.clearTimeout(this.#pending); } catch (_) {}
      this.#pending = null;
    }
    try { this.#client?.off('connection-change', this.#handler); } catch (_) {}
    this.#client = null;
    this.#handler = null;
  }

  didDestroy() {
    this.#stopped = true;
    if (this.#timer !== null) {
      try { this.contentWindow.clearInterval(this.#timer); } catch (_) {}
      this.#timer = null;
    }
    this.#detach();
    this.#require = this.#store = this.#getAV = null;
  }
}
