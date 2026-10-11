# Firefox 155.0.1 geometry patch ports

Ported the seven assigned patches without modifying the shared `firefox-src` tree or committing changes.

## Changes

- **range-domrect-spoofing.patch:** moved the two seeded DOMRect noise hooks from `nsRange.cpp` to `dom/base/AbstractRange.cpp`. Firefox 155 moved bounding/client rect methods and their traversal helpers into `AbstractRange`; the port preserves that refactor, including the new internal `CollectClientRects` path. Only the existing exposed bounding/client rect result paths receive noise. Unpositioned/empty early returns and cross-shadow-boundary selection remain native.
- **screen-spoofing.patch:** retained the per-container dimension manager, setters, screen overrides, device-surface override and media-query integration. Updated include and declaration insertion points around Firefox's removed `GetRegionalPrefsLocales` API. Preserved new NEON/SSE rectangle sources in `gfx/src/moz.build` while adding the cloakcfg include directory. The audio declaration belongs to the separately ported audio patch and is not restored by this patch.
- **svg-bbox-spoofing.patch:** wrapped current `MakeAndAddRef<SVGRect>` results in the existing deterministic noise helper. Retained typed `SVGBBoxFlags`, `DisregardCSSZoom`, text-frame zoom adjustment, and the new empty-option fast return. Both CTM methods retain seeded noise and use `MakeAndAddRef<SVGMatrix>`. The actual 155.0.1 source still exposes `SVGMatrix` here; no `DOMMatrix` conversion is needed.
- **text-metrics-spoofing.patch:** retained width and four bounding-box noise additions immediately before `TextMetrics` construction, without restoring removed `GetBaselines`. Firefox 155's new individual `GetBaseline` calls remain intact.
- **webgl-spoofing.patch:** retained container vendor/renderer overrides ahead of native fallbacks and preserved all newly introduced WebGL vendor/renderer RFP targets. Shader precision overrides now follow Firefox 155's single `FuncScope` and strong `NotLostData` guard rather than restoring the removed duplicate scope/context check. Existing parameter, attribute, extension, and worker/container lookup hooks remain.
- **webgl-readback-noise.patch:** kept the encoded-image buffer hook and the successful synchronous IPC readback hook. Removed the obsolete in-process branch, which Firefox 155 no longer has. Also restored protection on Firefox 155's new asynchronous snapshot route used by capture streams: resolve the requesting canvas's seed with its explicit container ID before `SendReadPixelsAsync`, capture that scalar by value, and noise the copied RGBA destination once before the native swizzle/flip. The helper accepts an explicit seed so completion never queries an absent or changed initiating realm. Alpha, transparent zero pixels, native surface format selection, rejection paths, and shared IPC storage remain unchanged. `toBlob` still reaches `GetImageBuffer` through `CanvasRenderingContextHelper`.
- **cloakfox-letterboxing.patch:** uses `UpdateInnerSizeSpoofedForRFP` and `BrowsingContext::TopInnerSizeSpoofedForRFP` throughout. The changed `nsPresContext` guard continues updating the top-level visible size for Cloakfox letterboxing with global RFP disabled. Retained content/chrome and non-system caller gates. Preserved new Document Picture-in-Picture command initialization while removing inherited forced native-window sizing.

## Validation

Each patch was generated with `/tmp/cloakfox-port-patch.py generate NAME`. All seven passed application with `patch --fuzz=0` against their isolated before-155.0.1 snapshot, followed by byte-for-byte comparison against every intended output file.

For the range relocation, the helper's original sparse snapshot lacked `AbstractRange.cpp` because the old patch only named `nsRange.cpp`. Supplemented that patch's isolated baseline with the unchanged destination file from the read-only 155 source tree. The helper itself was not modified.

Additional source checks passed: no conflict markers; both range noise hooks and their include; three SVG bbox hooks and both matrix hooks; current text baseline API; exactly one shader precision scope; all new WebGL privacy fallback targets; exactly one synchronous readback noise call; and no obsolete `GetTopInnerSizeForRFP` references in the letterboxing work tree.

