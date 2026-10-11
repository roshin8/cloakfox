# Independent site-fingerprint review — 2026-09-07

Read-only review of the maintained patch, additions and actual Firefox source.
Native sources remained frozen for the controller's build. No tests, native
compilation or browser run was performed during this review.

## Actionable findings

### P1 — Stylo-created font groups permanently capture an unprotected zero seed

Location: `firefox-src/gfx/thebes/gfxTextRun.cpp:1900`, owned by
`patches/site-fingerprint-isolation.patch` (gfxFontGroup constructor).

The constructor resolves a document only on the main thread. On other threads
it recognizes only DOM `WorkerPrivate`. Firefox also creates font metrics during
Stylo traversal: `layout/style/GeckoBindings.cpp:1303` runs `Gecko_GetFontMetrics`
under the Servo FFI lock and calls `nsLayoutUtils::GetMetricsFor`;
`gfx/src/nsFontCache.cpp:58` explicitly supports both main-thread layout and
Stylo, constructing/caching `nsFontMetrics` and its `gfxFontGroup` on misses.
A Stylo thread has no DOM WorkerPrivate, so `ForContext(..., nullptr)` returns
zero and that group permanently carries no font-spacing site seed. Later cache
hits reuse it without refreshing identity. This creates path-dependent missing
font protection even though the new word-cache key itself includes site seed.

Fix by passing immutable, main-thread-precomputed container/site identity into
font metrics/group creation through a thread-safe document/pres-context path.
Do not simply touch Document/CookieJarSettings or synchronously dispatch NSS
initialization from Stylo while the main thread may be waiting for traversal.
Add a regression that forces first font-metric creation through parallel style
resolution and compares same/different publisher contexts plus canvas/DOM font
paths. A canvas-only main-thread `measureText` comparison cannot cover this.

### P2 — Cached font identity survives master-disable and seed rotation

Locations: `firefox-src/gfx/thebes/gfxTextRun.cpp:1902` and
`firefox-src/gfx/thebes/gfxHarfBuzzShaper.cpp:1494`.

The new seed is derived once per font group and copied into text runs/words.
HarfBuzz now reads that captured value instead of the prior current cfg lookup.
If a page creates its font group while enabled and then the user disables
`cloakfox.enabled` or changes its spacing seed/secret, newly shaped words using
that same group still apply the captured old noise. The reverse transition
retains zero for groups created while disabled. Cached word hash/equality correctly
partition *the supplied seed*, but cannot correct a stale group seed.

Invalidate/rebuild dependent font metrics/text/word caches on protection or
identity generation changes, or carry a safe identity epoch and refresh at an
appropriate thread boundary. Merely adding an enable check in the shaper does
not fix already-cached words or seed rotation. Test new, previously-unshaped
strings and repeated cached strings in one document across disable/enable and
regeneration, in addition to fresh-profile tests.

### P2 — Exact-container lookup still falls back to process-global environment config

Location: `additions/cloakcfg/CloakfoxSiteSeed.hpp:29–31`.

`ExactConfig` returns `MaskConfig::GetJson()` when the exact overlay is absent or
malformed. The actual patched MaskConfig implements this as the shared
`CLOAK_CONFIG[_n]` environment object. Thus an environment config containing
`fingerprint:secret` and vector seeds can supply the same identity to unrelated
missing-container overlays. It also applies when `CloakConfigOverlay_Get` returns
empty because the master switch is disabled. Actor `siteSeedForWindow` does not
have this fallback, so native and actor outputs disagree for this configuration.
This contradicts the documented no-global-fallback/exact-container protocol.

Return an empty config for missing/invalid exact overlays, or explicitly scope
and gate a separately supported automation environment path. Add a test with a
nonempty environment config and missing/malformed overlays; the current native
helper test makes `MaskConfig::GetJson()` empty and therefore cannot catch this.

## Evidence supporting the design

