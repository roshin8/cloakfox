# Complete canvas rendering privacy pipeline — architectural design

Status: Mac implementation and installed acceptance completed 2026-10-15.
The user explicitly limited verification to Mac for this run. Canonical fonts,
common image/media producers, software GPU routing, transfer provenance and
qualified extraction cutover are implemented. Unknown producer guards and strict
GPU/refusal controls remain. The original cross-host gate below is deferred by
this scope decision; no identical-rendering guarantee across operating systems
or CPU/GPU architectures has been established. Evidence and limitations are in
`docs/canvas-pipeline-completion/README.md`.

## Intent and acceptance boundary

Implement an optional complete canvas rendering privacy mode, preserving existing
protection when off and preventing a downgrade when on. Give every observable
consumer the same protected backing pixels. Avoid detector-specific behavior.
Keep ordinary opaque author-supplied colors exact. Preserve browser-native alpha,
compositing, tainting, security and error semantics; do not promise exact arbitrary
RGBA round trips through premultiplied surfaces. A shared software rasterizer
alone is insufficient evidence that host-dependent font or GPU output is removed.

Completeness is a release gate, not a checkbox label. Do not ship a glyph-only,
software-only or partially audited mode as a complete replacement. A universal
claim that no site can recognize privacy protection is outside the guarantee.
An operational claim of no privacy regression requires the differential and
adversarial acceptance tests below, with explicit limits on their coverage.

## Confirmed baseline problem

The installed build 20261015111523, XUL SHA256
356322cd14637d05ae3a6bc3b4c4e32a208ff4522d9f6fe46637ea28ac100484,
uses coordinate-dependent RGB changes in CanvasFingerprintManager.cpp.
A known opaque midrange image exposes those changes. A local probe corrected the
readback of another path/gradient image to the native control exactly: zero
mismatches across 16,384 channels, in HTML, Offscreen and worker canvases, both
with and without the glyph toggle. This demonstrates one recovery attack; it
does not establish recovery of every image or exact text on every backend.

Evidence: `docs/canvas-pipeline-audit/installed-baseline.json` and
`tests/fingerprint/probe_canvas_pipeline_baseline.py`. The prior 589-check suite
established semantic consistency and isolation, not resistance to recovery.

## Approaches and selected architecture

1. A software-only switch reduces accelerated backend variation but still uses
   platform fonts, upstream images, decoding and color conversion. It cannot
   safely replace extraction protection and is rejected as the complete solution.
2. More readback noise can mitigate individual recovery attacks but retains
   authored-pixel contradictions and does not give every transfer/display consumer
   one authoritative image. It is a separate hardening project, not this solution.
3. A canonical renderer plus surface provenance is selected. Standardize the
   producer and carry its policy through the full pixel-transfer graph. Keep the
   existing fallback until replacement coverage and attack resistance are proven.

### Canonical 2D producer

Add a context-owned immutable policy object with renderer version, owning
container/site seed and canonical font/raster configuration. Select it at context
creation, including unused OffscreenCanvas contexts and worker handoff. Preserve
it through resize/reset/provider replacement and restoration. Changes take effect
on new contexts after reload; no seed rotation or identity regeneration.

Use an explicit software backend and basic backing provider. Merely returning
true from UseSoftwareRendering does not choose a fixed backend: gfxPlatform
selects preferred/fallback implementations. Audit EnsureTarget, BorrowTarget,
CopyBufferProvider, TryAcceleratedTarget, TrySharedTarget and TryBasicTarget.
Prohibit silent native fallback when canonical creation fails. Return the usual
context/allocation failure, respecting API error semantics.

All paths, strokes, clips, gradients, patterns, filters, shadows, compositing,
transforms and interpolation use the same canonical target and compatible
intermediate targets. Fixed rounding, color conversion, image sampling and CPU
feature policy are part of the renderer version. Exact opaque authored pixels
must not receive arbitrary coordinate RGB changes.

### Canonical text and fonts

Use the same shaping and glyph raster backend across supported operating systems;
Skia with platform ScaledFontMac/CoreText, DWrite or Fontconfig does not satisfy
this requirement. Bundle a fixed, licensed fallback and color-font set. Fix
fallback ordering, variation axes, hinting, antialiasing and color-glyph policy.
Use the canonical path for author-provided FontFace bytes too; otherwise custom
fonts still exercise host-dependent shaping/rasterization. Preserve font loading,
permissions and failure semantics; never expose host font names as fallback.

Canvas measureText must come from the same canonical shaping run as rendered
text, with consistent bounding boxes, advances, alignments and baselines. Existing
independent final-result metric scaling must not contradict the new backing image.
A font/resource packaging review precedes dependency installation or downloads.

