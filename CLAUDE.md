# Cloakfox

Daily-driver privacy browser: Camoufox (C++ fingerprint spoofing) + ContainerShield (per-container, per-domain identity isolation).

## What This Is

A hard fork of Camoufox (Firefox fork with 33+ C++ engine patches) transformed into a daily-use browser with:
- C++ level fingerprint spoofing (canvas, audio, fonts, WebGL, navigator, screen, WebRTC, etc.)
- Firefox Multi-Account Containers with per-container unique fingerprints
- Per-domain deterministic fingerprinting within each container
- Bundled "Cloakfox Shield" extension for container management, settings UI, monitoring

## Architecture

Three layers:
1. **C++ Engine** — 26 Camoufox patches applied to Firefox ESR. Spoofs APIs at native level via self-destructing `window.setXxx()` methods.
2. **Cloakfox Shield Extension** — Stripped ContainerShield. Background manages containers/profiles/seeds. Inject script calls `window.setXxx()` with domain-specific seeds. JS spoofers handle vectors C++ doesn't cover.
3. **Config** — `policies.json` + `cloakfox.cfg` restore daily-driver features (search, bookmarks, passwords) while keeping privacy hardened.

## Build

```bash
make fetch      # Download Firefox ESR source
make patch      # Apply C++ patches
make config     # Copy policies/prefs into source
make extension  # Build Cloakfox Shield extension
make build      # Compile Firefox (45-90 min on Apple Silicon)
make package    # Create macOS DMG
make all        # Full pipeline
```

## Repo Structure

- `patches/fingerprint/` — 19 C++ spoofing patches from Camoufox
- `patches/infra/` — 7 infrastructure patches from Camoufox
- `patches/cloakfox/` — New patches for daily-driver restoration
- `config/` — policies.json, cloakfox.cfg, local-settings.js
- `extension/` — Cloakfox Shield extension (TypeScript, React, Tailwind)
- `scripts/` — Build automation scripts
- `branding/` — App icons and about dialog assets
- `tests/` — Unit (Vitest) and E2E (Playwright)

## Extension Architecture

- `extension/src/background/` — Container manager, settings store, profile manager, config injector, header spoofer
- `extension/src/inject/` — Cloakfox bridge (calls window.setXxx()), fingerprint monitor
- `extension/src/content/` — MAIN ↔ ISOLATED world message bridge
- `extension/src/popup/` — React popup UI (6 tabs)
- `extension/src/lib/` — PRNG (xorshift128+), seed derivation, domain matcher, profiles

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
- Use PRNG from `extension/src/lib/crypto.ts` for all randomization, never Math.random()

## Testing

- Unit tests: Vitest, `extension/tests/unit/`
- E2E tests: Playwright, `tests/e2e/`
- Test spoofed values are deterministic given same seed
- Test different containers produce different fingerprints
- Test different domains produce different fingerprints within same container
