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

### Media and network consent

`cloakfox.opt.mediadevices_disabled` enforces an empty enumeration and denies
new page camera/microphone/display/output-selection requests. Existing streams
are not revoked. Device-change notifications are suppressed while disabled.
Persona location values preserve native location permission checks.

External WebRTC IP discovery is independently opt-in via
`cloakfox.webrtc.external_ip_discovery` (default false).
`cloakfox.webrtc.protect_unready` defaults true: native ICE is relay-only while
discovery is off or either family mask is missing. TURN-less services can fail.
Installed masks are snapshots, not a VPN kill switch; existing connections
retain their ICE policy until reconfigured/recreated.

WebSocket blocking resolves a worker's `WorkerPrivate::GetOriginAttributes()`
container explicitly, including nested/shared/service workers. Exceptions use
neutral browser-policy wording. Blocking prevents new handshakes; existing
sockets are not automatically closed. The master switch restores native access.

Allowed WebSocket handshakes read their UA from the HTTP channel's origin
attributes and container configuration, rather than a process-wide cached UA.
The real Origin, native cookies, TLS checks and proxy handling are preserved.
WebSocket blocking remains off by default and is independent of these protections.

### Identity gap protections

Ordinary HTTP request headers and CONNECT requests resolve the channel or
transaction origin attributes. Persona values never populate the native
process-wide UA/language/encoding caches; disabling Cloakfox restores native
values without a stale persona. WebSocket handshake identity remains supported.

WebRTC mask setters are ChromeOnly, system-principal gated and called through
actor Xrays. Overlay mutations write the authoritative cloakfox.s namespace.
Pending content writes remain readable until the parent preference mirror
acknowledges them, so back-to-back IPv4/IPv6 writes cannot overwrite each other.

Privacy actors also match inherited HTTP/HTTPS/file content principals for
about:blank/srcdoc. System, opaque and internal documents stay excluded from
actors. Native WebGPU policy uses each window/worker's origin attributes and
also covers synchronous initial blank frames. Disabled policy returns undefined;
the explicit compatibility opt-out preserves the native GPU object and identity.
API replacements validate receivers
through captured native methods/getters before returning their configured values.

Canvas noise covers every nonzero RGB channel of opaque pixels and leaves
transparent/zero pixels unchanged. WebGL2 personas include uniform-buffer and
3D/array-texture limits. Strict precise/PBO pixel readback is on by default
(cloakfox.opt.webgl_typed_readback_disabled); its explicit compatibility opt-out
returns exact GPU data. Neither policy silently perturbs computation buffers.

FontFace lifecycle/loading remains native for URL and buffer webfonts. local()
sources are skipped while the owning persona font list is active; URL fallbacks
continue to work. Only the parent mutates the global font whitelist.

WebRTC proxy protection (cloakfox.webrtc.protect_proxy, default true) resolves
ICE server routes before gathering and forces native proxy transports for proxy
or resolution-error routes. Unavailable PAC errors do not silently become DIRECT.
Normal system/PAC DIRECT routes remain supported. Existing connections require
recreation or ICE restart after route changes. This does not implement an OS VPN
kill switch. Unsupported proxy/UDP-only combinations fail closed.

Page and worker language values use the same own-container identity as HTTP
headers. Canonical language lists omit HTTP quality syntax and duplicates;
frozen binding caches invalidate on relevant configuration/master changes,
including already-running workers and opaque content documents. System windows
and ChromeWorkers retain native locale values. Native locale/RFP behavior remains
the master-off fallback.
