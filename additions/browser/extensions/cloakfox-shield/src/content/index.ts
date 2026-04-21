/**
 * Content Script - Message bridge between page context and background.
 *
 * In MV3, inject/index.js runs directly in the page context via world:"MAIN".
 * This content script only bridges messages since the page context
 * cannot access extension APIs.
 */

const MSG_FINGERPRINT_REPORT = 'FINGERPRINT_REPORT';
const MSG_GET_FINGERPRINT_REPORT = 'GET_FINGERPRINT_REPORT';
const MSG_GET_RECOMMENDATIONS = 'GET_RECOMMENDATIONS';
const PAGE_MSG_FINGERPRINT_REPORT = 'CONTAINER_SHIELD_FINGERPRINT_REPORT';
const PAGE_MSG_GET_REPORT = 'CONTAINER_SHIELD_GET_REPORT';
const PAGE_MSG_GET_RECOMMENDATIONS = 'CONTAINER_SHIELD_GET_RECOMMENDATIONS';

import browser from 'webextension-polyfill';

// SYNCHRONOUS: query the C++ cloakfoxIsConfigured() WebIDL method for
// each per-container spoofer manager and store the result in
// sessionStorage. This bridges ISOLATED → MAIN: the inject script in
// MAIN world reads sessionStorage at document_start and uses the
// cached state to decide whether to skip JS spoofers (because C++ is
// already configured for this container).
//
// Why ISOLATED: the WebIDL method is Func-gated to require the
// cloakfox-shield extension's principal — only ISOLATED-world content
// scripts have that principal. MAIN-world inject script (or any page
// script) calling cloakfoxIsConfigured gets `undefined`.
//
// Why sessionStorage: synchronous, scoped per-tab, persists across
// same-tab navigations. The inject script is registered AFTER content
// in manifest.json, so by the time MAIN runs, sessionStorage is set.
(() => {
  try {
    const pageWin = (window as any).wrappedJSObject;
    const isConfigured = pageWin?.cloakfoxIsConfigured;
    if (typeof isConfigured !== 'function') return;
    const NAMES = [
      'canvas', 'audio', 'screen', 'webglVendor', 'webglRenderer',
      'fontList', 'fontSpacing', 'speechVoices',
      'navigatorUserAgent', 'navigatorPlatform', 'navigatorOscpu',
      'navigatorHardwareConcurrency',
    ];
    const result: Record<string, boolean> = {};
    for (const n of NAMES) {
      try { result[n] = !!isConfigured.call(pageWin, n); } catch {}
    }
    sessionStorage.setItem('__cloakfox_configured', JSON.stringify(result));
  } catch {}
})();

// Sync the HTTP/2 fingerprint profile into the page's privileged
// window.setHttp2Profile() WebIDL method. Runs at document_start so the
// pref change is visible before any H2 connection this tab establishes.
// The method writes network.http.http2.fingerprint_profile globally
// (Firefox prefs are process-wide), so one successful call is enough.
(async () => {
  try {
    const stored = await browser.storage.local.get('globalSettings');
    const globalSettings = stored.globalSettings as { http2Profile?: string } | undefined;
    const profile = globalSettings?.http2Profile;
    if (profile !== 'firefox' && profile !== 'chrome' && profile !== 'safari') return;
    const pageWin = (window as any).wrappedJSObject;
    // One UI toggle drives both transports — coherent fingerprint.
    if (typeof pageWin?.setHttp2Profile === 'function') {
      pageWin.setHttp2Profile(profile);
    }
    if (typeof pageWin?.setHttp3Profile === 'function') {
      pageWin.setHttp3Profile(profile);
    }
  } catch {}
})();

// Page → Background: forward fingerprint reports
window.addEventListener('message', async (event) => {
  if (event.source !== window) return;
  const { type, ...data } = event.data || {};

  if (type === PAGE_MSG_FINGERPRINT_REPORT) {
    try {
      await browser.runtime.sendMessage({
        type: MSG_FINGERPRINT_REPORT,
        summary: data.summary,
        detail: data.detail,
        url: data.url,
      });
    } catch {}
  }

  // Open test runner when requested by test harness
  if (type === 'CONTAINER_SHIELD_OPEN_TEST_RUNNER') {
    try {
      await browser.runtime.sendMessage({ type: 'OPEN_TEST_RUNNER', only: data.only || '' });
    } catch {}
  }

  // Forward the inject script's active profile + worker preamble to background
  if (type === 'CONTAINER_SHIELD_ACTIVE_PROFILE') {
    try {
      await browser.runtime.sendMessage({
        type: 'ACTIVE_PROFILE',
        profile: data.profile,
        domain: data.domain,
        workerPreamble: data.workerPreamble,
      });
    } catch {}
  }
});

// Background → Page: forward report/recommendation requests
browser.runtime.onMessage.addListener((rawMessage: unknown) => {
  const message = rawMessage as { type: string; settings?: unknown };
  if (message.type === MSG_GET_FINGERPRINT_REPORT) {
    window.postMessage({ type: PAGE_MSG_GET_REPORT }, '*');
    return true;
  }
  if (message.type === MSG_GET_RECOMMENDATIONS) {
    window.postMessage({ type: PAGE_MSG_GET_RECOMMENDATIONS, settings: message.settings }, '*');
    return true;
  }
  // Test runner: read spoofed values from the PAGE context (not isolated world)
  // Use wrappedJSObject to access the page's spoofed navigator/screen/etc.
  if (message.type === 'EXEC_READ_VALUES') {
    const r: Record<string, any> = {};
    const pageWin = (window as any).wrappedJSObject || window;
    const pageNav = pageWin.navigator;
    try { r.ua = pageNav.userAgent; } catch {}
    try { r.platform = pageNav.platform; } catch {}
    try { r.vendor = pageNav.vendor; } catch {}
    try { r.cores = pageNav.hardwareConcurrency; } catch {}
    try { r.tzo = new pageWin.Date().getTimezoneOffset(); } catch {}
    try { r.screenW = pageWin.screen.width; } catch {}
    try { r.screenH = pageWin.screen.height; } catch {}
    try {
      const c = pageWin.document.createElement('canvas');
      const gl = c.getContext('webgl');
      const ext = gl?.getExtension('WEBGL_debug_renderer_info');
      r.glVendor = ext ? gl.getParameter(ext.UNMASKED_VENDOR_WEBGL) : 'no ext';
      r.glRenderer = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'no ext';
    } catch {}
    return Promise.resolve(r);
  }
  // Test runner: read page DOM text (for parsing CreepJS output)
  if (message.type === 'EXEC_READ_DOM') {
    return Promise.resolve({ text: document.body.innerText });
  }
  return false;
});
