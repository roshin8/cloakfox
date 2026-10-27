# Cloakfox

Daily-driver privacy browser: Camoufox (C++ fingerprint spoofing) + ContainerShield (per-container, per-domain identity isolation).

## What This Is

A hard fork of Camoufox, rebased onto Firefox 159.0 with C++ engine patches, transformed into a daily-use browser with:
- C++ level fingerprint spoofing (canvas, audio, fonts, WebGL, navigator, screen, WebRTC, etc.)
- Firefox Multi-Account Containers with per-container unique fingerprints
- Top-level schemeful-site deterministic noise within each container
- Bundled "Cloakfox Shield" extension for container management, settings UI, monitoring

## Architecture

Three layers:
1. **C++ Engine** — Camoufox + LibreWolf patches (ordered native patches) applied to Firefox 159.0. Spoofs APIs at native level via self-destructing `window.setXxx()` methods.
2. **Cloakfox Shield Extension** — Stripped ContainerShield. Popup UI plus a parent-process pref/persona bridge (`experiment-apis/cloakfox.js`). NO content or inject scripts — see "Spoofer Architecture (cpp-first)" below.
3. **Config** — `policies.json` + `cloakfox.cfg` restore daily-driver features (search, bookmarks, passwords) while keeping privacy hardened.

## Build

```bash
make fetch           # Download pinned Firefox source tarball
make setup-minimal   # Extract source + copy additions/ (policies, cloakcfg, extension)
make dir             # Apply all patches (ordered via patches/order.txt)
make extension       # Build Cloakfox Shield extension in-place
make build           # Compile Firefox (45-90 min on Apple Silicon)
make package-macos   # Create macOS DMG (also: package-linux, package-windows)
```

## Repo Structure

- `patches/` — Flat directory of all C++ engine patches (ordered by `patches/order.txt`)
- `patches/order.txt` — Explicit apply order; overrides alphabetical default
- `settings/` — policies.json, cloakfox.cfg, local-settings.js
- `additions/cloakcfg/` — MaskConfig.hpp, MouseTrajectories.hpp, json.hpp (copied into firefox-src)
- `additions/browser/extensions/cloakfox-shield/` — Cloakfox Shield extension (TypeScript, React, Tailwind)
- `scripts/` — Build automation scripts (patch.py, fetch-firefox.sh, copy-additions.sh, package.py)
- `branding/` — App icons and about dialog assets
- `tests/` — `tests/fingerprint/` is the live suite (selenium probes + node/pytest unit
  tests). Exclude generated `tests/fingerprint/reports` from pytest collection.
  `tests/async*/` and `tests/golden-firefox/` are inherited Playwright E2E
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
  TabHistory, Timezone, WebGPU, WebRTC. Timing actors cover callback scheduling;
  native Performance clocks/timeline entries use one immutable per-global
  presentation mode. Reload pages/restart workers to apply timing or master
  switch changes to those clocks. Each `*Child` patches page objects via
  `Cu.exportFunction` on `DOMDocElementInserted`, gated on `cloakfox.enabled`.
  Patch spoofs on the PROTOTYPE with native descriptor flags, never the
  instance — an own property leaks the tamper via `Object.keys()`.
- **cloakfox-shield extension** (`additions/browser/extensions/cloakfox-shield/`)
  — popup UI + `experiment-apis/cloakfox.js` (parent-process pref/persona
  bridge). No content/inject scripts.
- **Persona/seed** (`additions/browser/components/cloakfox/`) —
  `CloakfoxPersonas`, `CloakfoxBFNetwork` (BrowserForge Bayesian net),
  `CloakfoxSeedSync` (parent → `Services.cpmm.sharedData` for the actors).

### Website-facing device labels

Audio & media settings support per-device names and fallback labels for cameras,
microphones and speakers. Preferences use `cloakfox.<camera|microphone|speaker>.website_label_*`.
Native MediaManager applies labels only when generic media privacy is configured;
raw-ID maps never change public device IDs or permission filtering. Physical
inventory helpers are ChromeOnly and independently require system callers.
Display capture labels must remain native: screen/window/browser are video
inputs too, but must never inherit camera labels (sites validate monitor sharing).

