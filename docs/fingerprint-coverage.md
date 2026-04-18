# Cloakfox fingerprint coverage

What every fingerprint signal looks like in Cloakfox — where the spoof happens, who feeds the value, and where the patch comes from.

## Legend

**Spoof site** — where the actual spoof lives:
- `C++` — Gecko/Firefox C++ patch (engine-level, undetectable to JS)
- `C++ (content-only)` — patched in a function that only runs for web content, browser UI is untouched
- `JS` — extension runtime hook, no C++ patch
- `pref` — static Firefox pref in `settings/cloakfox.cfg`
- `ext webRequest` — extension rewrites HTTP request/response via webRequest API

**Value source** — who decides what value to spoof to (for C++/JS signals):
- `extension` — per-container, per-domain generation via profile + PRNG
- `pref` — static from `cloakfox.cfg`
- `—` — static Firefox built-in (no value generation needed)

**Source columns** — where each patch originated:
- ☑ **Firefox** = native Firefox static / RFP handling
- ☑ **Camoufox** = pre-existing from upstream daijro/camoufox
- ☑ **Cloakfox** = new on this fork's `unified-maskconfig` branch

---

## Signals covered

| # | Signal / API | Spoof site | Value source | Firefox | Camoufox | Cloakfox |
|---|---|---|---|:---:|:---:|:---:|
| 1 | Canvas `getImageData`/`toDataURL` pixel fp | C++ | extension (setCanvasSeed) | ☐ | ☑ | ☐ |
| 2 | Canvas `measureText` TextMetrics | C++ | extension (canvas seed) | ☐ | ☐ | ☑ |
| 3 | OffscreenCanvas | C++ | extension (canvas seed) | ☐ | ☑ | ☐ |
| 4 | AudioBuffer fingerprint | C++ | extension (setAudioFingerprintSeed) | ☐ | ☑ | ☐ |
| 5 | OfflineAudioContext rendering | C++ | extension (audio seed) | ☐ | ☑ | ☐ |
| 6 | AudioContext `sampleRate`/`outputLatency`/`maxChannelCount` | C++ | extension (setCloakConfig) | ☐ | ☑ | ☐ |
| 7 | `navigator.userAgent` | C++ | extension (setNavigatorUserAgent) | ☐ | ☑ | ☐ |
| 8 | `navigator.platform` | C++ | extension (setNavigatorPlatform) | ☐ | ☑ | ☐ |
| 9 | `navigator.oscpu` | C++ | extension (setNavigatorOscpu) | ☐ | ☑ | ☐ |
| 10 | `navigator.appVersion` | C++ | extension (setCloakConfig) | ☐ | ☑ | ☐ |
| 11 | `navigator.language` / `.languages` | C++ | extension (setCloakConfig locale) | ☐ | ☑ | ☐ |
| 12 | `navigator.hardwareConcurrency` | C++ | extension (setNavigatorHardwareConcurrency) | ☐ | ☑ | ☐ |
| 13 | `navigator.maxTouchPoints` | C++ | extension (setCloakConfig) | ☐ | ☐ | ☑ |
| 14 | `navigator.webdriver` | C++ | extension (always false) | ☐ | ☐ | ☑ |
| 15 | `navigator.globalPrivacyControl` | C++ | extension (setCloakConfig) | ☐ | ☑ | ☐ |
| 16 | `navigator.gpu` (WebGPU) | C++ | extension (disable flag) | ☐ | ☐ | ☑ |
| 17 | `navigator.vibrate` | C++ | extension (disable flag) | ☐ | ☐ | ☑ |
| 18 | `navigator.getGamepads` | C++ | extension (disable flag) | ☐ | ☐ | ☑ |
| 19 | `navigator.requestMIDIAccess` | C++ | extension (disable flag) | ☐ | ☐ | ☑ |
| 20 | `navigator.requestMediaKeySystemAccess` (EME) | C++ | extension (disable flag) | ☐ | ☐ | ☑ |
| 21 | `navigator.clipboard.read`/`.write` | C++ | extension (disable flag) | ☐ | ☐ | ☑ |
| 22 | `navigator.permissions.query` | C++ | extension (spoof flag) | ☐ | ☐ | ☑ |
| 23 | `navigator.vendor` / `.product` / `.appName` | Firefox constant | — | ☑ | ☐ | ☐ |
| 24 | `navigator.buildID` | pref | pref | ☐ | ☐ | ☑ |
| 25 | `Notification.permission` / `.requestPermission` | C++ | extension (disable flag) | ☐ | ☐ | ☑ |
| 26 | WebGL `VENDOR` / `RENDERER` | C++ | extension (profile.gpu) | ☐ | ☑ | ☐ |
| 27 | WebGL `getParameter` (all params) | C++ | extension (setCloakConfig webGl:parameters) | ☐ | ☑ | ☐ |
| 28 | WebGL `getSupportedExtensions` | C++ | extension (setCloakConfig webGl:supportedExtensions) | ☐ | ☑ | ☐ |
| 29 | WebGL `getShaderPrecisionFormat` | C++ | extension (setCloakConfig) | ☐ | ☑ | ☐ |
| 30 | `screen.width`/`height`/`availWidth`/`availHeight` | C++ | extension (profile.screen via setScreenDimensions) | ☐ | ☑ | ☐ |
| 31 | `screen.colorDepth` / `screen.pixelDepth` | C++ | extension (setScreenColorDepth) | ☐ | ☑ | ☐ |
| 32 | `screen.orientation.type` | C++ | extension (mobile-aware) | ☐ | ☐ | ☑ |
| 33 | `window.innerWidth`/`innerHeight` | C++ | extension (setCloakConfig window:*) | ☐ | ☑ | ☐ |
| 34 | `window.outerWidth`/`outerHeight` | C++ | extension | ☐ | ☑ | ☐ |
| 35 | `window.screenX`/`screenY` | C++ | extension | ☐ | ☑ | ☐ |
| 36 | `window.scrollMaxX`/`Y`, `pageXOffset`/`Y` | C++ | extension | ☐ | ☑ | ☐ |
| 37 | `window.devicePixelRatio` | C++ | extension | ☐ | ☑ | ☐ |
| 38 | `window.visualViewport` scale/offsets | C++ | extension (spoof flag) | ☐ | ☐ | ☑ |
| 39 | `window.name` | C++ | extension (disable flag) | ☐ | ☐ | ☑ |
| 40 | `Element.getBoundingClientRect` | C++ | extension (canvas seed) | ☐ | ☐ | ☑ |
| 41 | `Element.getClientRects` | C++ | extension (canvas seed) | ☐ | ☐ | ☑ |
| 42 | `Element.offsetWidth`/`Height`/`Left`/`Top` | C++ | extension (canvas seed) | ☐ | ☐ | ☑ |
| 43 | `Range.getBoundingClientRect` / `getClientRects` | C++ | extension (canvas seed) | ☐ | ☐ | ☑ |
| 44 | `SVGTextContentElement.getComputedTextLength` | C++ | extension (canvas seed) | ☐ | ☐ | ☑ |
| 45 | `SVGGraphicsElement.getBBox` | C++ | extension (canvas seed) | ☐ | ☐ | ☑ |
| 46 | `Intl.DateTimeFormat().resolvedOptions().timeZone` / `Date.getTimezoneOffset()` | C++ | extension (profile-matched via setTimezone) | ☐ | ☑ | ☐ |
| 47 | `Intl.*` locale (language/region/script) | C++ | extension (setCloakConfig locale:*) | ☐ | ☑ | ☐ |
| 48 | `setTimeout` / `setInterval` jitter | C++ | extension (per-container seed) | ☐ | ☐ | ☑ |
| 49 | `performance.now()` precision | pref | pref | ☑ | ☐ | ☑ |
| 50 | `performance.timeOrigin` | Firefox RFP service | — | ☑ | ☐ | ☐ |
| 51 | `HTMLMediaElement.canPlayType()` | C++ | extension (codecs:spoof) | ☐ | ☐ | ☑ |
| 52 | `MediaSource.isTypeSupported()` | C++ | extension (codecs:spoof) | ☐ | ☐ | ☑ |
| 53 | `MediaCapabilities.decodingInfo` / `encodingInfo` | C++ | extension (spoof flag) | ☐ | ☐ | ☑ |
| 54 | `navigator.storage.estimate()` / `.persisted()` | C++ | extension (fake quota) | ☐ | ☐ | ☑ |
| 55 | `indexedDB.databases()` | C++ | extension (hide flag) | ☐ | ☐ | ☑ |
| 56 | Fonts enumeration (system font list) | C++ | extension (profile.fonts via setFontList) | ☐ | ☑ | ☐ |
| 57 | Font spacing seed (CSS font-width detection) | C++ | extension (setFontSpacingSeed) | ☐ | ☑ | ☐ |
| 58 | `speechSynthesis.getVoices()` | C++ | extension (platform-matched voices) | ☐ | ☑ | ☐ |
| 59 | WebRTC local IP (ICE candidates) | C++ | extension (profile IPs via setWebRTCIPv4/6) | ☐ | ☑ | ☐ |
| 60 | WebRTC mDNS hostnames | pref | pref | ☐ | ☐ | ☑ |
| 61 | `WebSocket` constructor | C++ | extension (block flag) | ☐ | ☐ | ☑ |
| 62 | `navigator.geolocation.*` | C++ | extension (profile coords via setGeolocation) | ☐ | ☑ | ☐ |
| 63 | `navigator.mediaDevices.enumerateDevices` | C++ | extension (fake counts via setMediaDeviceCounts) | ☐ | ☑ | ☐ |
| 64 | `navigator.getBattery()` | C++ + pref | extension per-container + pref disable | ☐ | ☑ | ☑ |
| 65 | `history.length` | C++ | extension (random via setHistoryLength) | ☐ | ☑ | ☐ |
| 66 | `document.lastModified` | C++ | extension (hide flag) | ☐ | ☐ | ☑ |
| 67 | `document.body.client*` rect | C++ | extension (setCloakConfig document.body.*) | ☐ | ☑ | ☐ |
| 68 | `@media (prefers-color-scheme)` | C++ (content-only) | extension (random per container) | ☐ | ☐ | ☑ |
| 69 | `@media (prefers-reduced-motion)` | C++ (content-only) | extension | ☐ | ☐ | ☑ |
| 70 | `@media (prefers-reduced-transparency)` | C++ (content-only) | extension | ☐ | ☐ | ☑ |
| 71 | `@media (prefers-contrast)` | C++ (content-only) | extension | ☐ | ☐ | ☑ |
| 72 | `@media (inverted-colors)` | C++ (content-only) | extension | ☐ | ☐ | ☑ |
| 73 | HTTP `User-Agent` header | C++ netwerk | extension (profile-matched) | ☐ | ☑ | ☐ |
| 74 | HTTP `Accept-Language` header | C++ netwerk | extension | ☐ | ☑ | ☐ |
| 75 | HTTP `Accept-Encoding` header | C++ netwerk | extension | ☐ | ☑ | ☐ |
| 76 | Client Hints headers (`Sec-CH-UA-*`) | ext webRequest | extension (profile-matched) | ☐ | ☐ | ☑ |
| 77 | `Error().stack` format | JS | extension (stealth.ts) | ☐ | ☐ | ☑ |
| 78 | `Function.prototype.toString` native-look | JS | extension (stealth.ts) | ☐ | ☐ | ☑ |
| 79 | iframe inheritance of all spoofs | JS fallback | extension (iframe-patcher) | ☐ | ☐ | ☑ |
| 80 | Worker thread navigator consistency | C++ WorkerNavigator | extension (shared MaskConfig) | ☐ | ☑ | ☐ |
| 81 | KeyboardEvent cadence timing | JS | extension (keyboard/cadence.ts) | ☐ | ☐ | ☑ |
| 82 | Feature detection consistency (`CSS.supports`, `hasFeature`) | JS | extension (features/feature-detection.ts) | ☐ | ☐ | ☑ |
| 83 | `Math.*` trig precision | JS | extension (math/math.ts) | ☐ | ☐ | ☑ |

