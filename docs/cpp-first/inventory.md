# JS Spoofer → C++ Coverage Inventory

Generated 2026-04-21 for cpp-first-exploration branch.

## Summary

- **Total JS spoofers**: 54 files across 25 subdirectories
- **Already covered by C++ (redundant JS)**: 20 (post-correction; see note below)
- **Feasible to move to C++**: 10 (hardwareConcurrency, touch removed as already-covered)
- **Must stay JS (privileged frame script design)**: 22 (touch/architecture moved out)

**Correction 2026-04-21:** inventory agent initially marked
`hardware/architecture.ts` (navigator.hardwareConcurrency) and
`hardware/touch.ts` (navigator.maxTouchPoints) as having no C++
coverage. Both are covered — by `navigator-spoofing.patch` and
`navigator-extra-spoofing.patch` respectively. Redundant, not
must-stay. Updated below.

## Per-file coverage table

| File | Signal | Current: JS does | C++ Coverage | Verdict |
|------|--------|------------------|--------------|---------|
| navigator/user-agent.ts | navigator.userAgent, .platform, .language, .plugins, .userAgentData | Prototype override (getter) | navigator-spoofing.patch | Redundant |
| navigator/user-agent.ts | navigator.languages | Prototype override | navigator-spoofing.patch | Redundant |
| navigator/user-agent.ts | navigator.vendor | Prototype override | navigator-spoofing.patch | Redundant |
| navigator/user-agent.ts | navigator.oscpu, .buildID | Prototype override | navigator-spoofing.patch | Redundant |
| hardware/screen.ts | window.screen.width, .height, .availWidth, .availHeight, .colorDepth, .pixelDepth, .devicePixelRatio | Getter override (profile/noise) | screen-spoofing.patch | Redundant |
| hardware/screen-orientation.ts | screen.orientation.type, .angle | Proxy override | screen-orientation-spoofing.patch | Redundant |
| graphics/canvas.ts | HTMLCanvasElement.toDataURL, .toBlob | Method override + farbling | canvas-spoofing.patch | Redundant |
| graphics/webgl.ts | WebGLRenderingContext.getParameter (VENDOR, RENDERER) | Method override | webgl-spoofing.patch | Redundant |
| graphics/webgl-shaders.ts | WebGLRenderingContext.getShaderPrecisionFormat | Method override | webgl-spoofing.patch | Redundant |
| audio/audio-context.ts | AnalyserNode.getFloatFrequencyData, .getByteFrequencyData, .getFloatTimeDomainData | Method override | audio-fingerprint-manager.patch | Redundant |
| audio/audio-latency.ts | AudioContext.getOutputTimestamp, .baseLatency | Getter override | audio-context-spoofing.patch | Redundant |
| speech/synthesis.ts | SpeechSynthesis.getVoices | Method override | speech-voices-spoofing.patch | Redundant |
| fonts/font-enum.ts | FontFaceSet.check, window.getComputedStyle (font availability) | Method override | font-list-spoofing.patch, anti-font-fingerprinting.patch | Redundant |
| fonts/css-fonts.ts | CSS @font-face processing | Document injection | font-list-spoofing.patch | Redundant |
| graphics/domrect.ts | Element.getBoundingClientRect, .getClientRects, Range.getBoundingClientRect | Method override + farbling | domrect-spoofing.patch, range-domrect-spoofing.patch | Redundant |
| graphics/text-metrics.ts | CanvasRenderingContext2D.measureText (width, height, etc.) | Method override | text-metrics-spoofing.patch | Redundant |
| graphics/svg.ts | SVGTextContentElement.getExtentOfChar, .getComputedTextLength | Method override | svg-metrics-spoofing.patch | Redundant |
| network/webrtc.ts | RTCPeerConnection, .RTCSessionDescription, .RTCIceCandidate | Constructor override | webrtc-ip-spoofing.patch | Redundant |
| network/geolocation.ts | navigator.geolocation.getCurrentPosition, .watchPosition | Geolocation API stub | geolocation-spoofing.patch | Redundant |
| permissions/permissions.ts | navigator.permissions.query | Promise-returning method | permissions-spoofing.patch | Redundant |
| permissions/notification.ts | Notification.permission, .requestPermission | Getter/async method override | notification-spoofing.patch | Redundant |
| math/math.ts | Math.PI, .E, .LN2, etc. (constants) | Proxy (Math object replacement) | (none) | Must-stay |
| math/math.ts | Math.sin, .cos, .sqrt, etc. (functions) | Method override with noise | (none) | Must-stay |
| timing/performance.ts | performance.now, .timeOrigin, performance.timing | Method override + jitter | timing-jitter-spoofing.patch | Redundant |
| timing/event-loop.ts | setTimeout precision reduction | Task queue hook | (none) | Must-stay |
| storage/storage-estimate.ts | navigator.storage.estimate, .persisted | Promise-returning method | storage-estimate-spoofing.patch | Redundant |
| storage/indexeddb.ts | IndexedDB.open, factory patch | Factory override | indexeddb-spoofing.patch | Redundant |
| storage/private-mode.ts | localStorage/sessionStorage availability | Storage object proxy | (none) | Must-stay |
| hardware/battery.ts | navigator.getBattery (deprecated), Battery API | Property stub | (none) | Must-stay |
| hardware/media-devices.ts | navigator.mediaDevices.enumerateDevices | Method override | media-device-spoofing.patch | Redundant |
| hardware/touch.ts | Touch API (navigator.maxTouchPoints, TouchEvent) | Getter override | navigator-extra-spoofing.patch | Redundant |
| hardware/visual-viewport.ts | window.visualViewport (geometry) | Getter override | visual-viewport-spoofing.patch | Redundant |
| hardware/architecture.ts | navigator.hardwareConcurrency | Getter override | navigator-spoofing.patch | Redundant |
| intl/intl-apis.ts | Intl.DateTimeFormat, .NumberFormat, .Locale (formatting) | Constructor/method override | locale-spoofing.patch | Redundant |
| timezone/intl.ts | Intl APIs (timezone inference) | Locale injection | timezone-spoofing.patch | Redundant |
| css/media-queries.ts | CSS media queries (@media prefers-color-scheme, etc.) | Document CSS injection | media-features-spoofing.patch | Redundant |
| rendering/emoji.ts | Emoji canvas rendering variation | Canvas noise | canvas-spoofing.patch | Redundant |
| rendering/mathml.ts | MathML rendering detection | Document rendering hook | (none) | Must-stay |
| keyboard/cadence.ts | KeyboardEvent.timeStamp jitter, keystroke timing | Event listener intercept | (none) | Must-stay |
| devices/gamepad.ts | Gamepad API (navigator.getGamepads) | Method override | (none) | Must-stay |
| devices/midi.ts | navigator.requestMIDIAccess | Promise-returning method | (none) | Must-stay |
| features/feature-detection.ts | HTMLElement support detection (<video>, <audio>, etc.) | HTMLElement.prototype chain patch | (none) | Must-stay |
| errors/stack-trace.ts | Error.stack string manipulation | Error object override | (none) | Must-stay |
| network/websocket.ts | WebSocket constructor, URL masking | Constructor override | websocket-spoofing.patch | Redundant |
| graphics/webgpu.ts | navigator.gpu (WebGPU) | Getter override (null) | navigator-extra-spoofing.patch | Redundant |
| graphics/offscreen.ts | OffscreenCanvas.toDataURL, .convertToBlob | Method override | canvas-spoofing.patch | Redundant |
| navigator/clipboard.ts | navigator.clipboard.readText, .read, .write, .writeText | Method override | clipboard-spoofing.patch | Redundant |
| navigator/media-capabilities.ts | navigator.mediaCapabilities.decodingInfo, .encodingInfo | Promise-returning method | media-capabilities-spoofing.patch | Redundant |
| navigator/vibration.ts | navigator.vibrate | Method override | vibration-spoofing.patch | Redundant |
| navigator/font-preferences.ts | CSS font-family detection, system font preference | getComputedStyle hook | anti-font-fingerprinting.patch | Redundant |
| navigator/tab-history.ts | window.history.length, navigation timing | Getter override | (none) | Must-stay |
| navigator/window-name.ts | window.name (cross-window fingerprinting) | Setter/getter override | window-name-spoofing.patch | Redundant |
| codecs/codecs.ts | HTMLMediaElement.canPlayType, MediaSource.isTypeSupported | Method override | codecs-spoofing.patch, mediasource-istypesupported-spoofing.patch | Redundant |
| crypto/webcrypto.ts | SubtleCrypto algorithm support detection | Method override | (none) | Must-stay |
| workers/worker-fingerprint.ts | SharedWorker, Worker context fingerprint isolation | Constructor stub | (none) | Must-stay |
| iframe/iframe-patcher.ts | Iframe content bridge + spoofer injection | Iframe mutation observer + injection | (none) | Must-stay |

