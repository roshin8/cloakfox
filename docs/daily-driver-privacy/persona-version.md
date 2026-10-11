# Persona build-version migration — task 1

Implemented 2026-09-07 in the Firefox 155 compatibility worktree.

## Behavior

- `CloakfoxPersonas.sys.mjs` reads `AppConstants.MOZ_APP_VERSION` and uses its major version plus `.0` for generated Firefox and rv tokens. Release patch numbers, nightly/beta suffixes and ESR suffixes stay out of the UA. This follows the major-only UA convention in `firefox-src/build/moz.configure/init.configure` (`uaversion="%s.0" % major_version`). AppConstants is generated from the build's application-version metadata.
- `CloakfoxSeedSync.sys.mjs` upgrades the existing persisted navigator UA, HTTP UA and appVersion in place at startup, including cfgs that already have font keys. No persona resampling or seed rotation occurs for complete cfgs. Existing unrelated values survive.
- The canonical `CloakfoxOverrides` contract applies each stored override last. Explicit old-version UA/header/appVersion overrides remain pinned. Custom identity strings outside the generated desktop Firefox shape remain unchanged.
- Source additions were copied byte-for-byte to matching `firefox-src/browser/components/cloakfox/` modules.

## Tests and evidence

New `tests/fingerprint/test_persona_version.mjs` evaluates the full production Personas, Overrides and SeedSync modules with only Gecko imports/exports adapted for Node. Stubs supply build metadata, BrowserForge input, Gecko preferences, contextual identities, observers, randomness and sharedData. Tests call production startup and assert persisted output; migration logic is not copied into tests.

RED command, before production edits:

```sh
node --test tests/fingerprint/test_persona_version.mjs
```

Result: 7 tests, 1 passed, 6 failed. Four fresh-config cases retained `146.0` instead of build majors 155/156/157; persisted cfg remained at `146.0`; an explicit appVersion override was not reapplied on existing cfg startup. Custom cfg preservation passed.

GREEN command, after implementation and added boundary coverage:

```sh
node --test tests/fingerprint/test_persona_version.mjs tests/fingerprint/test_seedsync_fonts.mjs tests/fingerprint/test_h3_guard.mjs
```

Result: 20 passed, 0 failed. Ten new tests cover four build channels, startup identity migration and idempotence, unchanged seeds/unrelated values, per-field overrides, explicitly pinned Firefox-shaped identities, custom direct cfg preservation, font-key upgrade, and corrupt cfg recovery. Ten existing font/H3 tests also pass.

## Scope and limits

No build, browser run, commit or live profile manipulation was performed. Controller owns integration/runtime verification. Legacy cfgs contain no generated/manual provenance marker: canonical desktop Firefox-shaped strings set directly in cfg without override prefs are treated as generated. The documented per-field override prefs preserve intentional pins, including old Firefox versions. User-pinned fields may intentionally contradict generated fields; migration does not override that choice.

Follow-up coverage: independent, divergent navigator UA (`144.0`) and HTTP UA (`145.0`) overrides remain unchanged while generated appVersion migrates to `155.0`. The final combined command passes 21 tests. Future cfg schema should record generator/schema version plus generated identity baseline separately from overrides; this would allow precise provenance-based migrations instead of recognizing legacy string shape.