## Per-container uniqueness / orchestration

The extension is the engine that makes everything per-container. Without it, the C++ patches default to real browser values.

| # | Extension responsibility | Layer | Source |
|---|---|---|---|
| 84 | Per-domain deterministic profile generation (UA, screen, fonts, GPU, timezone, locale) | JS (inject + background) | ☐ Firefox ☐ Camoufox ☑ Cloakfox |
| 85 | Per-container master seed + xorshift128+ sub-PRNG derivation | JS (inject) | ☐ Firefox ☐ Camoufox ☑ Cloakfox |
| 86 | Calls individual WebIDL setters at document_start (setCanvasSeed, setWebGLVendor, etc.) | JS (inject/core-bridge.ts) | ☐ Firefox ☐ Camoufox ☑ Cloakfox |
| 87 | Batched `setCloakConfig()` JSON for keys without individual setters | JS (inject/core-bridge.ts) | ☐ Firefox ☐ Camoufox ☑ Cloakfox |
| 88 | Container lifecycle (create / delete / rotate / persist) | JS (background) | ☐ Firefox ☐ Camoufox ☑ Cloakfox |
| 89 | Settings UI (popup, options page, signal monitor) | JS (React) | ☐ Firefox ☐ Camoufox ☑ Cloakfox |
| 90 | HTTP request header rewriting (`Sec-CH-UA-*`, etc.) | webRequest API | ☐ Firefox ☐ Camoufox ☑ Cloakfox |
| 91 | IP leak warning & proxy validation | JS (background) | ☐ Firefox ☐ Camoufox ☑ Cloakfox |