`node --check` passed for the resulting `browser-init.js` and `RFPHelper.sys.mjs`. `git diff --check` reports patch-format context-only blank lines (a single required space), so it is not a clean whitespace signal for these rewritten patch files.

## Integration and runtime limits

The full ordered patch application and C++ build remain required. Several insertion contexts depend on earlier patches that other agents are porting, especially `nsGlobalWindowInner`, canvas includes, and `moz.build` lists. Exact isolated application does not prove compile or runtime behavior.

After a 155 build, run `probe_letterboxing.py`, `probe_webgl_tables.py`, and `probe_webgl_readback.py`, plus range/SVG/measureText probes for repeatability, container/domain separation, disabled spoofing, and SVG zoom/empty-box behavior.

## Async snapshot review correction

Independent review identified that Firefox 146 capture streams reached the synchronous `DoReadPixels` hook, while Firefox 155 introduced `SupportAsyncSnapshot` → `GetSurfaceSnapshotAsync` → `BackBufferSnapshotAsync` → `DoReadPixelsAsync`. The initial port missed this changed route; the updated patch now covers it as described above.

`python3 tests/fingerprint/test_webgl_async_readback.py` passes two tests. The source integration test checks synchronous seed resolution using `GetUserContextId`, by-value capture, no late configuration lookup in the callback, and exactly one noise application between row copying and swizzle. The second compiles the actual readback helper and canvas-noise implementation extracted from the shipped patches with `-std=c++17 -Wall -Wextra -Werror`. It checks deterministic output under changed completion-time seed, different identity output, unchanged source IPC buffer, alpha preservation, zero-seed bypass, unsupported format/type bypass, short buffers, and transparent zero pixels.

Regenerated `webgl-readback-noise.patch` and repeated exact isolated application plus byte comparison successfully. The updated shared Firefox source must receive this patch delta before compiling. A real browser capture-stream probe is still required to verify the full asynchronous rendering route. The inherited whole-destination handling of direct `readPixels` padding is outside this compatibility fix and remains unchanged.

## Letterboxing runtime correction

The full Firefox 155 build completed, but `probe_letterboxing.py` reported one
failure in `runtime-letterboxing.log`: after resizing the top window, a cached
cross-origin iframe `matchMedia(device-width)` result and its CSS media-rule
result remained `[True, "1"]` instead of `[False, "0"]`. Initial geometry,
letterboxing buckets, and iframe screen-size agreement passed.

The port publishes the top-level viewport into the replicated
`InnerSizeSpoofedForRFP` browsing-context field. The Firefox 155 field had no
`DidSet` invalidation hook, so a fixed-size iframe did not receive a media-feature
change when only its top-level viewport changed. The iframe's own layout size
did not change. Device-width/device-height are also not marked
`VIEWPORT_DEPENDENT` in Servo, so a viewport-only change reason is insufficient
for these CSS dependencies.

Added `BrowsingContext::DidSet(FieldIndex<IDX_InnerSizeSpoofedForRFP>,
CSSIntSize)` to `cloakfox-letterboxing.patch`. When the replicated size actually
changes, it walks the local presentation contexts in the subtree and signals
`SystemMetricsChange` for documents using Cloakfox letterboxing. Each process
receives the replicated field update, covering remote iframes as well as local
ones. `JustThisDocument` avoids duplicate subtree propagation, and the existing
letterboxing predicate excludes chrome and disabled protection. The callback
does not force iframe layout dimensions to match the top-level dimensions.

The original snapshotted patch had no `BrowsingContext` hunks; this correction
adds that missing invalidation behavior to the Firefox 155 patch. The new
baseline entries were copied from the worktree's fully ported Firefox 155
`BrowsingContext.cpp` and `.h`, which no prior patch in the captured stack
modified. No concurrent changes from the original checkout were copied.

The patch was regenerated and passed exact application with fuzz zero and
byte-for-byte output verification. `BrowsingContext.cpp` passed `-fsyntax-only`
using its generated production compile command, with only `-c`/output arguments
replaced for syntax checking. The same two-file change is present in the
worktree's full Firefox source. No concurrent rebuild was started by this
correction; the integrating task must rebuild and rerun the existing runtime
probe before claiming the failure resolved.
