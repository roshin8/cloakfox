# Canvas Producers and Provenance Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development; preserve earlier source and ledger. User explicitly approved implementation; no repeat permission gate.

**Goal:** Continue the approved complete pipeline, repair first-draw instability, implement a real fixed-font producer and preserve conservative pixel provenance through transfer paths. Do not misrepresent missing GPU/color/font capabilities as complete.

**Architecture:** Fixed-font HarfBuzz shaping/outlines share one run for geometry/metrics. Native/unsupported input retains guarded fallback. Thread-safe SourceSurface sidecar metadata records producers without changing pixel bytes or permitting extraction bypass. ImageBitmap clones/conversions preserve labels, and unlabeled IPC surfaces remain unknown.

**Tech Stack:** Firefox158 C++/Moz2D/HarfBuzz, existing licensed font pack, Selenium, Python/Node.

**Spec:** `docs/superpowers/specs/2026-10-15-complete-canvas-pipeline-design.md`.

## Global Constraints

- Experiment remains `cloakfox.experimental.canvas_pipeline`, default false, authoritative `canvas:canonical_2d`.
- Retain extraction/metric and strict GPU readback guards until full release acceptance.
- No native GPU or software platform renderer may be represented as a canonical shader backend.
- No content debugging properties, detector-specific exceptions, personal profile changes or early complete-mode label.
- Unknown/lost metadata always downgrades confidence; never clears host input flags.

## Review Focus

- Cold fallback families must not produce first-use missing glyphs for protected content.
- Failed/unsupported canonical text work must fall back without partial drawing or mutation.
- Font files must be bounded, pinned and loaded from app resources rather than host enumeration.
- Crop/color/alpha conversion and worker cloning must not erase GPU/native producer labels.
- Concurrent source metadata updates must never drop a contributor or become trusted through zero/unknown values.

## Task1: First-use font fallback (glyph_firstdraw_fix)

- [x] Preserve failing deterministic seed/profile and per-operator images.
- [x] Compile real GlobalFontFallback branch into a fixture; observe RED for cold allowed family with masking on.
- [x] Exclude protected masked content from async skipping, keeping existing synchronous cmap initialization and native async behavior.
- [x] Observe GREEN, emit standalone ordered patch, repeat fixed-seed cold starts in rebuilt browser with no sleeps/retries.

## Task2: Fixed-font text producer (canonical_text_impl)

- [x] Add actual packagedfont/HarfBuzz tests for glyph extents, advances, kerning, empty/space and strict unsupported-input refusal.
- [x] Implement shared shaped-outline result from pinned font bytes with Mozilla Unicode callbacks and HB OT font functions.
- [x] Integrate supported fill/stroke/measure paths behind frozen context flag; use same run and metric scale for geometry.
- [x] Tag unsupported/native text as HostText; retain guarded fallback without claiming general FontFace/bidi/color support.
- [x] Preserve native ownership, transform/clip/filter behavior; snapshot and generate separate patch.

## Task3: Thread-safe producer metadata (root)

Create `gfx/2d/CanvasPrivacy.h/.cpp`, export from moz.build. API:

```cpp
enum class CanvasPixelSource : uint32_t {
 Unknown=1, Software2D=2, FixedFontOutline=4, HostText=8,
 ExternalPixels=16, Media=32, GPU=64
};
void AddCanvasPixelSource(SourceSurface*, CanvasPixelSource);
uint32_t GetCanvasPixelSources(SourceSurface*);
void MergeCanvasPixelSources(SourceSurface* destination, SourceSurface* source);
```

- [x] Compile actual helper code against minimal surface/mutex primitives; assert no labels, null sources and unknown bits remain conservative. Stress concurrent OR updates and unknown merges.
- [x] Store metadata using SourceSurface ThreadSafeUserData with serialized initialization/update; add no context seeds, origin strings or hardware identity.
- [x] Add ImageBitmap owned source-mask field and clone member; preserve across readback wrappers, crop/resize/options and target optimization. Missing source labels remain Unknown.
- [x] Mark GPU snapshot producer outputs through four native async/sync paths (gpu_canonical_impl); preserve all existing readback behavior.
- [x] Context accumulates software/text/import sources; snapshots carry the union. Add media and external-input labels conservatively. Never use metadata alone to skip current extraction.

## Task4: Candidate validation and release decision (root)

- [ ] Integrate standalone patches in dependency order; strict replay/build and full Node/Python suites.
- [ ] Fresh source review and fix material findings before packaging.
- [ ] Test cold-start deterministic first-glyph reproduction, supported canonical text behavior, fallback cases, workers/transfers, isolation, PNG/crop consistency, GPU strict guards and settings persistence.
- [ ] Run pinned unmodified libraries and adversarial recovery tests on candidate before installed test.
- [ ] Install candidate with backup solely for requested installed acceptance, verify binary hashes/signature, repeat relevant tests. Restore prior active app if full acceptance fails.
- [ ] Record passed regressions separately from failed full-release requirements; do not mark whole objective complete without canonical GPU/customfont/color/media/cross-host acceptance.
