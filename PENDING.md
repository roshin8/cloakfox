# Cloakfox — pending work

Living tracker of what's outstanding after the test-suite pass that landed on
`unified-maskconfig` 2026-04-19. Ordered by priority. Keep this file under
revision control so we don't lose context between sessions.

## P0 — blocks release / blocks real-site validation

### ~~Self-destructing WebIDL setters defeat C++/JS skip-coordination~~ — FIXED in commit `4bb9a03edb`

**Resolution (option 1 from below):** Added a non-self-destructing
WebIDL query method `window.cloakfoxIsConfigured(name)` that returns
true if a per-userContext spoofer manager has been configured already.

In `core-bridge.ts`, every callCore for a Func-gated setter is now
wrapped in `callOrAlreadyConfigured(setter, name, ...args)` which:
1. Tries the setter (works on nav 1).
2. Falls back to `cloakfoxIsConfigured(name)` (works on nav 2+).

If either returns true, the signal goes into `handled` and the JS
spoofer correctly skips. Covers all 12 self-destructing setters:
canvas, audio, navigator UA/platform/oscpu/HWC, screen, fontList,
fontSpacing, webglVendor, webglRenderer, speechVoices.

Backward-compat: on builds without the new WebIDL, the helper returns
false and behavior degrades to today's "always run JS fallback".

CI build pending (run `24699715160`). Re-probe against the resulting
DMG to verify `jsWebglRan: false` on second navigation.

---

### Original report (kept for historical context):

**Root cause discovered while debugging the WebGL Chrome-UA mismatch.**

How it's supposed to work: `core-bridge.ts` calls C++ WebIDL setters
(`setCanvasSeed`, `setNavigatorUserAgent`, `setWebGLVendor`,
`setWebGLRenderer`, `setScreen`, `setHardwareConcurrency`,
`setFontList`, `setSpeechVoices`, etc.). If the call succeeds, it
adds the corresponding signal name (e.g. `'graphics.webgl'`) to a
`handled` Set. The JS spoofer registry then skips any spoofer whose
name is in that set — leaving the C++ value as the only source.

What actually happens after the FIRST navigation:
1. WebIDL setter is called → C++ stores value in
   RoverfoxStorageManager keyed by userContextId.
2. C++ deletes the WebIDL property from the JS window AND sets a
   "disabled" flag in storage (e.g. `webgl_vendor_disabled_<id>`).
3. The disabled flag is checked at WebIDL binding time by `Func`
   attribute (e.g. `IsVendorFunctionEnabledForWebIDL`). On every
   subsequent window construction in the same userContext, the
   property is **never bound** at all — `typeof setWebGLVendor`
   returns `'undefined'` from the start, not "called and
   self-destructed".
4. `core-bridge.ts:callCore` returns `false` for
   `setWebGLVendor` because the function isn't there.
5. `handled.add('graphics.webgl')` doesn't fire.
6. JS WebGL spoofer runs as fallback and overrides
   `WebGLRenderingContext.prototype.getParameter` with its own
   values — which used to be Firefox-style.

The C++ stored values still persist in RoverfoxStorageManager, but
the JS spoofer's getParameter override wins (it ran later, on the
prototype). The C++ patch reads its stored values inside the
GetParameter implementation (`webgl-spoofing.patch:2328`), but that
implementation is bypassed by the JS prototype override.

This is why all WebIDL-handled signals (canvas, screen, navigator UA,
fonts, speech, timezone, etc.) end up "double-spoofed" — first by
C++ on nav 1, then by JS on every subsequent nav. The JS values win
at the prototype level. If the JS values diverge from the C++ values
(or are not browser-coherent), you get fingerprint mismatches like
the WebGL Chrome-UA bug.

**Diagnostic verified live:** sentinels added to `webgl.ts` and
`spoofers/index.ts` showed:
- nav 1: `coreHandled` contains 31 entries including `graphics.webgl`,
  `jsWebglRan` is false (skip works).
