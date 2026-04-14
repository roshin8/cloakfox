# Cloakfox: Implementation Plan

> **Project:** Cloakfox — daily-driver privacy browser with per-container, per-domain fingerprint isolation
> **Base:** Fork of Cloakfox (Firefox fork with 33+ C++ fingerprint spoofing patches)
> **Repo:** `cloakfox`
> **License:** Open source (MPL-2.0 / GPL-3.0)
> **Platform:** macOS (Apple Silicon) first

---

## 1. What We're Building

A daily-driver Firefox-based browser that:
- Spoofs 50+ fingerprinting APIs at the **C++ engine level** (undetectable by JS)
- Provides **per-container identity isolation** via Firefox Multi-Account Containers
- Generates **per-domain deterministic fingerprints** within each container
- Ships with a **bundled extension** (stripped ContainerShield) for container management, settings UI, and fingerprint monitoring
- Works as a normal browser (bookmarks, passwords, search, extensions, etc.)

### Why Not Just an Extension?

JS-level spoofing (ContainerShield's current approach) has fundamental limitations that C++ engine patches solve:

| Vector | JS Extension | C++ Engine Patch |
|--------|-------------|-----------------|
| TLS/JA3/JA4 fingerprinting | Cannot touch | Handled at network stack |
| HTTP/2 SETTINGS frame | Not interceptable | Patched in nsHttpHandler |
| Canvas pixel buffer | Intercept after GPU render (detectable) | Noise in rendering pipeline (native) |
| AudioWorklet | Separate thread, bypassable | Patched in audio pipeline |
| CSS font metrics | Cannot control layout engine | Patched in HarfBuzz/gfxPlatformFontList |
| ServiceWorker injection | Blocked by Firefox security | No injection needed, values are native |
| WebRTC ICE candidates | Timing gaps in JS interception | Intercepted at SDP protocol level |
| Cross-context consistency | Separate spoofer instances per iframe/worker | Automatic everywhere via C++ |
| Function.prototype.toString | Patched but patchable detection | Genuinely native code |
| Spoofer initialization overhead | 5-50ms detectable delay | Zero overhead |
| DOM property descriptors | Object.defineProperty (detectable) | Native getters, no descriptors to detect |
| Installed extension detection | Extension itself is detectable | No extension to detect (spoofing is built-in) |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Cloakfox Browser                │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │           C++ Engine Layer (Gecko)                 │  │
│  │                                                   │  │
│  │  33+ patches from Cloakfox:                       │  │
│  │  CanvasFingerprintManager    (pixel noise)        │  │
│  │  AudioFingerprintManager     (audio buffer noise) │  │
│  │  NavigatorManager            (UA, platform, cores) │  │
│  │  ScreenDimensionManager      (screen size, DPR)   │  │
│  │  FontListManager             (font filtering)     │  │
│  │  FontSpacingSeedManager      (glyph metrics)      │  │
│  │  WebGLParamsManager          (GPU strings)        │  │
│  │  WebRTCIPManager             (ICE candidates)     │  │
│  │  TimezoneManager             (tz override)        │  │
│  │  + network, locale, geolocation, speech, etc.     │  │
│  │                                                   │  │
│  │  RoverfoxStorageManager (cross-process, keyed     │  │
│  │    by mUserContextId = Firefox container ID)      │  │
│  │                                                   │  │
│  │  Self-destructing window.setXxx() methods         │  │
│  │  (entry points for extension to configure C++)    │  │
│  └───────────────────────────────────────────────────┘  │
│                          ▲                               │
│                          │ window.setCanvasSeed()        │
│                          │ window.setNavigatorPlatform() │
│                          │ window.setScreenDimensions()  │
│                          │ window.setFontList()          │
│                          │ ... etc                       │
│                          │                               │
│  ┌───────────────────────┴───────────────────────────┐  │
│  │        Bundled Extension (Cloakfox Shield)            │  │
│  │                                                   │  │
│  │  Background:                                      │  │
│  │    ContainerManager → Firefox contextualIdentities│  │
│  │    SettingsStore    → per-container + domain rules │  │
│  │    ProfileManager   → unique profile per container│  │
│  │    ConfigInjector   → delivers seed+profile to    │  │
│  │                       content script per page     │  │
│  │    HeaderSpoofer    → aligns HTTP headers w/ profile│
│  │    ProfileRotation  → auto-rotate fingerprints    │  │
│  │    CollisionDetector→ no duplicate fingerprints   │  │
│  │                                                   │  │
│  │  Inject (MAIN world, document_start):             │  │
│  │    CloakfoxBridge   → calls window.setXxx() with  │  │
│  │                       domain-specific seeds       │  │
│  │    FingerprintMonitor → tracks API access          │  │
│  │                                                   │  │
│  │  Content (ISOLATED world):                        │  │
│  │    MessageBridge    → page ↔ background relay     │  │
│  │                                                   │  │
│  │  Popup UI (React + Tailwind):                     │  │
│  │    Dashboard, Fingerprint, Signals, Headers,      │  │
│  │    Whitelist, Settings tabs                       │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Key Architectural Insight: Per-Domain via Self-Destructing Methods

Cloakfox's C++ managers already support per-container values via `mUserContextId`. They expose **self-destructing `window.setXxx()` methods** — JS functions that set a value in the C++ layer and then delete themselves from the window object.

The extension's content script (MAIN world, `document_start`) calls these methods with **domain-specific seeds** on every navigation. No MaskConfig or C++ changes needed.

**Flow:**
1. User navigates to `example.com` in Container-1
2. `webNavigation.onCommitted` fires in background
3. Background looks up Container-1's entropy seed + assigned profile
4. `browser.scripting.executeScript` injects `window.__CLOAKFOX__ = { seed, profile }` into MAIN world with `injectImmediately: true`
5. Inject content script reads `window.__CLOAKFOX__`, derives domain seed: `hash(containerSeed + "example.com")`
6. Calls `window.setCanvasSeed(derivedInt)`, `window.setNavigatorPlatform(profile.platform)`, etc.
7. Self-destructing methods store values in RoverfoxStorageManager keyed by `mUserContextId`
8. All subsequent API calls return C++-spoofed values
9. `window.__CLOAKFOX__` is deleted to prevent page access
10. User navigates to `other.com` → steps 2-9 repeat with different domain seed

---

## 3. Repository Structure

```
cloakfox/
├── Makefile                          # Build orchestrator
├── mozconfig                         # Firefox build config (macOS ARM)
├── UPSTREAM_VERSION                  # Pinned Cloakfox commit hash
│
├── patches/
│   ├── fingerprint/                  # 19 spoofing patches (from Cloakfox)
│   │   ├── canvas-spoofing.patch
│   │   ├── audio-fingerprint-manager.patch
│   │   ├── audio-context-spoofing.patch
│   │   ├── font-hijacker.patch
│   │   ├── font-list-spoofing.patch
│   │   ├── anti-font-fingerprinting.patch
│   │   ├── navigator-spoofing.patch
│   │   ├── network-patches.patch
│   │   ├── screen-spoofing.patch
│   │   ├── webgl-spoofing.patch
│   │   ├── geolocation-spoofing.patch
│   │   ├── locale-spoofing.patch
│   │   ├── timezone-spoofing.patch
│   │   ├── webrtc-ip-spoofing.patch
│   │   ├── media-device-spoofing.patch
│   │   ├── speech-voices-spoofing.patch
│   │   ├── voice-spoofing.patch
│   │   ├── fingerprint-injection.patch
│   │   └── cross-process-storage.patch
│   │
│   ├── infra/                        # 7 infrastructure patches (from Cloakfox)
│   │   ├── config.patch
│   │   ├── browser-init.patch
│   │   ├── chromeutil.patch
│   │   ├── force-default-pointer.patch
│   │   ├── shadow-root-bypass.patch
│   │   ├── all-addons-private-mode.patch
│   │   └── macos-sandbox-crash-fix.patch
│   │
│   └── cloakfox/                        # New patches for daily-driver
│       └── restore-daily-driver.patch  # Undo automation-hostile defaults
│
├── config/
│   ├── policies.json                 # Daily-driver enterprise policies
│   ├── cloakfox.cfg                     # AutoConfig prefs (replaces cloakfox.cfg)
│   └── local-settings.js            # AutoConfig loader
│
├── extension/                        # Bundled "Cloakfox Shield" extension
│   ├── manifest.json
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── background/              # Container mgmt, settings, profiles
│       ├── content/                 # Message bridge (ISOLATED world)
│       ├── inject/                  # Cloakfox bridge + monitor (MAIN world)
│       ├── popup/                   # React UI (6 tabs)
│       ├── pages/                   # Onboarding, options
│       ├── lib/                     # Crypto, domain matcher, profiles
│       ├── types/                   # TypeScript interfaces
│       └── constants/               # Message types, config
│
├── branding/                         # Cloakfox branding assets
│   ├── icon.svg
│   ├── about-dialog.html
│   └── newtab-logo.svg
│
├── scripts/
│   ├── fetch-firefox.sh             # Download Firefox ESR source
│   ├── apply-patches.sh             # Apply patches in order
│   ├── build-extension.sh           # npm ci && npm run build:prod
│   ├── bundle-extension.sh          # Copy XPI to distribution/extensions/
│   ├── package-dmg.sh               # Create macOS DMG
│   └── check-upstream.sh            # Diff against new Cloakfox releases
│
├── .cirrus.yml                       # Cirrus CI (full builds)
├── .github/workflows/
│   ├── build.yml                    # GitHub Actions (incremental)
│   └── release.yml                  # Tagged release → DMG artifact
│
└── tests/
    ├── unit/                         # Vitest
    │   ├── crypto.test.ts
    │   ├── domain-matcher.test.ts
    │   └── cloakfox-bridge.test.ts
    └── e2e/                          # Playwright
        ├── container-isolation.spec.ts
        ├── domain-consistency.spec.ts
        ├── daily-driver.spec.ts
        └── anti-detection.spec.ts
```

---

## 4. Patch Decisions

### 4.1 KEEP — Fingerprint Spoofing (19 patches)

| Patch | What it does | C++ Manager |
|-------|-------------|-------------|
| `canvas-spoofing` | Deterministic pixel noise in getImageData/toDataURL/toBlob | CanvasFingerprintManager |
| `audio-fingerprint-manager` | 0.8% variance audio buffer transformation | AudioFingerprintManager |
| `audio-context-spoofing` | Sample rate, latency, channel count via MaskConfig | MaskConfig direct |
| `font-hijacker` | Font whitelist at gfxPlatformFontList level | MaskConfig direct |
| `font-list-spoofing` | Per-context font allowlists | FontListManager |
| `anti-font-fingerprinting` | HarfBuzz glyph spacing modification | FontSpacingSeedManager |
| `navigator-spoofing` | Platform, oscpu, UA, hardwareConcurrency | NavigatorManager |
| `network-patches` | UA, Accept-Language, Accept-Encoding in nsHttpHandler | MaskConfig direct |
| `screen-spoofing` | Screen width/height/colorDepth | ScreenDimensionManager |
| `webgl-spoofing` | Vendor, renderer, extensions, shader precision | WebGLParamsManager |
| `geolocation-spoofing` | Lat/long/accuracy in Geolocation.cpp | MaskConfig direct |
| `locale-spoofing` | Language/region/script | MaskConfig direct |
| `timezone-spoofing` | Per-realm timezone override | TimezoneManager |
| `webrtc-ip-spoofing` | ICE candidate IP replacement at SDP level | WebRTCIPManager |
| `media-device-spoofing` | Mic/webcam/speaker counts | MaskConfig direct |
| `speech-voices-spoofing` | Voice filtering per-context | SpeechVoicesManager |
| `voice-spoofing` | Fake voice synthesis | MaskConfig direct |
| `fingerprint-injection` | Central DOM property interception | MaskConfig direct |
| `cross-process-storage` | RoverfoxStorageManager IPC for parent-child sync | RoverfoxStorageManager |

### 4.2 KEEP — Infrastructure (7 patches)

| Patch | Why |
|-------|-----|
| `config` | Integrates config files into Firefox build |
| `browser-init` | Browser initialization with fingerprinting resistance |
| `chromeutil` | Chrome utility modifications |
| `force-default-pointer` | Consistent pointer behavior |
| `shadow-root-bypass` | Shadow DOM access for spoofing |
| `all-addons-private-mode` | Extensions work in private browsing |
| `macos-sandbox-crash-fix` | macOS stability |

### 4.3 REMOVE (8+ patches)

| Patch | Why Remove |
|-------|-----------|
| `no-css-animations` | Daily driver needs CSS animations |
| `no-search-engines` | Users need search engines |
| `disable-extension-newtab` | Extensions need new tab pages |
| `disable-remote-subframes` | Breaks cross-origin iframes on real sites |
| `0-playwright` | Not an automation browser |
| `1-leak-fixes` | Playwright-specific |
| `global-style-sheets` | Don't inject custom chrome.css that hides UI |
| `pin-addons` | Users manage their own extensions |
| `ghostery/*` | Users install their own adblocker |
| `librewolf/*` | Evaluate individually; likely remove most |

### 4.4 NEW — `restore-daily-driver.patch`

Reverses any remaining daily-driver-hostile behavior from `config.patch` and `browser-init.patch` that we can't fix via prefs alone. Minimal C++ changes.

---

## 5. Config Restoration (Daily-Driver Defaults)

### 5.1 `config/policies.json`

```json
{
  "policies": {
    "DisableTelemetry": true,
    "DisablePocket": true,
    "DisableFirefoxStudies": true,
    "DisableFirefoxAccounts": false,
    "OverrideFirstRunPage": "",
    "SearchEngines": {
      "Default": "DuckDuckGo"
    },
    "ExtensionSettings": {
      "cloakfox-shield@cloakfox": {
        "installation_mode": "force_installed",
        "install_url": "file:///path/to/cloakfox-shield.xpi"
      }
    },
    "Bookmarks": [],
    "EnableTrackingProtection": {
      "Value": true,
      "Fingerprinting": false
    }
  }
}
```

Key: `Fingerprinting: false` disables Firefox's built-in RFP (resistFingerprinting) which would conflict with Cloakfox's C++ patches. RFP makes everyone look the same; we want per-container uniqueness.

### 5.2 `config/cloakfox.cfg`

**Re-enable daily-driver features:**
```javascript
// Search and URL bar
pref("browser.urlbar.suggest.searches", true);
pref("browser.urlbar.suggest.history", true);
pref("browser.urlbar.suggest.bookmark", true);
pref("browser.urlbar.suggest.topsites", true);
pref("browser.urlbar.maxRichResults", 10);

// New tab page
pref("browser.newtabpage.enabled", true);
pref("browser.newtabpage.activity-stream.feeds.topsites", true);

// Passwords and forms
pref("signon.rememberSignons", true);
pref("browser.formfill.enable", true);

// Reader mode
pref("reader.parse-on-load.enabled", true);

// Tab management
pref("browser.tabs.warnOnClose", true);
pref("browser.tabs.tabmanager.enabled", true);

// Spell check
pref("layout.spellcheckDefault", 1);
```

**Keep privacy-hardened:**
```javascript
// DO NOT enable resistFingerprinting (conflicts with C++ patches)
pref("privacy.resistFingerprinting", false);

// Container support (critical)
pref("privacy.userContext.enabled", true);
pref("privacy.userContext.ui.enabled", true);

// Cookie isolation
pref("network.cookie.cookieBehavior", 5);  // dFPI

// Strict referrer
pref("network.http.referer.XOriginPolicy", 2);

// No geolocation by default
pref("geo.enabled", false);

// No remote debugging
pref("devtools.debugger.remote-enabled", false);
```

---

## 6. Extension: Cloakfox Shield

### 6.1 What to REMOVE from ContainerShield

**Entire `src/inject/spoofers/` directory** — all 66 JS spoofer modules. C++ handles all spoofing now.

**Files to remove:**
- `src/inject/spoofers/**/*` (66 modules across 22 categories)
- `src/lib/stealth.ts` (Function.prototype.toString patching — not needed, C++ functions are genuinely native)
- `src/lib/farbling.ts` (noise injection — done by C++ patches)

### 6.2 What to KEEP from ContainerShield

**Background (all):**
- `container-manager.ts` — Firefox container API (contextualIdentities)
- `settings-store.ts` — per-container settings + domain rule merging
- `profile-manager.ts` — unique profile per container + collision detection
- `collision-detector.ts` — cross-container fingerprint similarity
- `header-spoofer.ts` — HTTP header alignment (UA, Accept-Language)
- `profile-rotation.ts` — automatic fingerprint rotation
- `message-handler.ts` — inter-component messaging
- `statistics-store.ts`, `badge-manager.ts`, `context-menu.ts`, `keyboard-shortcuts.ts`, `ip-isolation.ts`, `dns-protection.ts`

**Libraries:**
- `lib/crypto.ts` — PRNG (xorshift128+), seed derivation, SHA-256
- `lib/domain-matcher.ts` — wildcard/regex/suffix domain matching
- `lib/profiles/` — UA profiles and screen sizes
- `lib/protection-presets.ts`

**Content bridge:**
- `content/index.ts` — MAIN ↔ ISOLATED world message relay

**Monitor:**
- `inject/monitor/fingerprint-monitor.ts` — tracks API access attempts

**UI (all):**
- `popup/` — all 6 tabs (Dashboard, Fingerprint, Signals, Headers, Whitelist, Settings)
- `pages/` — onboarding, options, IP warning, test runner

**Types and constants:**
- `types/`, `constants/`

### 6.3 What to ADD: New Files

#### `extension/src/inject/cloakfox-bridge.ts`

Replaces the entire spoofers directory. Single responsibility: call Cloakfox's `window.setXxx()` methods with domain-specific deterministic values.

```typescript
// Pseudocode — actual implementation will follow this structure

import { PRNG } from '../lib/crypto';
import type { AssignedProfile, SpooferSettings } from '../types';

export async function configureCloakfoxSpoofing(
  containerSeed: string,
  domain: string,
  profile: AssignedProfile,
  settings: SpooferSettings
): Promise<void> {
  // Derive domain-specific seed
  const domainSeed = await PRNG.fromDerivedKey(containerSeed, domain, 'master');
  
  // Canvas (if enabled)
  if (settings.graphics?.canvas !== 'off' && typeof window.setCanvasSeed === 'function') {
    window.setCanvasSeed(domainSeed.nextInt(1, 2147483647));
  }
  
  // Audio (if enabled)
  if (settings.audio?.context !== 'off' && typeof window.setAudioFingerprintSeed === 'function') {
    window.setAudioFingerprintSeed(domainSeed.nextInt(1, 2147483647));
  }
  
  // Navigator
  if (settings.navigator?.userAgent !== 'off' && typeof window.setNavigatorPlatform === 'function') {
    window.setNavigatorPlatform(profile.userAgent.platform);
    window.setNavigatorUserAgent(profile.userAgent.userAgent);
    window.setNavigatorHardwareConcurrency(profile.hardwareConcurrency);
  }
  
  // Screen
  if (settings.hardware?.screen !== 'off' && typeof window.setScreenDimensions === 'function') {
    window.setScreenDimensions(profile.screen.width, profile.screen.height);
    window.setScreenColorDepth(profile.screen.colorDepth);
  }
  
  // Fonts
  if (settings.fonts?.enumeration !== 'off' && typeof window.setFontList === 'function') {
    const fontSubset = selectPlatformFonts(profile.userAgent.platform, domainSeed);
    window.setFontList(fontSubset.join(','));
    window.setFontSpacingSeed(domainSeed.nextInt(1, 2147483647));
  }
  
  // WebRTC
  if (settings.network?.webrtc !== 'off' && typeof window.setWebRTCIPv4 === 'function') {
    window.setWebRTCIPv4(generateDeterministicIP(domainSeed));
  }
  
  // ... additional managers as available
}
```

#### `extension/src/background/config-injector.ts`

Delivers container-specific seeds to the MAIN world inject script before page scripts run.

```typescript
// Pseudocode

import { ContainerManager } from './container-manager';
import { SettingsStore } from './settings-store';
import { ProfileManager } from './profile-manager';

export class ConfigInjector {
  constructor(
    private containers: ContainerManager,
    private settings: SettingsStore,
    private profiles: ProfileManager
  ) {
    // Listen for navigations
    browser.webNavigation.onCommitted.addListener((details) => {
      this.injectConfig(details.tabId, details.url);
    });
  }

  private async injectConfig(tabId: number, url: string): Promise<void> {
    const domain = new URL(url).hostname;
    const containerId = await this.containers.getContainerForTab(tabId);
    const entropy = await this.settings.getEntropy(containerId);
    const profile = await this.profiles.getAssignedProfile(containerId);
    const settings = await this.settings.getSettingsForDomain(containerId, domain);

    // Inject config into MAIN world before content scripts run
    await browser.scripting.executeScript({
      target: { tabId },
      world: 'MAIN',
      injectImmediately: true,
      func: (config) => {
        (window as any).__CLOAKFOX__ = config;
      },
      args: [{
        seed: entropy.seed,
        domain,
        profile,
        settings: settings.spoofers
      }]
    });
  }
}
```

#### `extension/src/inject/index.ts` (rewritten)

Shrinks from ~180 lines to ~30. Reads config, calls bridge, cleans up.

```typescript
// Pseudocode

import { configureCloakfoxSpoofing } from './cloakfox-bridge';
import { initFingerprintMonitor } from './monitor/fingerprint-monitor';
import { generateFallbackSeed } from '../lib/crypto';

(async () => {
  const domain = window.location.hostname;
  
  // Read config injected by background (via config-injector.ts)
  const config = (window as any).__CLOAKFOX__;
  delete (window as any).__CLOAKFOX__;  // Prevent page access
  
  if (config) {
    await configureCloakfoxSpoofing(
      config.seed,
      config.domain,
      config.profile,
      config.settings
    );
  } else {
    // Fallback: domain-only seed (no container context available)
    const fallbackSeed = generateFallbackSeed(domain);
    // Still call bridge with default profile
    await configureCloakfoxSpoofing(fallbackSeed, domain, DEFAULT_PROFILE, DEFAULT_SETTINGS);
  }
  
  // Monitor fingerprint access attempts (for popup display)
  initFingerprintMonitor();
  
  // Notify content script that spoofing is active
  window.postMessage({ type: 'CLOAKFOX_ACTIVE', domain }, '*');
})();
```

### 6.4 Popup UI Changes

Minimal modifications to existing tabs:

- **Signals Tab**: Each category shows "C++ Protected" badge instead of JS spoofer toggles. Toggle still works (controls whether bridge calls that window.setXxx method).
- **Dashboard Tab**: Add "Engine: C++" status indicator. If `window.setCanvasSeed` doesn't exist (running in vanilla Firefox), show warning: "Running without C++ engine — JS fallback active."
- **All other tabs**: No changes.

### 6.5 Extension Bundling

Built extension XPI placed at `distribution/extensions/cloakfox-shield@cloakfox.xpi` in Firefox source tree. Firefox auto-loads extensions from this directory on startup. Force-installed via `policies.json` so users can't accidentally uninstall it (but can disable).

---

## 7. Build System

### 7.1 Makefile

```makefile
FIREFOX_VERSION := 128.0           # Match Cloakfox's base
CLOAKFOX_VERSION := v0.x.x         # Pinned upstream tag

.PHONY: all fetch patch config extension build package clean

all: fetch patch config extension build package

fetch:
    scripts/fetch-firefox.sh $(FIREFOX_VERSION)

patch:
    scripts/apply-patches.sh

config:
    cp config/policies.json firefox-src/distribution/policies.json
    cp config/cloakfox.cfg firefox-src/defaults/pref/cloakfox.cfg
    cp config/local-settings.js firefox-src/defaults/pref/local-settings.js

extension:
    cd extension && npm ci && npm run build:prod
    scripts/bundle-extension.sh

build:
    cd firefox-src && ./mach build

package:
    scripts/package-dmg.sh
```

### 7.2 mozconfig (macOS Apple Silicon)

```
ac_add_options --enable-application=browser
ac_add_options --enable-optimize
ac_add_options --disable-debug
ac_add_options --disable-tests
ac_add_options --disable-crashreporter
ac_add_options --disable-updater
ac_add_options --disable-telemetry
ac_add_options --with-ccache=ccache
mk_add_options MOZ_MAKE_FLAGS="-j$(sysctl -n hw.ncpu)"
```

### 7.3 CI/CD

**Cirrus CI** (`.cirrus.yml`) — free for open source, no time limit:
- Full builds on macOS ARM
- ccache persisted between builds (keyed by patch checksums)
- Build artifact: DMG uploaded to GitHub Releases

**GitHub Actions** (`.github/workflows/build.yml`):
- Incremental builds on `macos-14` runners (Apple Silicon)
- ccache via `actions/cache`
- PR validation: extension unit tests + type-check (fast, no Firefox build)
- Release workflow: trigger Cirrus CI full build on tag push

---

## 8. Testing Strategy

### 8.1 Unit Tests (Vitest — fast, run on every PR)

**Keep from ContainerShield:**
- `crypto.test.ts` — PRNG determinism, seed derivation
- `domain-matcher.test.ts` — pattern matching
- `validation.test.ts` — input validation

**Remove:**
- All `spoofers/*.test.ts` — JS spoofers no longer exist

**Add:**
- `cloakfox-bridge.test.ts`:
  - Mock `window.setXxx()` methods
  - Verify: same container+domain → same seeds passed to C++
  - Verify: different domains → different seeds
  - Verify: different containers → different seeds
  - Verify: settings.graphics.canvas === 'off' → `setCanvasSeed` not called
  - Verify: missing `window.setXxx` → graceful skip (no throw)

### 8.2 E2E Tests (Playwright — run on full builds)

- **Container isolation**: Open same site in 2 containers, extract canvas fingerprint via `toDataURL()`, verify they differ
- **Domain consistency**: Visit site, navigate away, return — verify `toDataURL()` is identical
- **Cross-domain isolation**: Visit site A and site B in same container — verify canvas fingerprints differ
- **Daily-driver smoke test**: Search bar works, bookmarks saveable, password manager functional, CSS animations play
- **Anti-detection**: Run against CreepJS, BrowserLeaks, FingerprintJS, Pixelscan — verify no "bot detected" flags

---

## 9. Phased Milestones

### Milestone 1: "It Builds" — Week 1-2

**Goal:** Cloakfox compiles on macOS ARM with selected patches, boots to a working browser.

- [ ] Create repo with Makefile and scripts
- [ ] Fetch Firefox ESR source matching Cloakfox's base version
- [ ] Copy 26 patches (19 fingerprint + 7 infra) from Cloakfox
- [ ] Apply patches and build
- [ ] Verify browser launches
- [ ] Verify `window.setCanvasSeed` exists in devtools console

### Milestone 2: "Daily Driver" — Week 2-3

**Goal:** Browser works for daily use — search, bookmarks, passwords, animations.

- [ ] Remove automation patches (Playwright, no-search-engines, etc.)
- [ ] Write `policies.json` and `cloakfox.cfg` with daily-driver defaults
- [ ] Create `restore-daily-driver.patch` for any remaining issues
- [ ] Verify: DuckDuckGo search works, bookmarks save, passwords autofill
- [ ] Verify: CSS animations play, extensions installable, new tab page works
- [ ] Verify: Multi-Account Containers UI visible in toolbar

### Milestone 3: "Extension Bridge" — Week 3-5

**Goal:** Per-container, per-domain fingerprint isolation working end-to-end.

- [ ] Fork ContainerShield into `extension/` directory
- [ ] Remove all 66 JS spoofer modules + stealth.ts + farbling.ts
- [ ] Implement `cloakfox-bridge.ts`
- [ ] Implement `config-injector.ts`
- [ ] Rewrite `inject/index.ts`
- [ ] Bundle extension into browser build
- [ ] E2E test: two containers visiting same site → different canvas fingerprints
- [ ] E2E test: same container revisiting site → identical canvas fingerprint
- [ ] E2E test: same container, different domains → different fingerprints

### Milestone 4: "Polish" — Week 5-7

**Goal:** Production-quality experience.

- [ ] Update Signals tab UI ("C++ Protected" badges)
- [ ] Add engine status indicator to Dashboard
- [ ] Header alignment (UA, Accept-Language match C++ profile)
- [ ] Collision detection across containers
- [ ] Profile rotation (hourly/daily/weekly)
- [ ] Domain whitelist/exceptions
- [ ] CreepJS score testing and tuning
- [ ] Performance profiling (page load overhead)
- [ ] Branding (app icon, about dialog, window title)
- [ ] Onboarding page for first run

### Milestone 5: "CI and Distribution" — Week 7-8

**Goal:** Automated builds and public releases.

- [ ] Cirrus CI config for macOS full builds
- [ ] GitHub Actions for PR validation (extension tests only)
- [ ] Release workflow: tag → build → DMG artifact
- [ ] README with installation instructions
- [ ] Self-signed macOS code signing for alpha

### Milestone 6: "Advanced" — Week 9+

**Goal:** Expand platform support and features.

- [ ] Linux build (AppImage or .deb)
- [ ] Windows build (installer)
- [ ] Proxy-per-container support (optional future feature)
- [ ] Custom new tab page with container quick-launch
- [ ] Cross-device settings sync via Firefox Accounts
- [ ] Mouse/scroll behavioral biometric defense (research)

---

## 10. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Timing race**: inject script runs before `__CLOAKFOX__` config arrives | Wrong fingerprint for first page load | `injectImmediately: true` (Firefox 128+); fallback domain-only seed as safety net |
| **Cloakfox patches don't apply** to target Firefox ESR | Build fails | Pin to exact Firefox version Cloakfox uses; test patch application in CI |
| **`window.setXxx()` API changes** in upstream Cloakfox | Bridge breaks silently | `typeof` checks before every call; pin upstream version |
| **C++ patches conflict** with daily-driver features | Site breakage | Test each removed patch individually; keep `disable-remote-subframes` removal last |
| **macOS code signing** | Gatekeeper blocks unsigned app | Self-sign for alpha; Apple Developer ID ($99/yr) for public release |
| **No C++ experience** | Can't debug patch issues | Minimize new C++ (zero new patches for MVP); existing patches are battle-tested |
| **Firefox ESR version bumps** | Patches may not apply to new base | Track Cloakfox upstream; they maintain patch compatibility |
| **Extension XPI bundling** | Firefox may not auto-load | Test `distribution/extensions/` path; fallback to `policies.json` force-install |

---

## 11. Key Files Reference

### From ContainerShield (to keep/modify):
- `src/background/container-manager.ts` — Firefox container API
- `src/background/settings-store.ts` — per-container settings + domain rules
- `src/background/profile-manager.ts` — unique profile assignment
- `src/background/header-spoofer.ts` — HTTP header alignment
- `src/background/message-handler.ts` — IPC routing
- `src/lib/crypto.ts` — PRNG, seed derivation (foundation of determinism)
- `src/lib/domain-matcher.ts` — wildcard/regex domain matching
- `src/content/index.ts` — MAIN ↔ ISOLATED bridge
- `src/inject/monitor/fingerprint-monitor.ts` — API access tracking
- `src/popup/` — all React UI components

### New files to create:
- `extension/src/inject/cloakfox-bridge.ts` — calls window.setXxx() with domain seeds
- `extension/src/background/config-injector.ts` — delivers seeds to MAIN world
- `extension/src/inject/index.ts` — rewritten (30 lines, reads config + calls bridge)

### From Cloakfox (patches to copy):
- `patches/canvas-spoofing.patch` — CanvasFingerprintManager
- `patches/audio-fingerprint-manager.patch` — AudioFingerprintManager
- `patches/navigator-spoofing.patch` — NavigatorManager (uses mUserContextId)
- `patches/cross-process-storage.patch` — RoverfoxStorageManager
- (+ 22 more patches listed in Section 4)
