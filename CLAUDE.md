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
2. **Cloakfox Shield Extension** — Stripped ContainerShield. Background manages containers/profiles/seeds. Inject script calls `window.setXxx()` with domain-specific seeds. JS spoofers handle vectors C++ doesn't cover.
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
- `additions/juggler/` — Playwright automation bridge
- `scripts/` — Build automation scripts (patch.py, fetch-firefox.sh, copy-additions.sh, package.py)
- `branding/` — App icons and about dialog assets
- `tests/` — Unit (Vitest) and E2E (Playwright)

## Extension Architecture

- `additions/browser/extensions/cloakfox-shield/src/background/` — Container manager, settings store, profile manager, config injector, header spoofer
- `additions/browser/extensions/cloakfox-shield/src/inject/` — Cloakfox bridge (calls window.setXxx()), fingerprint monitor
- `additions/browser/extensions/cloakfox-shield/src/content/` — MAIN ↔ ISOLATED world message bridge
- `additions/browser/extensions/cloakfox-shield/src/popup/` — React popup UI (6 tabs)
- `additions/browser/extensions/cloakfox-shield/src/lib/` — PRNG (xorshift128+), seed derivation, domain matcher, profiles

## Critical Constraints

- C++ patches MUST be applied before `./mach build` — they modify Gecko source directly
- `privacy.resistFingerprinting` MUST be false — RFP conflicts with C++ patches (makes everyone identical; we want per-container uniqueness)
- `privacy.userContext.enabled` MUST be true — containers are the foundation
- Inject script MUST run at `document_start` in MAIN world before any page script
- `window.__CLOAKFOX__` config MUST be deleted after reading to prevent page access
- Same container + same domain MUST produce identical fingerprints across reloads
- Don't add console.log in inject scripts (detectable by fingerprinting sites)

## Code Style

- TypeScript strict mode, no `any` unless wrapping browser APIs that lack types
- camelCase for variables/functions, PascalCase for types/components
- Imports: group by external, internal, types
- No default exports except React components
- Use PRNG from `additions/browser/extensions/cloakfox-shield/src/lib/crypto.ts` for all randomization, never Math.random()

## Testing

- Unit tests: Vitest, `additions/browser/extensions/cloakfox-shield/tests/unit/`
- E2E tests: Playwright, `tests/e2e/`
- Test spoofed values are deterministic given same seed
- Test different containers produce different fingerprints
- Test different domains produce different fingerprints within same container
