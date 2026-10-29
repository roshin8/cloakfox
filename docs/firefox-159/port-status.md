# Firefox 159 source port — 2026-10-27

## Current state

All 17 initially conflicting patch files are resolved. A clean replay of the complete 158-patch stack against the verified official Firefox 159.0 source succeeds with zero patch failures. This is source-port acceptance, not a native-browser build or runtime acceptance. No installed app, profile, DMG, updater trust or permission setting was changed.

Branch `codex/firefox-159-port` is isolated from the existing main/checkpoint worktree. Base 99cead4f453c4d1b96a6684c95afbda46d7e4448 and initial port checkpoint 0b7287e90e remain reachable. Chromium's native sources, locks, compiler/checkpoint machinery and ongoing remote run 40544857164 were not changed, cancelled or restarted.

## Conflict resolutions

- Font/canvas: retain 159's CheckedInt include and new font-palette lookup; preserve canonical rendering/provenance hooks.
- Screen/focus: adapt 159 FIELD attributes with top-only/custom validation; preserve same-top focus checks, orientation lock release and RefPtr ownership. Keep the existing upstream PushManager interface.
- Session storage: use 159's private window-ID WeakMap, not spoofable public __SSi properties; add restore-file pruning inside the new SessionWriter class using its private paths and the existing mutex/finally unlock. Keep default-container and failure propagation protections.
- Network: adapt neqo stream-limit enum/map APIs and grouped NSS experimental APIs; retain connection policy/worker propagation, allowlists, TLS validation and per-container settings. Preserve all vendor manifest entries/package provenance and update only modified payload hashes.
- Build/Cocoa: adapt root build-file context and native-control initialization without changing real button actions/accessibility.
- Whole-patch syntax: fix no-terminal-newline checksum metadata and add a regression that rejects a file header swallowed by an unfinished hunk.

The current inventory derives its version from upstream.sh and writes gecko159-inventory.json. The historical158 manifest is retained. This is parity-tracking metadata, not a claim that native Chromium privacy coverage advanced. Runtime probe guards require159; the explicit stock158 feature-comparison mode is retained.

## Verification

- Initial replay:141/158 applied,17 conflicts (patch-replay.json is preserved as failure evidence).
- Clean final replay:158/158 applied, zero failures (patch-replay-final.json).
- Fingerprint Node suite:363 passed, no skips.
- Fingerprint Python/native-snippet suite:81 passed. The two required fdlibm objects were compiled from159 bundled source with contraction/fast-math disabled, not copied from158 or replaced with host math.
- Release Python suite:31 passed, including three whole-patch syntax regressions. Release Node test:1 passed.
- Native network snapshot test:1 passed.
- CI helper suite:151 passed using Homebrew Python3.12. The initial asdf interpreter lacked lzma; its failed archive test was an environment failure and was rerun without changing the test.
- Engine source/helper suite:94 discovered,35 skipped without native binaries; remaining checks passed. Skipped runtime tests are not acceptance.
- Vendor audit:224 payload SHA256 values across neqo-http3, neqo-transport and nss-rs match manifests; complete entry sets and original package hashes preserved.
- Rust syntax:157 source files parsed with rustfmt without rewriting files; this is not type/link checking.
- Independent source review: no actionable correctness/privacy regression found; no reviewer native-build/runtime claim.
- Fresh official-feed security check: ready=true for159.0, no bypass or offline authorization.

## Native build/runtime limitation

Full Firefox159 compilation and browser runtime tests have NOT run. Native configure encountered local toolchain incompatibilities: cached Mozilla Clang 19's linker cannot parse the installed SDK 27 TAPI architecture; cached SDK 14.4 is correctly rejected (159 requires at least 26.5); native Apple Clang 21's ld64 is not recognized by the upstream configure probe. No minimum-SDK, compiler, sandbox, TLS or privacy guard was relaxed. Configure scratch state stays under this159 source tree, not the shared toolchain directories.

About12 GiB is free internally; the external build volume is absent. Do not delete Chromium checkpoints/source trees or user data for a build. Next acceptance requires a compatible independently provisioned Mozilla compiler/linker +SDK 26.5 or newer, sufficient build storage, then full compile and owned headless/runtime regressions. Live window input and installed-app replacement are not authorized by this source-port verification.

## Source provenance

Official archive: https://archive.mozilla.org/pub/firefox/releases/159.0/source/firefox-159.0.source.tar.xz
Verified against Mozilla 159.0/SHA512SUMS before extraction:
669241f3fc672d8240ddc4158b6125e5c2566bd0013a0a96a3874ee17bf0d9b3d91c842e653cb35eab0921829ce3660e9d795900b3c3a5488cd6020f85a0aac3

The freshness check alone is not full release authorization. No release package was created or published.
