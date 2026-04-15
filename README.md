# Cloakfox

A daily-driver privacy browser with **C++ level fingerprint spoofing** and **per-container, per-domain identity isolation**.

Hard fork of [Camoufox](https://github.com/daijro/camoufox) (Firefox with 19+ C++ engine patches) + a bundled extension (Cloakfox Shield) for container management and fingerprint configuration.

## Why

JS-based fingerprint spoofing has fundamental limitations that can't be solved from an extension:

| Vector | JS Extension | C++ Engine Patch |
|--------|-------------|-----------------|
| Canvas pixel buffer | Intercept after GPU render (detectable) | Noise in rendering pipeline |
| AudioWorklet | Separate thread, bypassable | Patched in audio pipeline |
| CSS font metrics | Cannot control layout engine | Patched in HarfBuzz |
| TLS/JA3 fingerprinting | Cannot touch | Handled at network stack |
| WebRTC ICE candidates | Timing gaps in JS interception | Intercepted at SDP level |
| Function.prototype.toString | Patched but detectable | Genuinely native code |

Camoufox solves these at the C++ level, but lacks container support and daily-driver features. Cloakfox adds both.

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Cloakfox Browser              │
│                                                  │
│  C++ Engine (Gecko + 19 Camoufox patches)        │
│  ├── CanvasFingerprintManager                    │
│  ├── AudioFingerprintManager                     │
│  ├── NavigatorManager                            │
│  ├── ScreenDimensionManager                      │
│  ├── FontListManager / FontSpacingSeedManager    │
│  ├── WebGLParamsManager                          │
│  ├── WebRTCIPManager                             │
│  ├── TimezoneManager                             │
│  └── RoverfoxStorageManager (per-container IPC)  │
│              ▲                                   │
│              │ window.setCanvasSeed()             │
│              │ window.setNavigatorPlatform()      │
│              │ ... (16 self-destructing methods)  │
│              │                                   │
│  Cloakfox Shield Extension                          │
│  ├── Background: container mgmt, config inject   │
│  ├── Inject: calls window.setXxx() per-domain    │
│  ├── Content: MAIN ↔ ISOLATED world bridge       │
│  └── Popup: React UI (6 tabs)                    │
│                                                  │
│  Config: policies.json + cloakfox.cfg               │
│  (daily-driver defaults, privacy hardened)        │
└─────────────────────────────────────────────────┘
```

**Per-domain fingerprinting flow:**
1. User navigates to `example.com` in Container-1
2. Background derives domain seed: `SHA-256(containerSeed + "example.com")`
3. Injects seed into MAIN world via `scripting.executeScript`
4. Inject script calls `window.setCanvasSeed(seed)`, `window.setNavigatorPlatform(...)`, etc.
5. C++ managers store values keyed by `mUserContextId` — self-destructing methods delete themselves
6. Same container + same domain = identical fingerprint across reloads
7. Different container or different domain = completely different fingerprint

## Building

### Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop/) (16GB+ RAM allocated)
- [Node.js](https://nodejs.org/) (for extension development only)

### Full build (Docker)

```bash
make docker
```

This builds a Linux binary in a Docker container. Output goes to `dist/`.

### Extension only (native)

```bash
cd extension
npm ci
npm test        # 32 unit tests
npm run build   # production build
```

### Build targets

```bash
make help         # Show all targets

# Docker (recommended)
make docker       # Full build in Docker
make docker-shell # Debug shell inside build container

# Native (requires Firefox build toolchain)
make fetch        # Download Firefox 135.0.1 source
make setup        # Extract and init git repo
make patch        # Apply 19 C++ patches
make additions    # Copy MaskConfig, branding
make config       # Copy policies, prefs, mozconfig
make extension    # Build Cloakfox Shield extension
make build        # Compile Firefox
make run          # Launch browser
```

## Repo Structure

```
├── patches/
│   ├── fingerprint/    # 13 C++ spoofing patches from Camoufox
│   └── infra/          # 6 infrastructure patches
├── additions/          # MaskConfig.hpp, branding assets (from Camoufox)
├── config/             # policies.json, cloakfox.cfg, chrome.css
├── extension/          # Cloakfox Shield (TypeScript, React)
│   ├── src/
│   │   ├── background/ # Container manager, config injector
│   │   ├── inject/     # Cloakfox bridge, fingerprint monitor
│   │   ├── content/    # MAIN ↔ ISOLATED world bridge
│   │   ├── popup/      # React UI (6 tabs)
│   │   └── lib/        # PRNG, domain matcher, profiles
│   └── tests/unit/     # 32 Vitest tests
├── scripts/            # Build automation
├── Dockerfile          # Reproducible Linux build
├── Makefile            # Build orchestrator
└── PLAN.md             # Full implementation plan
```

## Patches

### Kept from Camoufox (19)

**Fingerprint spoofing (13):** anti-font-fingerprinting, audio-context-spoofing, fingerprint-injection, font-hijacker, geolocation-spoofing, locale-spoofing, media-device-spoofing, network-patches, screen-hijacker, timezone-spoofing, voice-spoofing, webgl-spoofing, webrtc-ip-spoofing

**Infrastructure (6):** all-addons-private-mode, browser-init, chromeutil, config, force-default-pointer, shadow-root-bypass

### Removed (7)

no-css-animations, no-search-engines, disable-extension-newtab, disable-remote-subframes, global-style-sheets, pin-addons, windows-theming-bug-modified — these break daily-driver functionality.

## Status

**Milestone 1: "It Builds"** — Complete
- 19 patches applied, Firefox compiles with 0 errors
- Cloakfox Shield extension scaffold with 32 passing tests
- Docker build pipeline working

**Milestone 2: "Daily Driver"** — Next
- Verify browser launches and daily-driver features work
- Verify `window.setCanvasSeed` and other C++ APIs exist

See [PLAN.md](PLAN.md) for the full 6-milestone roadmap.

## FAQ

### macOS says "Cloakfox can't be opened because Apple cannot check it for malicious software"

This is normal for unsigned apps. Go to **System Settings → Privacy & Security**, scroll down — you'll see a message about Cloakfox being blocked. Click **"Open Anyway"**.

Alternatively, run this in Terminal before first launch:
```bash
xattr -dr com.apple.quarantine /Applications/Cloakfox.app
```

## License

MPL-2.0 — same as Firefox/Camoufox.

## Credits

- [Camoufox](https://github.com/daijro/camoufox) by daijro — C++ fingerprint spoofing engine
- [Firefox](https://www.mozilla.org/firefox/) by Mozilla — browser foundation
- [LibreWolf](https://librewolf.net/) — data reporting and build patches