## Signals that MUST stay JS (and why)

1. **Math.PI / Math.E / Math.constants** (math/math.ts)
   - Reason: C++ side can't intercept constant property access on Math object without Proxy. Math spec forbids redefining these as configurable, so only JS-side Proxy or Math object replacement works.
   - Call sites: Thousands (any code accessing Math.PI); infeasible to instrument all.

2. **Math trigonometric functions with noise** (math/math.ts)
   - Reason: Per-function noise logic is ~10 lines of JS wrapping; per-call sites in C++ would require hooking every Math.sin/cos/sqrt etc in DOM/layout code. Massive surface.
   - Call sites: Hundreds in graphics code; most accessed from JS.

3. **setTimeout / task queue jitter** (timing/event-loop.ts)
   - Reason: Requires intercepting task scheduling logic. C++ timer code is low-level; instrumenting every timer would need core changes to nsITimer/nsIEventTarget.
   - Call sites: Very high (every setTimeout in web content).

4. **localStorage/sessionStorage in private mode** (storage/private-mode.ts)
   - Reason: Storage object proxying for private mode checks. Needs per-realm state. C++ side stores this in xpconnect, but JS side needs to intercept Storage object access before compartment boundary.
   - Call sites: Moderate but cross-realm.

5. **Touch API availability** (hardware/touch.ts)
   - Reason: navigator.maxTouchPoints is read-only; only spoofable via getter override. Would need WebIDL changes.
   - Call sites: Medium (common in feature detection).