- nav 2: `coreHandled` contains only 12 entries (the non-WebIDL ones
  like `permissions.query`, `storage.estimate` that don't self-disable).
  `jsWebglRan` is true. WebIDL setters all show typeof `undefined`
  because they were never bound.

**Workaround already applied (commit `d487e550c6`):** make the JS
spoofer's GPU lists match what C++ would have emitted for each UA
family, so coherent values either way.

**Architectural fix paths (pick one):**

1. **Add a non-self-destructing query method.** New WebIDL like
   `__cloakfoxWebGLConfigured()` returns `true` if the disabled flag
   is set for this userContext. core-bridge.ts checks it BEFORE
   trying the setter; adds to `handled` based on either path. This
   is the cleanest — C++ remains the source of truth, JS skips
   correctly on nav 2+.
2. **Persist the handled set in sessionStorage.** core-bridge.ts
   reads sessionStorage on entry to remember "I configured WebGL
   on a prior nav this tab"; uses that to populate `handled` even
   when the setter is missing. Per-tab cache; per-container cache
   needs cross-tab coordination (background script).
3. **Don't self-destruct WebIDL after first call.** Re-bind on
   every nav; have the C++ setter no-op (already-set guard) on
   subsequent calls. Loses the security property of "page can't
   keep probing the setter" but the page can't observe much from
   a no-op anyway.

Option 1 is most invasive but architecturally cleanest. Option 3 is
smallest patch. Option 2 is workable but messy.

**Files touched (any option):** `additions/browser/extensions/cloakfox-shield/src/inject/core-bridge.ts`,
plus either C++ patches (option 1 or 3) or extension storage logic
(option 2).

### WebGL emits Firefox-style strings under a Chrome UA (verified broken)

**Symptom:** With the assigned UA = `Chrome/123 Mac OS X`, the WebGL
debug-renderer extension returns:
- `UNMASKED_VENDOR_WEBGL = "Apple Inc."`
- `UNMASKED_RENDERER_WEBGL = "Apple M1"` (rotates across runs within
  Apple family — M1, M1 Pro, M2, M2 Pro, M3, M4)

But real Chrome on Mac uses ANGLE and returns:
- `UNMASKED_VENDOR_WEBGL = "Google Inc. (Apple)"`
- `UNMASKED_RENDERER_WEBGL = "ANGLE (Apple, ANGLE Metal Renderer: Apple
  M1 Pro, Unspecified Version)"`

The values we emit are FIREFOX-style. With a Chrome UA they're a direct
mismatch any anti-bot would notice — Chrome ≠ ANGLE-renderer-string is
a known fingerprint divergence. Same issue would apply for Chrome/Windows
or Chrome/Linux profiles emitting Firefox-style Mesa/etc strings.

**Diagnosis:** All four WebIDL setters self-destructed in the probe
(`setWebGLVendor: undefined`, `setWebGLRenderer: undefined`,
`setCanvasSeed: undefined`, `setNavigatorUserAgent: undefined`). C++
WAS called. `core-bridge.ts:399` `pickPlatformGPU()` correctly returns
ANGLE-style strings for Mac platform (`"Google Inc. (Apple)"` /
`"ANGLE (Apple, ANGLE Metal Renderer: Apple M1, ...)"`). But what
WebGL queries return is the JS spoofer's `MAC_GPUS` list values
(`webgl.ts:` `"Apple Inc." / "Apple M1"`). Two scenarios:

1. C++ stored the spoofed value but the parameter-resolver patch reads
   from a different source / doesn't override `UNMASKED_*_WEBGL`.
2. C++ ran successfully but the JS spoofer ran AFTER and overrode it
   (the skip()/handled set didn't gate JS WebGL away).

**Fix path:**
- Verify which scenario via console.log injection in webgl.ts
  `initWebGLSpoofer` — if it runs at all, scenario #2.
- If scenario #2: fix the skip-gating in spoofers/index.ts so JS WebGL
  doesn't run when C++ took ownership.
- If scenario #1: fix the C++ webgl-spoofing.patch storage read at
  parameter-resolution time.
- Either way: align the JS MAC_GPUS list with the C++ ANGLE-style
  strings so even when JS wins it emits Chrome-coherent values.

**Files touched:** `additions/browser/extensions/cloakfox-shield/src/inject/core-bridge.ts`,
`additions/browser/extensions/cloakfox-shield/src/inject/spoofers/graphics/webgl.ts`,
`additions/browser/extensions/cloakfox-shield/src/inject/spoofers/index.ts`,
possibly `patches/webgl-spoofing.patch`.



### WebIDL setters don't actually persist prefs

**Symptom:** `window.setHttp2Profile("chrome")` self-destructs (proving the
method ran) but the `network.http.http2.fingerprint_profile` pref stays at
its default. Same for `setHttp3Profile`. The extension's
`content/index.ts` calls both setters from `globalSettings.http2Profile`
— it's a no-op today.

**Cause:** The C++ handler calls `Preferences::SetCString` /
`Preferences::SetUint` from content-process scope. In e10s Firefox the
parent owns the prefs DB; content-side writes don't IPC up to the parent
automatically, so they don't persist or propagate to the other content
processes that establish H2/H3 connections.

**Working path today:** `about:config` or profile `prefs.js` (set at
browser start via `opts.set_preference` in tests) — these write through
the parent. CLI-style pref override works. UI toggle does not.

**Fix path:** Expose a WebExtensions Experiment API in the
`cloakfox-shield` system addon that the background script calls. The
background runs with privileged-extension scope and can write through
`Services.prefs.setCharPref` (goes through parent). Scope: new
`experiment_apis` manifest entry + `schema.json` + `api.js` + plumbing
so the popup/options pages call `browser.cloakfoxPrefs.setProfile(...)`
instead of the (broken) WebIDL setter.

**Files touched:** `additions/browser/extensions/cloakfox-shield/manifest.json`,
new `additions/browser/extensions/cloakfox-shield/src/experiment_apis/`,
`additions/browser/extensions/cloakfox-shield/src/content/index.ts` (remove
the broken setHttp2Profile/setHttp3Profile calls), `settings/cloakfox.cfg`
(unchanged — defaultPref is still correct).

### Cold-start Sec-CH-UA race

**Symptom:** First navigation in a session doesn't emit `Sec-CH-UA`,
`Sec-CH-UA-Mobile`, `Sec-CH-UA-Platform` headers. Second navigation
onward, they fire correctly. Verified live.

**Cause:** The `webRequest` header-spoofer in `background/header-spoofer.ts`
reads `browser.storage.local[activeProfile:${tabId}]` to get the brands.
That entry is populated only after the inject script runs, post-messages
to content script, which forwards to background. On the FIRST navigation
the storage key doesn't exist yet when `onBeforeSendHeaders` fires.

**Fix path:** Have `background/index.ts` pre-assign a profile to the
default container at startup (synchronously) and write it to
`activeProfile:<tabId>` for any newly-opened tab before the first request
fires. Or: move the brands source to `settings.profile.brands` on the
container settings, so the header-spoofer doesn't depend on the activeTab
round-trip for request 0.

**Files touched:** `additions/browser/extensions/cloakfox-shield/src/background/index.ts`,
`additions/browser/extensions/cloakfox-shield/src/background/header-spoofer.ts`,
`additions/browser/extensions/cloakfox-shield/src/types/settings.ts`.

### Real-site validation with a post-all-fixes DMG

Once CI `24637464609` (or its successor) goes green on both Linux + macOS:

- Run `python tests/fingerprint/antibot_battery.py` against the new DMG,
  review the markdown + screenshots.
- Manual check that the extension popup UI actually works end-to-end —
  pick a container, toggle protection level, verify the per-container
  fingerprint changes on a refresh at `browserleaks.com`. This was never
  tested before the `jar.mn` fix because the extension wasn't loading.
- Hit 2-3 real anti-bot sites (Cloudflare challenge page, Akamai-protected
  site, PerimeterX) with `chrome` profile active, confirm they don't
  immediately challenge.

## P1 — JS spoofer audit (~55 files, only ~5 live-verified)

Live testing of Math.PI surfaced four stacked bugs (double-XOR seed,
noise-below-ULP, Proxy invariant violation, copy-before-override silent
failure). The double-XOR fix unblocks ALL spoofers' PRNG streams — so
per-domain seeding should work across the board now. But there's no
guarantee the rest don't have their own specific bugs (e.g. the
Math-style non-configurable property issue, or wrong override targets).

**Quick-audit tool:** `tests/fingerprint/probe_js_spoofers.py` dumps ~40
signals via a single Cloakfox launch and compares against "unspoofed
defaults on my machine" heuristics. Run it first to triage what's
broken before writing per-spoofer tests.

### Verified working via live probe

- `navigator.userAgent` — spoofed to Chrome 125 Windows post-warmup
- `navigator.hardwareConcurrency` — spoofed (16 vs real 12)
- `Math.sin(x)` — ±1e-12 noise on result
- `Math.PI / Math.E / ...` — per-domain noise at 1e-13 (post-fix)
- `Sec-CH-UA / Sec-CH-UA-Mobile / Sec-CH-UA-Platform` — emitted on
  warm navigations for Chromium profiles
- H2 SETTINGS / WINDOW_UPDATE / HPACK — all three profiles distinct

### Not yet live-verified (presumed working via C++ or untouched code)

Most of these have C++ patches that do the heavy lifting; the JS
spoofer is a fallback or complement. Low risk, but worth a probe run.

- `canvas.toDataURL` noise (C++ canvas-spoofing patch)
- WebGL `getParameter(VENDOR/RENDERER)` (C++ webgl-spoofing + JS)
- WebGL shader precision / extension list (JS: webgl.ts, webgl-shaders.ts)
- `OffscreenCanvas` (JS: offscreen.ts)
- `WebGPU` adapter info (JS: webgpu.ts, C++: nothing currently)
- `AudioContext` getChannelData noise (C++: audio-context-spoofing)
- `OfflineAudioContext` (JS: offline-audio.ts)
- `HTMLMediaElement` latency (JS: audio-latency.ts)
- `MediaSource.isTypeSupported` (C++: mediasource-istypesupported + JS)
- `RTCRtpSender.getCapabilities` (JS: codecs.ts)
- `screen.width / height / availWidth / availHeight` (C++: screen-spoofing)
- `window.outerWidth / outerHeight / screenFrame` (JS: screen-frame.ts)
- `screen.orientation.type` (C++: screen-orientation-spoofing + JS)
- `navigator.getBattery()` (JS: battery.ts; C++ disables entirely via pref)
- `navigator.mediaDevices.enumerateDevices()` (C++: media-device + JS)
- `navigator.maxTouchPoints` (JS: touch.ts)
- `navigator.architecture / bitness` via UA-CH (JS: architecture.ts)
- `window.visualViewport.*` (C++: visual-viewport-spoofing + JS)
- `navigator.clipboard.*` (C++: clipboard-spoofing + JS)
- `navigator.vibrate()` (C++: vibration-spoofing + JS)
- `document.fonts.check()` / FontFaceSet (C++: font-list + JS: font-enum)
- CSS font-family fallback enumeration (JS: css-fonts.ts)
- `navigator.fontConfig` (JS: font-preferences.ts)
- `window.name` persistence (C++: window-name-spoofing + JS)
- `navigator.mediaCapabilities.decodingInfo()` (C++: + JS)
- CSS media queries: prefers-color-scheme, prefers-reduced-motion,
  color-gamut, resolution (C++: media-features-spoofing)
- `speechSynthesis.getVoices()` (C++: speech-voices-spoofing + JS)
- `navigator.permissions.query()` (C++: permissions-spoofing + JS)
- `navigator.storage.estimate()` (C++: storage-estimate-spoofing + JS)
- `indexedDB.databases()` (C++: indexeddb-spoofing + JS)
- `window.Notification.permission` (C++: notification-spoofing + JS)
- `navigator.getGamepads()` (JS: gamepad.ts)
- `navigator.requestMIDIAccess()` (JS: midi.ts)
- `window.crypto.getRandomValues` (JS: webcrypto.ts)
- `window.Notification.requestPermission` (C++ + JS)
- `performance.now()` timer resolution (C++: timing-jitter-spoofing + JS)
- `setTimeout / setInterval` jitter (JS: event-loop.ts)
- Worker fingerprint propagation (JS: worker-fingerprint.ts)
- Service worker UA override (JS: worker-fingerprint.ts)
- `Error().stack` normalization (JS: stack-trace.ts)
- Emoji rendering quirks (JS: emoji.ts)
- MathML bbox (JS: mathml.ts)
- SVG bbox / CTM / getTotalLength (C++ handles; JS: svg.ts)
- Iframe re-patching on dynamic append (JS: iframe-patcher.ts)
- `Intl.DateTimeFormat().resolvedOptions().timeZone` (C++: locale-spoofing + JS: intl-apis.ts)
- Feature-detection (`document.implementation.hasFeature`, CSS.supports) (JS: feature-detection.ts)
- `Geolocation.getCurrentPosition` (C++: geolocation-spoofing + JS)
- `WebSocket` constructor (C++: websocket-spoofing + JS)
- `tab.sessionStorage` history (JS: tab-history.ts)
- Private-mode detection (JS: private-mode.ts)
- Architecture-detection via Math.fround tricks (JS: architecture.ts)
- Keyboard cadence / typing rhythm (JS: cadence.ts — no test, separately P1)

### Known likely-broken (same class as the Math bugs)

No evidence yet — identification needed via probe run. Categories of
bugs to look for:

1. **Non-configurable property replacement.** Math.PI/E are non-writable
   non-configurable; I had to swap Math entirely via Proxy (which also
   broke — see history) and ultimately via a plain object copy. Similar
   bugs may exist in:
   - `navigator.userAgent` override — browsers lock this with specific
     descriptor rules; verify assignment sticks in page world not just
     selenium sandbox.
   - `screen.width / height` — check descriptor.
   - `navigator.hardwareConcurrency` — check.
   - Any `Object.defineProperty(X.prototype, 'someNativeGetter', ...)`
     in the spoofers — if the original getter is non-configurable, the
     override fails silently.

2. **Double-XOR-style seed cancellation.** Now fixed for the fallback
   path (inject/index.ts `generateSeed` no longer includes domain). But
   verify no other spoofer does its own XOR-with-domain on top of the
   pagePRNG — that would re-introduce cancellation.

3. **Selenium sandbox / page world mismatch.** When writing tests, `Math`
   is one case. `navigator` might be another — check via inline `<script>`
   DOM injection pattern (same trick used in test_math_constants.py).

### Action items

- [ ] Run `probe_js_spoofers.py` against the next green DMG, save the
      output as the baseline
- [ ] For each signal marked UNSPOOFED in probe output, triage: is the
      spoofer disabled by default? Is it genuinely broken?
- [ ] Write a per-spoofer test for each broken one, following
      `test_math_constants.py` pattern

## P1 — test coverage gaps

### Cross-container uniqueness (not just cross-domain)

`test_math_constants.py::test_math_pi_differs_across_domains` covers
per-domain seeding. It does NOT cover per-container: that requires the
inject script to receive a real container-scoped seed from the background,
which in turn requires the tab to be routed through a specific container
via the Multi-Account Containers API.

**Fix path:** Either add a test-mode pref (e.g.
`cloakfox.test.force_container_seed`) that injects a specific seed via the
inject path for testing, OR use privileged Marionette to create a
container and open a URL in it, then read Math.PI.

### CreepJS trust score extraction

`antibot_battery.py` captures CreepJS screenshots fine, but emits
`trust: ?` — the selectors `.unblurred-trust-score, .trust-score` don't
match CreepJS's shadow-DOM-rendered output.

**Fix path:** Use `document.querySelectorAll` inside a `<script>` tag
appended to the page so it runs in page world (same pattern as
`test_math_constants.py`), and walk the shadow roots with
`element.shadowRoot.querySelector` to reach the score elements.

### `areyouheadless` timeouts

`antibot_battery.py` hits a 60s navigation timeout on
`arh.antoinevastel.com/bots/areyouheadless` during smoke runs. May be
site flakiness; may be the site blocking selenium-driven Firefox.

**Fix path:** Bump timeout to 90s AND/OR detect the headless-test verdict
via the `verdict_extractor` rather than waiting for full page load AND/OR
drop the site from the default battery if it's consistently flaky.

### Keyboard cadence spoofing

No integration test exists for `inject/spoofers/keyboard/cadence.ts`. The
spoofer adds jitter to `KeyboardEvent.timeStamp`. Worth a test that
synthesizes keyboard events via Marionette and asserts the timestamps
diverge from the monotonic clock.

### WebRTC SDP fingerprint

C++ patches cover WebRTC IP leak (mDNS suppression) but not SDP-level
fingerprint (media line order, fingerprint algorithm list). Worth
profiling what real Chrome/Firefox/Safari emit and spoofing it. Not yet
attempted.

## P2 — housekeeping

### `CLAUDE.md` refresh

The top-level `CLAUDE.md` still describes the pre-test architecture. It
doesn't mention:
- The `tests/fingerprint/` harness + selenium+geckodriver choice
- The 7 gotchas documented in `tests/fingerprint/README.md`
- The `defaultPref()` contract for cloakfox.cfg
- The `jar.mn` dest-path rule

Should be a short pointer block — the detailed docs live in
`tests/fingerprint/README.md`.

### Memory refresh

Session memory didn't capture the 7 bugs as anti-regression markers.
Worth writing to:
- `feedback_testing.md` — "Cloakfox extension tests need selenium+geckodriver,
  NOT Playwright (no Juggler patch)"
- `feedback_build.md` — "AutoConfig cloakfox.cfg must use defaultPref() for
  toggleable prefs; pref() clobbers on every startup"
- `architecture.md` — "Content-process WebIDL setters can't persist
  Preferences — use Experiment API from background"

### Stale Playwright commit

`8de1f2c1aa — Fingerprint test harness: Playwright + mitmproxy` is
superseded by `1d6bbec843` which rewrote to Selenium. The Playwright
test file was replaced but the commit message still mentions Playwright.
Harmless but confusing when grepping history.

## Out of scope (not pending — deliberately deferred)

- **TLS JA3/JA4 spoofing.** Requires NSS patches. Weeks of work, separate
  project scope.
- **HTTP/3 wire-level SETTINGS frame observation.** Would need
  mitmproxy-quic or wireshark integration in the test harness. The pref
  plumbing is verified; the SETTINGS emission is covered by the Rust
  unit tests in neqo-http3 that shipped with the patch.
- **HTTP/3 profile UI toggle per-container.** Same underlying problem as
  the P0 WebIDL-setter-doesn't-persist issue — the extension toggle
  needs the Experiment API path to actually work.

## How to update this file

- Move items to the completed section (or delete) as they land.
- Keep each bullet self-contained: symptom, cause, fix path, files
  touched. Future-you won't have the context you have today.
- If an item spawns subtasks, nest them in place rather than creating
  a separate file.