Camera exposure uses `mediaDevices:cameraDevices` (a JSON-array string) in the
selected container's overrides. Missing means automatic system order; an explicit
array selects up to the maximum, and `[]` blocks all cameras. Legacy single
`mediaDevices:cameraDevice` values are retained until the user saves the new UI.
`CloakfoxCameraExposure.hpp` applies the camera maximum/selection to website
enumeration and pre-permission capture candidates. System-principal capture and
display capture are excluded. Existing streams are not forcibly stopped.

### Site media compatibility

`CloakfoxHackerRankMediaChild` is a separate compatibility actor, registered
only for the top-level `https://www.hackerrank.com/pair/*` application. It
refreshes HackerRank's cached local Zoom participant ID after failover and
advances the application's video render epoch. It does not change capture,
permissions, media transport, fingerprint signals, editor state or SDK internals.
The application has no public recovery API: discovery uses the existing store
capabilities and getAV getter signature, without hard-coded bundle IDs/export
names. Site changes can invalidate this adapter; unsupported shapes are left
alone. `cloakfox.compat.hackerrank_media=false` disables it on the next load.

`CloakfoxCoderPadMediaChild` is restricted to CoderPad's HTTPS `/*/zoom_room`
documents, including iframe use. For verified Zoom SDK 2.5.0 / media
7.1.0.15306, it selects the existing canvas sender when the combined worker
cannot consume VideoFrame messages without a track processor. A muted native
self-preview reuses the authorized stream in the current local participant's
player. It never starts capture, creates a client, changes permissions or
transport, or alters remote players/browser APIs. Discovery avoids fixed module
IDs and Symbol names; unknown versions are untouched. To opt out, set
`cloakfox.compat.coderpad_media=false` and reload.

## Critical Constraints

- `/Applications/Firefox.app` and Mozilla's `org.mozilla.firefox` bundle are reserved for genuine Mozilla Firefox. Never install, copy, rename, or synchronize Cloakfox over them. Install only a verified `org.mozilla.cloakfox` / `cloakfox` executable bundle as `Cloakfox.app`.
- Firefox appearance is a private, profile-owned cache copy named `Stealthfox.app`, with a distinct bundle ID. Never distribute or install an appearance copy into Applications. Preserve personal profiles independently of application replacement.

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
- After changing privileged resource modules in a loose development build,
  launch previews with `-purgecaches`, including when reusing a preview profile.
  An unchanged BuildID can retain old startup bytecode even though the UI loads
  newer source. Verify the reused profile as well as a clean test profile.
- Unit tests: `tests/fingerprint/test_*.mjs` (node --test) and `test_*.py`.
  Run in CI by the `unit-tests` job. NOTE: no Vitest suite exists despite
  earlier docs claiming one — do not assume `.test.ts` files are present.
- Test spoofed values are deterministic given same seed
- Test different containers produce different fingerprints
- Test different domains produce different fingerprints within same container


### Identity-gap port safeguards

Request UA/encoding and CONNECT identity use channel/transaction origin attributes;
native handler caches retain native values. Allowed WebSockets retain their real
Origin, cookie isolation and TLS/proxy behavior, with own-container headers.
Authoritative mask writes use cloakfox.s;158 synchronously re-reads parent config
on the main thread and keeps worker snapshots behind the existing cache mutex.

Native window/worker GPU getters enforce container policy even before deferred
blank-frame actors, preserving native brands and enabled-object identity. Canonical
language lists and frozen caches follow own-container updates, while system
windows/ChromeWorkers retain native values. Opaque content keeps masked languages.

Canvas noise covers nonzero RGB even when alpha is zero; alpha and all-zero clears
remain exact. Precise/PBO WebGL readback is restricted by default, with an explicit
compatibility opt-out. Existing158 site seeds, asynchronous snapshot ownership and
mutable WebGL state are preserved. FontFace URL/buffer loading remains native;
existing158 masked local-font policy remains in force, and global whitelist
retirement is parent-only.

WebRTC proxy protection and unready relay controls default on. Optional reported-IP
lookup remains separately opt-in (`cloakfox.webrtc.ip_lookup.enabled`). Required
proxy checks cover resolver, actual connection, failover and replacement routes.
TURN-less or unsupported proxy combinations can fail. Existing calls need ICE
restart/recreation after routing changes; this is not an OS VPN kill switch.