### Image provenance and upstream producers

Attach immutable renderer/policy provenance to source surfaces, ImageBitmap
payloads and cross-process/worker transfer records. Reuse security tainting where
appropriate, but keep privacy provenance separate from origin-clean: a same-origin
image can already contain host-dependent pixels.

Known author-supplied pixels can enter the canonical target without arbitrary
noise. Inputs rendered from SVG text, DOM/canvas snapshots, native video color
conversion or GPU output require canonical production, a proven normalization
path, or an explicitly protected fallback. Destination Skia rendering cannot
undo entropy embedded in source pixels. An unknown producer must never silently
qualify its pixels as canonical.

WebGL/WebGPU shader output needs its own canonical software backend if transparent
full GPU compatibility is required. Generic reported capabilities do not provide
canonical shader arithmetic or texture sampling. Until such a backend exists,
retain existing GPU readback protection and do not claim the complete-mode release
gate has passed for GPU-derived images. Blocking unsupported inputs would be a
separate compatibility contract requiring an explicit user-visible choice.

### Single authoritative backing and every consumer

Canonical snapshots and reads expose the same backing representation. Cover:

- getImageData, PNG/JPEG/WebP encoding, toDataURL, toBlob and convertToBlob;
- drawImage, canvas patterns, filter/shadow intermediates and canvas copies;
- createImageBitmap cropping, resizing, alpha/color options and structured clone;
- OffscreenCanvas transferControlToOffscreen, transferToImageBitmap and workers;
- bitmaprenderer transferFromImageBitmap and presentation snapshots;
- WebGL texture upload, framebuffer copy/blit/readback and WebGPU external uploads;
- captureStream, video/VideoFrame ingestion and frames copied back into canvas;
- asynchronous snapshots with retained owning policy, navigation and destruction.

Do not expose a raw source surface on a fast path when ordinary extraction would
be protected. Preserve origin taint, CORS, permissions and privileged/system
behavior. Identity ownership follows actual context/transfer metadata, never the
currently active tab or ambient container zero.

## Toggle and migration

Keep the existing additive glyph toggle and current installed behavior available.
Do not repurpose it silently into a substantially slower renderer. Introduce a
separate complete-pipeline setting only when the full release gate passes, default
off. Apply it authoritatively after generic overrides. Document performance,
font appearance and unsupported-backend consequences beside the toggle.

During development, use an internal experiment flag with extraction guards still
on. No public complete-protection label and no removal of those guards until
all native/rendering/transfer dependencies are implemented and verified.

## Test and release gates

1. Establish failing installed-baseline tests for known-fill calibration and
   native-raster recovery. Treat existing successful recovery as a confirmed gap.
2. Compare opaque colors and browser-native alpha semantics against native
   controls; exercise crop/export consistency without detector-specific inputs.
3. Run text, SVG, fonts, emoji, paths, gradients, filter, shadow, clipping and
   compositing corpora through every ingress/egress path above.
4. Attempt known-fill inversion, translation enumeration, repeated reads and
   redraws, channel amplification and thresholding via GPU uploads, bitmap/video
   round trips and read-frequency/acceleration changes.
5. Differential-test the same canonical renderer version across macOS, Linux and
   Windows and multiple GPUs/CPU architectures. Require identical canonical
   corpus pixels and consistent shaping metrics. A single Mac cannot establish
   cross-host normalization.
6. Verify same-site/container reload stability, different-site/container policy
   separation, worker ownership, unknown provenance, malformed policy, resource
   failures, disabled master switch and unsupported-feature fallback.
7. Keep strict float/integer/PBO GPU readback restrictions, location/media consent,
   network isolation and tainting tests green; do not let compatibility settings
   silently override privacy policy.
8. Test browsing compatibility, accessibility, large image memory use, editing,
   animation throughput and media/capture behavior with recorded before/after
   measurements; no universal performance guarantee.
9. Independently review source and the transfer graph. Replay ordered patches,
   build/package/sign, install with backup and repeat acceptance on the installed
   binary. Run pinned unmodified CreepJS/FingerprintJS, retain every warning.

The extraction-replacement cutover is blocked until canonical fonts and upstream
producer/provenance coverage exist and cross-host tests are available. Cosmetic
warning suppression is never an acceptance criterion on its own.

## Delivery boundaries

This is several dependent implementation projects: renderer/backing foundation;
font shaping/raster assets; canonical image/SVG/media producers; cross-API surface
provenance; canonical GPU backend; then cutover and installed acceptance. They
must be tracked independently and integrated under the same policy version.
No current code audit or one-machine test can honestly certify completion of
these projects or guarantee elimination of all hardware fingerprint information.
