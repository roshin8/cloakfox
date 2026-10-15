# Combined privacy source review — 2026-10-15

## Scope and answer

Three independent read-only reviewers examined the combined first-party production changes in commits8bb53bf88e, a35115c727 and b85e49a1a2, plus the current tracked/untracked rendering and GPU changes on codex/firefox-158-port. Base140d977998dd99ff82df6eb6e7aa3e1e7b4afc90; HEADb85e49a1a244dbddf8045e72a7c6f9ec8845f927. This extends the earlier feature-specific reviews; it does not justify saying every privacy leak has been ruled out.

**At the time of this review, three actionable findings remained unfixed:** one residual raw canvas-export hole, one WebGPU provenance/owner-isolation gap, and an IP-warning accuracy issue. These are source-review findings, not newly executed browser exploit demonstrations. No claim is made that actual personal information was recovered. TODO.md records each follow-up.

## Findings

1. **P1 residual gap: bitmaprenderer export lacks the Cloakfox extraction gate.** In native `dom/canvas/ImageBitmapRenderingContext.cpp:172–217`, GetImageBuffer attaches mCanvasPrivacyMetadata, converts through SurfaceToPackedBGRA and returns raw pixels. The only randomization is Firefox RFP, which this browser requires off. It does not apply the unknown/native/foreign-input treatment used by the2D serializer. A bitmap from an unverified/native producer can reach bitmaprenderer transfer and serialization; a context retained across enabling canonical rendering is one source scenario. `toDataURL`/`toBlob` and Offscreen `convertToBlob` need route-specific coverage. The raw export route predates today's commits; today's complete-pipeline work did not close it. No claim of newly introduced regression or successful installed exploit is made.
2. **P2: WebGPU canvas/device ownership is not compared at configure.** Native `dom/webgpu/CanvasContext.cpp` checks canonical-device status but not the device's exact container/site ownership against the transferred canvas's captured owner. An unused OffscreenCanvas transferred A→B can retain A's provenance and accept B's canonical device/profile. The pure-GPU output path can then certify it under A when no external imports are present. WebGL has the corresponding owner comparison. Reject mismatches or conservatively mark output unqualified. This is a provenance/profile-isolation gap, not demonstrated host GPU identity exposure.
3. **P2: IP-warning copy overstates destination knowledge.** `additions/browser/components/cloakfox/content/ip-warning.js:18` says containers use the same public IP “for this hostname.” The actual measurements use ipify/httpbin and a per-container cache; visited-host records associate those lookup values with visits. Destination-dependent proxies/PAC, provider pools or IPv4/IPv6 routes can differ. Qualify the copy as equal lookup measurements associated with recorded visits. No direct destination-egress reproduction was performed.

## Independent coverage

- **today_canvas_review:**2D/font/geometry allocation, producers/import/filter/pattern tracking, extraction/export/capture, Offscreen and bitmap transfers, frozen owner/site keys, raster/SVG provenance, glyph dispatch and canonical font policy. Relevant authoritative additions were compared to native mirrors. Ten focused native/helper tests passed; these do not cover bitmaprenderer serialization.
- **today_policy_review:** privileged persona/override/SeedSync/Settings/actor changes, the new GPU profile descriptor module, earlier IP-warning changes, native CSS media, Chromium client hints/identity, AudioWorklet and WebCodecs changes. Checked policy precedence, exact owners, secret handling, resets/regeneration, startup and native master gating.61focused Node tests passed.
- **today_gpu_integration_review:** WebGL canonical EGL routing, pinned SwiftShader ICD loading, WebGPU instance/adapter/device constraints, actual GPU resource/shader validators, readback/import/video provenance, ownership/lifetimes, dependency manifest/staging/strip/package integration, and scalar decoder selection/provenance. Eight focused native tests passed. GPU manifest verification and strict signatures for all three GPU libraries passed. All118imported decoder-source hashes matched the declared manifest, with one documented upstream delta.

The reviewers did not modify production code or launch browsers. They did not independently audit every line of vendored Skia, HarfBuzz, FreeType, FFmpeg or pinned GPU dependencies, fetch fresh upstream archives, execute dynamic exploits, or run cross-platform builds. Source and integration coverage is broader than the previous reviews, not a formal verification of all dependencies.

## Existing installed-test evidence

The latest installed Mac158BuildID20261015174757 passed331native GPU-profile checks,464unmodified-library checks with WebGPU enabled and448with it blocked. Node266and Python116tests passed, with14Python cases skipped. Additional renderer tests and exact acceptance scope are linked in `container-rendering-profiles/README.md`; pristine native replay passed144patches/409targets with no drift, and all82GPU resource hashes/signatures were verified.

Those tests verified actual resource bounds, repeated/restarted identities, sampled container/site/worker separation, context restoration, strict readbacks and known-fill attack resistance. They did not exercise the newly identified bitmaprenderer serializer and cross-owner WebGPU configure scenarios. Their pass counts cannot close those gaps.

Earlier feature-specific review defects were fixed and re-reviewed: canvas-exception-gated GPU identity derivation, partial preset resets, DOM float narrowing/union consistency, canonical export alpha conversion and unsupported WebRender font-collector fallback. These fixes remain distinct from the new open findings above.

## Work completed today

- Same-host recorded-visit filtering for IP conflict warnings, plus clearer Chromium settings availability text.
- AudioWorklet graph readback protection, CSS depth/gamut consistency, Chromium HTTP/JS client-hint coherence and WebCodecs hardware-preference normalization.
- Optional canonical font/software canvas/WebGL/WebGPU pipeline, producer/provenance/import/export/capture safeguards, pinned GPU/codec resource staging and package signing repairs.
- DOM empty/caret/fragment/bounding-union consistency fixes, including double-precision protected unions.
- Default-off per-container/site native GPU resource profiles for Apple, Intel, AMD and NVIDIA personas, frozen context profiles, activation/preset validation and installed Mac verification.

Realistic coherent GPU capability catalogs remain TODO. Current resource enforcement is not physical driver emulation. CreepJS still reports rotation and GPU/capability recognition warnings; Chromium identity retains the Gecko/V8 mismatch. No detector warnings were suppressed. Today's installation/testing left personal profiles unchanged.

## Subsequent fixes

All three findings were subsequently fixed, tested on the installed Mac BuildID20261015180857 and independently re-reviewed. See [fix acceptance](privacy-gap-fixes/README.md) for RED/GREEN evidence, exact tests and coverage limits. This preserves the original findings as review history rather than silently deleting them.