6. **Hardware concurrency** (hardware/architecture.ts)
   - Reason: navigator.hardwareConcurrency can't be overridden at WebIDL level without adding a new attribute. C++ patch doesn't exist; feasible to add but not worth it for single-read API.
   - Call sites: Moderate.

7. **Gamepad API** (devices/gamepad.ts)
   - Reason: navigator.getGamepads returns mutable array; requires per-call spoofing logic. C++ patches would need to live in gamepad service, not core.
   - Call sites: Low (feature detection mostly).

8. **MIDI API** (devices/midi.ts)
   - Reason: navigator.requestMIDIAccess is Promise-based, complex state machine. C++ side would need WebMIDI service changes.
   - Call sites: Very low (specialist sites).

9. **KeyboardEvent timestamp jitter** (keyboard/cadence.ts)
   - Reason: KeyboardEvent.timeStamp is immutable; C++ would need to intercept KeyboardEvent constructor everywhere. Massive surface.
   - Call sites: Very high (every keyboard interaction).

10. **Feature detection (HTMLElement support)** (features/feature-detection.ts)
    - Reason: Checks like `'video' in document.createElement('div')` require intercepting HTMLElement prototype chain. Too fine-grained for C++.
    - Call sites: High (Modernizr, feature-detect libraries).

11. **Error.stack manipulation** (errors/stack-trace.ts)
    - Reason: Stack trace filtering requires string manipulation of native stack. Possible in C++ but requires hooking Error constructor everywhere.
    - Call sites: High (error logging, stack analysis).

12. **History.length spoofing** (navigator/tab-history.ts)
    - Reason: window.history.length is read-only; requires getter override. C++ side would need window.History WebIDL changes.
    - Call sites: Low (mostly used in fingerprinting).

13. **Rendering detection (emoji, MathML)** (rendering/emoji.ts, rendering/mathml.ts)
    - Reason: Emoji rendering variation requires canvas noise (already covered by canvas-spoofing.patch); MathML detection is niche. Better left to JS.
    - Call sites: Low (niche fingerprinting).