---

## Remaining not yet covered

| # | Signal | Proposed layer | Effort | Why not done |
|---|---|---|---|---|
| R1 | `@media (color-gamut)` | C++ nsMediaFeatures.cpp | low | low priority, rare FP signal |
| R2 | `@media (dynamic-range)` HDR | C++ nsMediaFeatures.cpp | low | rare |
| R3 | `@media (resolution)` DPI | C++ nsMediaFeatures.cpp | low | DPR already covered |
| R4 | `SVGGraphicsElement.getCTM` / `getScreenCTM` | C++ | low | SVG bbox already covers main vector |
| R5 | `SVGGeometryElement.getTotalLength` / `getPointAtLength` | C++ | low | rarely FP'd |
| R6 | `FontFaceSet.check()` | C++ | medium | font list + spacing seed already cover |
| R7 | `getComputedStyle()` font-family fallback | C++ | medium | font list covers primary vector |
| R8 | `HTMLMediaElement.duration` precision | C++ | medium | risk of breaking playback |
| R9 | `Document.compatMode` / `characterSet` / `contentType` | C++ | low | already static across all Firefox |
| R10 | Math trig precision | SpiderMonkey | high | JIT/debug risk; JS spoofer handles |
| R11 | `Error().stack` format at engine level | SpiderMonkey | high | JS spoofer handles |
| R12 | `KeyboardEvent.timeStamp` jitter at engine | C++ events | high | breaks input semantics; JS spoofer handles |
| R13 | TLS JA3/JA4 fingerprint | NSS (security/) | — | out of Gecko scope |
| R14 | HTTP/2 SETTINGS frame ordering | netwerk | high | rarely FP'd in practice |
| R15 | TCP stack fingerprint | OS | — | impossible from browser |

## Firefox doesn't implement — JS spoofers were deleted

These APIs don't exist in Firefox source (verified via `grep dom/webidl/`):
Web Bluetooth, WebUSB, WebSerial, WebHID, Generic Sensor API (Accelerometer/Gyroscope/etc.), `Screen.isExtended` (Window Management), Keyboard API (`navigator.keyboard`), Apple Pay, WebSQL, `performance.memory` (Chrome-only), `navigator.deviceMemory` (Chrome-only), NetworkInformation (disabled by default).