- `CookieJarSettings.partitionKey` is an appropriate existing Gecko source for
  top-level site context. Actual Document code inherits its parent's settings,
  and WorkerPrivate documents its accessor as usable on any thread. Native
  OriginAttributes performs PSL, blob creator and null-principal handling.
- The C++/JS message framing, ASCII-base64 secret bytes, HMAC-SHA256 composition,
  unsigned seed formatting and big-endian digest truncation agree by inspection.
  Foreign-ancestor-bit normalization intentionally puts embedded trackers in the
  publisher's site identity. Valid-secret validation could be more canonical,
  but generated 32-byte base64 seeds fit both implementations.
- Pixel extraction retains native permission/placeholder checks before the
  Cloakfox noise decision. Unusable context/key generally produces zero and
  retains native canvas policy; the environment fallback above is the exception.
- Font word-cache hash **and equality** include the site seed, and shaped words
  receive it before shaping. This closes the direct same-font-cache crossover
  for groups carrying a correct current seed; the group-creation/lifetime gaps
  above remain.
- Full-secret HMAC limits simple cross-site base-seed inversion; 32-bit derived
  noise still has collisions and is not a claim that all fingerprint surfaces
  or the broad persona are unlinkable.

## Performance and runtime gates

Every DOM rectangle/text-metric derivation currently reads and parses the full
cfg JSON and performs NSS HMAC initialization/key import. `getClientRects` and
layout-measurement loops are hot paths; unlike a pure integer mixer this adds
allocations and crypto work per call. No measured slowdown is claimed here, but
profile representative scrolling/editors/charts and repeated rectangle/audio
queries before release. If caching is needed, key it by exact context/vector and
identity generation and invalidate correctly; caching only a container ID would
undo the privacy boundary.

The synchronous HMAC wrapper can initialize NSS via synchronous main-thread
dispatch on non-main threads when necessary. Dedicated worker usage follows an
existing supported NSS pattern; extending it to Stylo to fix the font issue
requires care because traversal can hold locks or block the main thread.

The controller's live probe still must demonstrate first/third-party windows,
dedicated/shared/service workers, opaque/top-level navigations, all supported
platforms and style-thread behavior. A successful native compile and pure HMAC
protocol tests do not resolve these contextual findings.

## Follow-up implementation (controller authorized)

All three findings now have source fixes; native build/live confirmation remains
pending. `nsPresContext` prepares a packed atomic container/site-seed snapshot on
the main thread at Init/Attach. `FontVisibilityProvider` exposes that snapshot,
so Stylo font creation and fresh text runs read it without Document/NSS access.
Font groups no longer permanently capture a seed; their accessor reads the
owner's current snapshot, including intentional zero. OffscreenCanvas providers
retain owner-thread derivation.

`CloakfoxSeedSync` emits a numeric `cloakfox.font_identity_epoch` when cfg strings
change, because actual Firefox preference IPC sanitizes dynamic strings.
Pres contexts observe that epoch and the master switch, refresh on main, flush
font metrics and reconstruct frames if the derived identity changed. This
intentionally incurs a full layout rebuild on rare appearance/protection changes
to discard existing text runs, rather than only changing future cache keys.
The epoch guard prevents recursive observer publication and wraps within int32.
`ExactConfig` now returns an empty object for invalid/missing overlays, with no
environment-config fallback.

New/extended regressions failed before changes and now pass:
`node --test tests/fingerprint/test_font_site_snapshot.mjs tests/fingerprint/test_site_seed_native.mjs tests/fingerprint/test_seedsync_fonts.mjs`
reports 12 passing tests. These compile the production group accessor and exact
lookup helper, exercise prepared-zero/changing-owner snapshots and test the real
SeedSync observer's numeric notification/recursion behavior. The accessor test
extracts code from the maintained patch and requires no Firefox checkout.
The consolidated site patch now covers 20 native files and its reverse dry-run
matches all current sources without fuzz/rejects. No full browser build or live
style-thread/toggle run was performed by this worker after these fixes.