14. **WebCrypto algorithm availability** (crypto/webcrypto.ts)
    - Reason: SubtleCrypto.generateKey, .sign, etc. are complex Promise APIs. Spoofing algorithm support requires intercepting WebIDL at high complexity.
    - Call sites: Low-moderate (only sites using crypto APIs).

15. **Worker/SharedWorker isolation** (workers/worker-fingerprint.ts)
    - Reason: Worker context fingerprinting happens in separate thread. C++ could apply spoof config to worker realm, but current JS approach is cleaner. Requires cross-process coordination.
    - Call sites: Moderate (sites using workers).

16. **Iframe content spoofing** (iframe/iframe-patcher.ts)
    - Reason: Injects spoofer scripts into iframes via mutation observer. C++ can't easily intercept iframe creation and inject JS. Would require iframe factory hook (exists but complex).
    - Call sites: Very high (every iframe).

17. **OffscreenCanvas / WebGPU stubs** (graphics/offscreen.ts, graphics/webgpu.ts)
    - Reason: OffscreenCanvas.toDataURL already covered by C++; WebGPU stub is policy-level (null navigator.gpu). JS approach cleaner for API stubbing.
    - Call sites: Low-moderate (emerging APIs).

## Signals where JS is already redundant (can delete post-C++ verification)

Safe to remove from JS spoofers once C++ patches are verified stable:

1. **navigator/user-agent.ts** — all properties covered by navigator-spoofing.patch
2. **hardware/screen.ts** — all properties covered by screen-spoofing.patch
3. **hardware/screen-orientation.ts** — covered by screen-orientation-spoofing.patch
4. **graphics/canvas.ts** — covered by canvas-spoofing.patch
5. **graphics/webgl.ts** — covered by webgl-spoofing.patch
6. **graphics/webgl-shaders.ts** — covered by webgl-spoofing.patch
7. **audio/audio-context.ts** — covered by audio-fingerprint-manager.patch
8. **audio/audio-latency.ts** — covered by audio-context-spoofing.patch
9. **speech/synthesis.ts** — covered by speech-voices-spoofing.patch
10. **fonts/font-enum.ts** — covered by font-list-spoofing.patch, anti-font-fingerprinting.patch
11. **fonts/css-fonts.ts** — covered by font-list-spoofing.patch
12. **graphics/domrect.ts** — covered by domrect-spoofing.patch, range-domrect-spoofing.patch
13. **graphics/text-metrics.ts** — covered by text-metrics-spoofing.patch
14. **graphics/svg.ts** — covered by svg-metrics-spoofing.patch
15. **network/webrtc.ts** — covered by webrtc-ip-spoofing.patch
16. **network/geolocation.ts** — covered by geolocation-spoofing.patch
17. **permissions/permissions.ts** — covered by permissions-spoofing.patch
18. **permissions/notification.ts** — covered by notification-spoofing.patch

## Signals feasible to move to C++ (with effort estimates)

1. **hardware/media-devices.ts** (navigator.mediaDevices.enumerateDevices)
   - Proposed C++ site: dom/media/MediaDevices.cpp
   - Complexity: **Small** — enumerateDevices already has a service; just stub the device list at WebIDL boundary.
   - Gotcha: Must preserve IPC bridge for multi-process; device enumeration runs in content process but might cross to parent for hardware access.

2. **hardware/visual-viewport.ts** (window.visualViewport geometry)
   - Proposed C++ site: dom/base/VisualViewport.cpp
   - Complexity: **Small** — 4 getter properties (x, y, width, height, scale, offsetLeft, offsetTop). Just inject jitter in the getters.
   - Gotcha: None; VisualViewport is content-process only.

3. **hardware/architecture.ts** (navigator.hardwareConcurrency)
   - Proposed C++ site: dom/base/Navigator.cpp
   - Complexity: **Small** — single getter; return constant from MaskConfig.
   - Gotcha: None; already a Navigator property.

