# Site-bound fingerprint noise — task 5

## Approved design and ownership

Root approved the following design before production task5 edits on 2026-09-07:

- Use Gecko `Document::CookieJarSettings()` / chrome `document.cookieJarSettings.partitionKey` and `WorkerPrivate::CookieJarSettings()` (documented any-thread accessor). These carry the top-level site into third-party frames and workers; do not use the tracker frame/worker's own origin.
- Gecko `OriginAttributes::SetPartitionKey` and `PopulateTopLevelInfoFromURI` handle the public suffix list, IPs, blob creator principals and opaque null-principal UUIDs. `privacy.dynamic_firstparty.use_site` defaults true in Firefox155. Normalize only the foreign-ancestor `,f` bit so frames agree with their top-level publisher. Missing/malformed/non-schemeful keys do not fall back to a global or tracker-origin identity.
- Derive HMAC-SHA256 using the ASCII base64 encoding of the full 32-byte container secret. Versioned message bytes are UTF-8 `cloakfox-site-v1\n<vector>\n<unsigned base seed>\n<canonical partition key>`. Read first four digest bytes in big-endian order; map a derived zero to 1, while an explicitly configured base zero still disables noise. Native code uses Gecko's `mozilla::HMAC`/NSS. The actor uses RFC2104 HMAC over the existing synchronous NSS-backed `nsICryptoHash` SHA256 API.
- Preserve broad persona, font allowlist, OS, hardware and other configuration. Only perturbation keys vary by site.

Owned native compile surface (all recorded in the new final patch):

- `dom/canvas/{CanvasRenderingContext2D,ClientWebGLContext,CanvasUtils}.cpp`
- `dom/media/webaudio/{AudioBuffer,AnalyserNode}.cpp`
- `dom/workers/WorkerPrivate.cpp`
- `dom/base/{Element,AbstractRange}.cpp`
- `dom/svg/{SVGGeometryElement,SVGGraphicsElement,SVGTextContentElement}.cpp`
- `gfx/thebes/{gfxFont.cpp,gfxFont.h,gfxTextRun.cpp,gfxTextRun.h,gfxHarfBuzzShaper.cpp}`

Owned additions: `cloakcfg/CloakfoxSiteSeedCore.hpp`, `cloakcfg/CloakfoxSiteSeed.hpp`, component `CloakfoxSiteSeed.sys.mjs`, Math/Keyboard/Timing/TabHistory child actors, small SeedSync secret migration/generation addition, extension experiment bridge secret generation. Controller authorized those coordinated SeedSync/bridge edits. The daily_defaults worker added the matching settings generator key and EXTRA_JS_MODULES registration.

## Implementation

Fresh cfgs include internal `fingerprint:secret`. Existing cfgs receive the missing key from their unchanged math master seed at startup. Regeneration and explicit Forget workflows generate a matching new secret; identity version migrations and all explicit overrides remain intact.

Canvas2D and WebGL pixel readback, audio data/analysis, worker/window Math, and DOM/SVG/text-metric noise now derive from their owning document/worker's top-level site. Window Math now reads the same cfg `math:trig_seed` as native worker Math, fixing the previous byte-offset disagreement. Actor PRNG inputs for Math constants, Keyboard, Timing and TabHistory are separately site-bound.

Font spacing is derived when the font group is created from its owning document/worker, then copied into text runs and shaped words. Both word-cache hash and equality include the derived site seed. No ambient/current-JS-window lookup is used to identify the font site. The historical `font:seed` cfg field has no native consumer in this checkout; the actual shaping vector is `fonts:spacing_seed`.

Canvas extraction checks still honor native permission/placeholder results first. A configured nonzero seed bypasses Firefox's native randomization only if site derivation succeeds. Missing secret/context retains native extraction policy. Explicit configured zero retains its established intentional-disable behavior. Other noise paths produce no spoofed noise when context/secret is unusable; they do not expose a shared container fallback.

## Verification

The first actor-helper attempt failed because the helper did not exist. With a stub API returning zero, the behavioral RED run of `node --test tests/fingerprint/test_site_seed.mjs` had 5 failures (known HMAC vectors and distinct-site behavior) and 2 passes. The production helper then passed all seven behavioral tests. Native protocol-core coverage was added after the shared actor protocol implementation: it compiles the real standard-C++ protocol header and checks canonicalization, message bytes, known digest-to-seed bytes, malformed input and explicit zero.

Final command:

```sh
node --test tests/fingerprint/test_site_seed.mjs tests/fingerprint/test_site_seed_native.mjs tests/fingerprint/test_persona_version.mjs tests/fingerprint/test_seedsync_fonts.mjs tests/fingerprint/test_h3_guard.mjs
```

Result: **29 passed, 0 failed**. Node stubs only the Gecko SHA256 service with Node crypto; production HMAC composition and context extraction run unchanged. Native protocol compilation uses `c++ -std=c++17`; Gecko/NSS wrapper compilation remains part of the controller's actual browser build.

`python3 -m py_compile tests/fingerprint/probe_site_isolation.py` passes. The new disposable-profile Selenium probe serves local HTTP `one.test`, `child.one.test`, `two.test`, and `tracker.test`; it checks reload/subdomain stability, separation for canvas/audio/font/Math, window/worker agreement and third-party frame/worker agreement under both publishers. It has not been run, as requested. HTTPS-Only is disabled only in this disposable local HTTP test profile.

Patch verification: `patch --dry-run -R -p1 -d firefox-src < patches/site-fingerprint-isolation.patch` succeeds for all 16 native files, with no fuzz/reject output. Native changes were diffed against exact pre-task worktree snapshots, preserving uncommitted port changes. Additions were copied to matching firefox-src locations. No old patch was rewritten, no stack reapplied, no commit or browser build/run performed. Controller must add `site-fingerprint-isolation.patch` last in `patches/order.txt`.

## Remaining integration checks and limits

Controller must compile the actual Gecko/NSS wrapper on supported platforms and run the live probe. No claim of demonstrated runtime isolation is made before that verification. Shared/service worker partition inheritance, opaque top-level navigation, host special schemes, optional math-constant mode, and rendering/performance compatibility need runtime coverage beyond the included dedicated-worker/local-HTTP probe. Non-schemeful partition keys (e.g. an explicitly disabled `privacy.dynamic_firstparty.use_site`) intentionally produce no Cloakfox site noise; native canvas fallback remains active. The broad persona remains container-scoped and can still contribute correlation: this change protects these noise outputs, not every possible fingerprinting signal or full unlinkability.

### Final default-container review correction

Native noise no longer calls MaskConfig's ambiguous `ucid=0` accessor for secrets or base seeds. `ExactConfig(ucid)` reads `CloakConfigOverlay_Get(ucid)` directly, so default-container layout/worker output cannot accidentally borrow the current JS realm's non-default container. Derivation reads the base seed and full secret from that same exact cfg. Canvas policy uses the same exact configured seed for its explicit-zero check.

Final focused command `node --test tests/fingerprint/test_site_seed.mjs tests/fingerprint/test_site_seed_native.mjs` passes **10/10**, including a new compiled production `ExactConfig`/`BaseSeed` extraction with real `json.hpp`, default-container zero, independent other-container seed and secret checks. The broader 29-test run above preceded this correction; no broad rerun was performed because the controller owns integration testing.

Updated `test_canvas_extraction_policy.py` now compiles the final patch's actual policy helper instead of the superseded base helper. `python3 tests/fingerprint/test_canvas_extraction_policy.py` passes **2/2**, covering disabled, missing, explicit zero, valid site and unavailable-site settings while retaining native gates. Final patch reverse dry-run is clean on all 16 files after the correction.

Native build dependencies: these existing target directories already have `/cloakcfg` in LOCAL_INCLUDES; `ScopedNSSTypes.h` is exported by `security/manager/ssl/moz.build`, and WorkerPrivate/Document headers are existing Gecko exports. No additional native moz.build changes were needed. Source changes were frozen and root notified safe-to-build after this verification. NSS include/link portability remains subject to root's actual build.

### Stylo and identity-lifetime correction

The independent review (`site-review.md`) found that Stylo-created font groups
had no DOM-worker context and could cache seed zero. Font identity is now
prepared on main in nsPresContext and exposed through an atomic packed snapshot
on FontVisibilityProvider; style threads never derive it from Document/NSS.
The font-group accessor reads the latest snapshot for new runs. Config changes
are announced via a numeric SeedSync epoch (dynamic cfg strings do not propagate
through content preference IPC); pres contexts refresh and rebuild existing
font/layout caches when the identity changes. Exact missing-container lookup no
longer falls back to the process environment config.

The site patch now includes 20 native files, adding nsPresContext.cpp/.h,
layout/base/moz.build and FontVisibilityProvider.h. Reverse dry-run succeeds.
New compiled production accessor/lookup tests and SeedSync epoch regression pass;
full native rebuild and live style/toggle verification belong to the controller.
