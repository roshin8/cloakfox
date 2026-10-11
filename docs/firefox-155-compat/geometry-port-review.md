# Independent review of the Firefox 155 geometry ports

Reviewed the seven resolved scratch patches against their before/after Firefox 146 snapshots, Firefox 155 baselines, and relevant current call sites. This was a read-only source review; no patches or shared Firefox source were changed and no Firefox binary was run.

## Upgrade finding: restore noise on asynchronous WebGL snapshots

**P1 — New asynchronous snapshot path bypasses the existing WebGL readback protection.**

Location: `webgl-readback-noise.patch`, resulting `dom/canvas/ClientWebGLContext.cpp`: `SupportAsyncSnapshot` / `GetSurfaceSnapshotAsync` around lines 1231–1237, and `DoReadPixelsAsync` around line 5756. Current `dom/html/HTMLCanvasElement.cpp:247` calls the asynchronous snapshot API for capture streams; its dispatcher at line 1542 selects the WebGL async implementation.

The port only calls `CloakfoxNoiseReadPixels` from synchronous `DoReadPixels`. Firefox 155's successful async IPC callback copies/swizzles the pixels and resolves the surface without passing that hook or `GetImageBuffer`. Firefox 146's WebGL context has no async snapshot implementation; `GetSurfaceSnapshot` calls `BackBufferSnapshot`, which calls the patched `DoReadPixels`. Thus the old path applied noise whenever its seed resolved nonzero, while the new path never does. The original patch's description emphasized readPixels/toDataURL/toBlob, but its effective snapshot hook coverage was broader. This should be treated as lost coverage during the upgrade, not solely as an unrelated new feature.

Action: add exactly one deterministic noise application to successful async snapshot pixel extraction. Resolve/capture the intended container/domain seed before asynchronous dispatch, or explicitly derive it from the context's principal/origin attributes; an implicit MaskConfig lookup in the promise callback must not depend on the initiating JS realm still being current. Preserve context-loss/error returns, alpha handling, Y flip and stride. Validate capture-stream frame pixels for repeatability and separation between containers/domains, alongside unchanged readPixels and encoded-image probes. Root has assigned this fix to the geometry port agent; re-review is pending.

## Deferred inherited issue

**P2 — `CloakfoxNoiseReadPixels` modifies bytes outside the returned pixel rectangle.**

Location: `webgl-readback-noise.patch:53` and the call at line 74; resulting `DoReadPixels` computes `byteOffset`, `byteStride` and returned `subrect`, copies only the valid rows, then passes the entire destination span to the helper. `ReadPixels` supplies the remaining typed-array span, not just the written rows. A larger buffer filled with nonzero sentinel bytes, or WebGL2 PACK_SKIP_ROWS/PACK_SKIP_PIXELS/row-length padding, can therefore have otherwise untouched bytes altered. This is present in the Firefox 146 patch too and is **not an upgrade blocker**.

Follow-up: noise only the copied pixel rows while preserving deterministic pixel indexing; add a 1×1 read into a larger sentinel-filled array and WebGL2 pack-state cases. Do not silently change this behavior as part of the scoped async fix.

## Checks with no further port findings

- Range: both public result hooks moved exactly once from `nsRange.cpp` into `AbstractRange.cpp`. Bounding/client results preserve the seeded sequence. The newly added internal `CollectClientRects` path does not double-noise layout data; the public client-rect wrapper still reaches `GetClientRectsInner`. Existing unpositioned and shadow-boundary selection behavior is retained.
- Screen: setters, WebIDL gates, dimension-manager lookups, device-surface override and CSS device-size hook are retained. The new WebDriver BiDi override path remains after the Cloakfox dimension lookup. New NEON/SSE build entries were not removed.
- SVG: three geometry-bearing bbox returns and both CTM returns receive noise. Typed SVGBBoxFlags, CSS zoom correction, MakeAndAddRef constructors and the new empty-options result are consistent with Firefox 155. Singular-matrix and empty/non-display semantics outside the hooks are retained.
- Text metrics: all five original width/bounding-box adjustments remain immediately before TextMetrics construction; new per-baseline GetBaseline calls are preserved.
- WebGL spoofing: one FuncScope and one strong NotLostData guard precede shader precision overrides; native error/null returns remain. Vendor/renderer overrides remain within the existing debug-extension guard and before all new Firefox privacy fallback targets. Array-return branches retain their returns and typed-array construction. Container and worker lookup logic is unchanged.
- Letterboxing: the new TopInnerSizeSpoofedForRFP helper calls Top()->GetInnerSizeSpoofedForRFP, so removing the explicit Top() at the migrated sites is correct. UpdateInnerSizeSpoofedForRFP still runs on visible-area changes and the Cloakfox condition bypasses the global-RFP-only guard. Content/chrome and caller gates are retained. Comparing the old/new semantic patch additions found only the intended renamed getters in the orientation/media hooks; browser initialization retains the new Picture-in-Picture setup.
- The existing seed lookup calls in range/SVG/text metrics/synchronous WebGL were preserved; no fresh shared global seed or hardcoded container ID was introduced. Full container/domain behavior still depends on the integrated MaskConfig implementation and runtime probes.

No additional compile-signature or duplicated-hook defect was identified by this review. Exact patch application and source checks do not substitute for the full Gecko build and fingerprint probes.


## Scoped re-review of the async snapshot fix

**Verdict: the upgrade finding is addressed; approved for integration and full-build/runtime validation.**

Re-read the current `webgl-readback-noise.patch` and resolved `DoReadPixelsAsync` source. The fix resolves `noiseSeed` before `SendReadPixelsAsync`, using `GetUserContextId()` from the owning canvas context. The callback captures the uint32_t seed by value and does not consult MaskConfig later. It calls the shared explicit-seed helper exactly once, on the copied writable RGBA surface, after row copies and before Firefox's native `SwizzleYFlipData`. The shared-memory source is unchanged. Native validation, context-loss, IPC rejection, allocation/mapping failure, promise resolution, alpha handling, stride and Y-flip control flow remain intact. The existing synchronous hook retains its original seed lookup and behavior.

Independently ran `python3 tests/fingerprint/test_webgl_async_readback.py`: **2 tests passed**. This includes compilation/execution of the actual extracted helper and canvas noise implementation with `-Wall -Wextra -Werror`; assertions cover by-value seed stability after a configuration change, deterministic repetition, differing seeds, alpha/source preservation, zero-seed no-op, unsupported formats and transparent/short buffers. These are focused source/helper tests, not a browser captureStream probe.

Checked the **actual patched** `firefox-src/cloakcfg/MaskConfig.hpp`, not only the stale pre-patch additions copy. `GetUint32` forwards the supplied container ID through `GetUintImpl` and `GetContextOverlay` into `CloakConfigOverlay_Get`. The latter reads `cloak_cfg_<userContextId>` and honors the master enabled switch; `GetUserContextId` covers window and OffscreenCanvas worker origin attributes. Capturing the resulting scalar prevents a later overlay update from changing an in-flight snapshot.

**Domain-isolation limitation:** this current C++ overlay API is keyed only by container, and the seed bridge derives `canvas:seed` from the container master seed. Neither it nor `CloakConfigOverlay_Get` accepts or derives a domain key. Therefore the fix correctly preserves the configured container seed at request time, but it does not independently establish different canvas noise between domains within that container. This is an existing seed architecture limitation, not an async-fix regression; do not describe the two focused tests as proof of per-domain isolation. Browser tests remain necessary for the resulting captureStream output. The inherited destination-padding issue remains deferred.