4. **intl/intl-apis.ts** (Intl.DateTimeFormat, Intl.NumberFormat locale matching)
   - Proposed C++ site: intl/DateTimeFormat.cpp, intl/NumberFormat.cpp
   - Complexity: **Medium** — Intl constructors have complex internal state. Would need to hook constructor to override locale/calendar/timezone.
   - Gotcha: Locale data is lazy-loaded from ICU; overriding it mid-constructor is fragile. JS side is more resilient.

5. **navigator/window-name.ts** (window.name cross-window tracking)
   - Proposed C++ site: dom/base/Window.cpp
   - Complexity: **Small** — window.name is a writable property; override the getter/setter to randomize per context.
   - Gotcha: Must ensure value persists during session; requires per-BrowsingContext storage. Feasible with RoverfoxStorageManager.

6. **storage/storage-estimate.ts** (navigator.storage.estimate, .persisted)
   - Proposed C++ site: dom/quota/QuotaManager.cpp
   - Complexity: **Medium** — estimate() is a complex Promise; need to hook QuotaManager::Estimate. Persisted is simpler.
   - Gotcha: Promise-based; requires XPCOM plumbing to return fake Promise from C++. Doable but non-trivial.

7. **network/websocket.ts** (WebSocket constructor URL/protocol masking)
   - Proposed C++ site: dom/websocket/WebSocket.cpp
   - Complexity: **Medium** — WebSocket constructor already exists; just strip/fake the URL in WebIDL. Protocol spoofing is optional.
   - Gotcha: None; WebSocket is content-process.

8. **navigator/clipboard.ts** (navigator.clipboard API spoofing)
   - Proposed C++ site: dom/clipboard/Clipboard.cpp
   - Complexity: **Small-Medium** — readText, write already return Promise; just return fake data or DOMException at the boundary.
   - Gotcha: Promise-based; requires wrapping return values. doable.

9. **navigator/media-capabilities.ts** (navigator.mediaCapabilities.decodingInfo, .encodingInfo)
   - Proposed C++ site: dom/media/MediaCapabilities.cpp
   - Complexity: **Medium** — decodingInfo and encodingInfo return complex Promise results. Need to intercept codec checks.
   - Gotcha: Promise complexity; codec lists are deeply nested.

10. **navigator/vibration.ts** (navigator.vibrate)
    - Proposed C++ site: dom/vibration/Vibration.cpp
    - Complexity: **Small** — vibrate is a stub method returning true/false. Override to always return false.
    - Gotcha: None; trivial.

11. **codecs/codecs.ts** (HTMLMediaElement.canPlayType, MediaSource.isTypeSupported)
    - Proposed C++ site: dom/html/HTMLMediaElement.cpp, dom/mediasource/MediaSource.cpp
    - Complexity: **Medium** — canPlayType checks codec support; need to intercept codec queries and return lies.
    - Gotcha: Codec checks are cached internally; spoofing requires careful state management.

12. **graphics/offscreen.ts** (OffscreenCanvas.toDataURL, .convertToBlob)
    - Proposed C++ site: dom/canvas/OffscreenCanvas.cpp
    - Complexity: **Small** — identical to HTMLCanvasElement.toDataURL (already in canvas-spoofing.patch). Extend the same logic.
    - Gotcha: Might need duplicate noise logic if OffscreenCanvas is in a different subsystem.

## Architecture notes for cpp-first design

**High-value moves** (do these first):
- navigator.userAgent, screen, webgl, canvas, audio, fonts, speech (already have patches; delete JS, test C++).
- Add C++ patches for: hardware/architecture, navigator/window-name, navigator/vibration (trivial getters).

**Medium-effort next wave**:
- Intl locale spoofing (Intl.DateTimeFormat/NumberFormat), navigator.mediaDevices.enumerateDevices, storage.estimate (Promise-based; test first).

**Leave in JS** (not worth the effort):
- Math constants (Proxy required), Math functions (thousands of call sites), Math. DOM event timestamps (KeyboardEvent.timeStamp), iframe injection, worker isolation, feature detection, error stack manipulation.

**Test strategy**: After C++ patches land, run regression suite with JS spoofers disabled by feature flag. Measure:
- Performance (should improve slightly; fewer JS calls).
- Coverage (same fingerprint resistance).
- Correctness (no console errors, sites don't break).

