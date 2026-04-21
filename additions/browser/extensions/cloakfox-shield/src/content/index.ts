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

// STEALTH COORDINATION — everything Cloakfox needs to do that touches
// C++ WebIDL setters happens in THIS (ISOLATED) script, not in the MAIN
// inject script. Reasons:
//
// 1. All Cloakfox setters (setCanvasSeed / setWebGLVendor / etc.) are
//    Func-gated to `nsGlobalWindowInner::IsCloakfoxShieldCaller`, which
//    accepts only callers whose principal contains the cloakfox-shield
//    addon. ISOLATED has that principal, MAIN does not.
// 2. Page MAIN scripts therefore see `typeof setCanvasSeed === 'undefined'`
//    at all times — no detection surface.
// 3. We write the resulting {config, handled} snapshot into a
//    documentElement attribute; the MAIN-world inject script reads it
//    synchronously and removes it on the same turn. By the time any
//    page <script> runs (strictly AFTER content scripts at document_start)
//    the attribute is gone.
//
// Nothing leaks to sessionStorage, localStorage, cookies, postMessage,
// CustomEvent, or any other page-observable channel.
import { generateConfig } from '@/lib/boot-config';
import { applyCoreProtections, setCoreTargetWindow } from '@/inject/core-bridge';

const BRIDGE_ATTR = 'data-cfx-boot';

(() => {
  try {
    const pageWin = (window as any).wrappedJSObject;
    if (!pageWin) return;

    // Build the same deterministic config MAIN used to build locally.
    const realPlatform = (navigator as any).platform || '';
    const origin = window.location.hostname || 'unknown';
    const config = generateConfig(origin, realPlatform);

    // Route all callCore() calls in this invocation to the page's
    // MAIN-world window (across the compartment), where the Func
    // gate sees the cloakfox-shield principal of this content script.
    setCoreTargetWindow(pageWin);

    // Re-derive hashedSeed (same way initializeSpoofers does) so the
    // C++ managers get identical seed material to what JS will use.
    const enc = new TextEncoder();
    const seedBytes = Uint8Array.from(atob(config.seed), c => c.charCodeAt(0));
    const domainBytes = enc.encode(config.domain);
    const hashedSeed = new Uint8Array(32);
    for (let i = 0; i < seedBytes.length; i++) hashedSeed[i % 32] ^= seedBytes[i];
    for (let i = 0; i < domainBytes.length; i++)
      hashedSeed[(seedBytes.length + i) % 32] ^= domainBytes[i];

    // Apply HTTP profile from user settings if configured. Best-effort;
    // if the browser.storage lookup is slow we don't block config gen.
    let http2Profile: 'firefox' | 'chrome' | 'safari' | undefined;
    try {
      // Synchronous pass-through — storage.local.get is async so this
      // only catches the warm cache case. Cold sessions fall back to
      // the pref default (set by cloakfox.cfg defaultPref).
      // (Kept for legacy behavior; most users use about:config.)
    } catch {}

    const handled = applyCoreProtections(
      hashedSeed,
      config.assignedProfile,
      config.settings as unknown as Record<string, Record<string, string>>,
      http2Profile
    );

    // Bridge to MAIN via documentElement attribute. MAIN reads and
    // removes on same turn — no persistence, no page-observable leak.
    const payload = JSON.stringify({ config, handled: Array.from(handled) });
    document.documentElement.setAttribute(BRIDGE_ATTR, payload);
  } catch {}
})();

// NOTE: the HTTP/2 and HTTP/3 fingerprint profiles are configured via
// `network.http.http2.fingerprint_profile` and
// `network.http.http3.fingerprint_profile` prefs. The WebIDL setters
// `setHttp2Profile` / `setHttp3Profile` exist but can't persist from a
// content-process caller — Preferences::SetCString/SetUint runs in the
// content process, and in e10s the parent owns the prefs DB, so the
// write doesn't IPC up and doesn't affect the network stack (which
// lives in the parent/socket process).
//
// Practical working path: `settings/cloakfox.cfg` sets these via
// `defaultPref(...)` at browser start, which writes through the parent
// process. about:config edits work the same way. The popup's
// http2Profile toggle cannot take effect until Cloakfox ships a
// WebExtensions Experiment API that lets the background script write
// prefs through privileged APIs. Tracked in PENDING.md.

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
