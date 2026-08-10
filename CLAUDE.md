# Cloakfox

Daily-driver privacy browser: Camoufox (C++ fingerprint spoofing) + ContainerShield (per-container, per-domain identity isolation).

## What This Is

A hard fork of Camoufox (Firefox 146.0.1 fork with C++ engine patches) transformed into a daily-use browser with:
- C++ level fingerprint spoofing (canvas, audio, fonts, WebGL, navigator, screen, WebRTC, etc.)
- Firefox Multi-Account Containers with per-container unique fingerprints
- Per-domain deterministic fingerprinting within each container
- Bundled "Cloakfox Shield" extension for container management, settings UI, monitoring

## Architecture

Three layers:
1. **C++ Engine** — Camoufox + LibreWolf patches (~36 total) applied to Firefox 146.0.1. Spoofs APIs at native level via self-destructing `window.setXxx()` methods.
2. **Cloakfox Shield Extension** — Stripped ContainerShield. Popup UI plus a parent-process pref/persona bridge (`experiment-apis/cloakfox.js`). NO content or inject scripts — see "Spoofer Architecture (cpp-first)" below.
3. **Config** — `policies.json` + `cloakfox.cfg` restore daily-driver features (search, bookmarks, passwords) while keeping privacy hardened.

## Build

```bash
make fetch           # Download Firefox 146.0.1 source tarball
make setup-minimal   # Extract source + copy additions/ (policies, cloakcfg, extension)
make dir             # Apply all patches (ordered via patches/order.txt)
make extension       # Build Cloakfox Shield extension in-place
make build           # Compile Firefox (45-90 min on Apple Silicon)
make package-macos   # Create macOS DMG (also: package-linux, package-windows)
```

## Repo Structure

- `patches/` — Flat directory of all C++ engine patches (29 top-level + 7 in `patches/librewolf/`)
- `patches/order.txt` — Explicit apply order; overrides alphabetical default
- `settings/` — policies.json, cloakfox.cfg, local-settings.js
- `additions/cloakcfg/` — MaskConfig.hpp, MouseTrajectories.hpp, json.hpp (copied into firefox-src)
- `additions/browser/extensions/cloakfox-shield/` — Cloakfox Shield extension (TypeScript, React, Tailwind)
- `scripts/` — Build automation scripts (patch.py, fetch-firefox.sh, copy-additions.sh, package.py)
- `branding/` — App icons and about dialog assets
- `tests/` — `tests/fingerprint/` is the live suite (selenium probes + node/pytest unit
  tests). `tests/async*/` and `tests/golden-firefox/` are inherited Playwright E2E
  suites that do NOT run on this branch (no Juggler); `tests/conftest.py` is their
  Playwright fixture file and breaks pytest collection, hence `--noconftest`.

## Spoofer Architecture (cpp-first)

Spoofing happens in two layers on this branch — NO MAIN-world inject/spoofer
extension code (that pre-pivot design was removed):

- **C++ patches** (`patches/`) — canvas, audio, webgl, navigator UA/platform/
  oscpu, screen, fonts, timezone, etc. Read per-container overlays from
  `cloak_cfg_<ucid>` prefs via `MaskConfig`.
- **JSWindowActors** (`additions/browser/components/cloakfox/actors/`) — 10
  chrome-principal `*Child`/`*Parent` pairs for the "must-stay-JS" vectors C++
  can't reach: Math, Keyboard, Timing, Gamepad, Midi, FeatureDetect,
  TabHistory, Timezone, WebGPU, WebRTC. Each `*Child` patches page objects via
  `Cu.exportFunction` on `DOMDocElementInserted`, gated on `cloakfox.enabled`.
  Patch spoofs on the PROTOTYPE with native descriptor flags, never the
  instance — an own property leaks the tamper via `Object.keys()`.
- **cloakfox-shield extension** (`additions/browser/extensions/cloakfox-shield/`)
  — popup UI + `experiment-apis/cloakfox.js` (parent-process pref/persona
  bridge). No content/inject scripts.
- **Persona/seed** (`additions/browser/components/cloakfox/`) —
  `CloakfoxPersonas`, `CloakfoxBFNetwork` (BrowserForge Bayesian net),
  `CloakfoxSeedSync` (parent → `Services.cpmm.sharedData` for the actors).

## Critical Constraints

- C++ patches MUST be applied before `./mach build` — they modify Gecko source directly
- `privacy.resistFingerprinting` MUST be false — RFP conflicts with C++ patches (makes everyone identical; we want per-container uniqueness)
- `privacy.userContext.enabled` MUST be true — containers are the foundation
- Same container + same domain MUST produce identical fingerprints across reloads
- Don't add console.log to any code that runs in page scope (detectable by fingerprinting sites)

## Code Style

- TypeScript strict mode, no `any` unless wrapping browser APIs that lack types
- camelCase for variables/functions, PascalCase for types/components
- Imports: group by external, internal, types
- No default exports except React components
- Use PRNG from `additions/browser/extensions/cloakfox-shield/src/lib/crypto.ts` for all randomization, never Math.random()

## Testing

- Fingerprint/runtime probes: **selenium + geckodriver** against a built
  binary, `tests/fingerprint/probe_*.py` (NOT Playwright — no Juggler on this
  branch). Set `CLOAKFOX_BIN=<app>/Contents/MacOS/cloakfox`. See
  `tests/fingerprint/README.md`.
- Dev build is NON-packaged: actor `*.sys.mjs` are loose files under
  `obj-*/dist/bin/browser/actors/` and `…/Cloakfox.app/Contents/Resources/browser/actors/`
  — copy edited sources there to test JS-only changes with no rebuild.
- Unit tests: `tests/fingerprint/test_*.mjs` (node --test) and `test_*.py`.
  Run in CI by the `unit-tests` job. NOTE: no Vitest suite exists despite
  earlier docs claiming one — do not assume `.test.ts` files are present.
- Test spoofed values are deterministic given same seed
- Test different containers produce different fingerprints
- Test different domains produce different fingerprints within same container
