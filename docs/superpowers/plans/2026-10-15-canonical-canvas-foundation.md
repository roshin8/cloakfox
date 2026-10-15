# Canonical Canvas Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Implement the independently testable backing/policy foundation of the approved complete pipeline without removing existing protection or claiming completion.

**Architecture:** A new internal experiment preference emits a context-owned policy bit. Eligible content 2D contexts explicitly allocate a basic Skia backing target, including worker OffscreenCanvas, without accelerated/shared/native fallback. Existing extraction, font and metric guards remain authoritative. Full release is gated on subsequent canonical text and producer/provenance projects from the approved specification.

**Tech Stack:** Firefox158 C++/Moz2D, privileged JS policy, Selenium/geckodriver, Python/Node.

**Spec:** `docs/superpowers/specs/2026-10-15-complete-canvas-pipeline-design.md`.

## Global Constraints

- Existing source changes remain intact; use current158 worktree.
- Internal Boolean `cloakfox.experimental.canvas_pipeline` defaults false and emits exact key `canvas:canonical_2d`.
- No public complete-protection label or new public checkbox before full acceptance.
- Preserve all extraction/metric and strict GPU readback guards, permissions and seeds.
- Capture policy before unused-context first drawing; reset retains captured policy.
- System contexts and master-off contexts retain established native allocation.
- Canonical allocation failure must not silently fall back to a native backend.
- Font/data provenance and cross-host normalization are explicitly unfinished.

## Review Focus

- Delayed first draw after preference changes retains creation policy.
- Bitmap resize and provider reuse preserve existing content and transform/clip state.
- Invalid policy types do not bypass extraction guards or activate experiment.
- Worker/default-container ownership cannot read ambient identities.
- Allocation failure produces ordinary context failure with no alternate backend.

### Task 1: Central policy and internal toggle

Files: `CloakfoxOverrides.sys.mjs`, `CloakfoxPersonas.sys.mjs`, `CloakfoxSeedSync.sys.mjs`, `settings/cloakfox.cfg`; tests `test_graphics_optins.mjs`.

- [x] Write actual-module/VM tests that expect `applyGraphicsPolicy` to emit `canvas:canonical_2d:false` by default, reject wrong-type prefs, override stale per-field config, update every saved valid config and preserve sentinels/seeds.
- [x] Run Node test and observe missing-field failure before implementation.
- [x] Emit only the exact Boolean using strict preference type handling. Extend graphics policy observer/backfill without regenerating identities:

```js
const pref = "cloakfox.experimental.canvas_pipeline";
let enabled = false;
try { enabled = Services.prefs.getBoolPref(pref, false) === true; } catch {}
return { ...config, "canvas:canonical_2d": enabled };
```

- [x] Run all Node tests; extend settings persistence probe to verify internal pref startup and existing UI independence. Do not add a public complete-mode control.

### Task 2: Frozen canonical backing allocation

Files: native `CanvasRenderingContext2D.cpp/.h`; new ordered `patches/canvas-canonical-backing.patch`; test `test_canvas_canonical_backing.py`.

Interfaces: `CaptureCanonicalCanvasPolicy()` captures exact owning-context policy; `UseCanonicalCanvasBacking()` reports frozen bit; `TryBasicTarget` provides canonical target when selected.

- [x] Snapshot both native files before edits in a task-specific directory.
- [x] Add actual-code compiled policy tests for strict Boolean config/master/principal gates. Add allocation-routing test that executes the extracted decision against accelerated/shared/basic fixtures and verifies canonical failure never calls those native alternatives.
- [x] Observe RED before adding native policy/branch.
- [x] Capture policy at `SetContextOptions` before null-options return, with owner principal and exact owning config; preserve through reset. Use a separate member from the existing glyph seed.
- [x] In `EnsureTarget`, choose only `TryBasicTarget` for a selected canonical context; keep existing provider bookkeeping/clear/path/clip/transform logic. Create the canonical target with:

```cpp
aOutDT = Factory::CreateDrawTarget(BackendType::SKIA, GetSize(), GetSurfaceFormat());
```

- [x] Require the basic provider and target backend to remain canonical when reborrowing. Retain normal errors if target creation/initialization fails. Normal/master-off contexts retain old backend selection. Do not remove image extraction or metric protections.
- [x] Run compiled tests; generate standalone patch from snapshots; append to ordered list.

### Task 3: Native runtime and installed foundation validation

Files: `probe_canvas_canonical_backing.py`; existing canvas/render/settings/graphics/library probes; evidence `docs/canonical-canvas-foundation/`.

- [ ] Write disposable-profile on/off/wrong-type/native tests for HTML, Offscreen, worker and transferred contexts; verify reload stability, bitmap reset, clips/transform, gradients/patterns/filter/shadow, PNG/crop agreement and policy retention.
- [ ] Use browser privileged diagnostics or actual-code coverage for backend choice; never expose a content-facing debugging property. Pixel equality alone does not prove backend choice.
- [ ] Verify flat authored colors still receive legacy extraction protection in the experimental phase; calibration recovery remains a known failed full-release acceptance test.
- [ ] Stage exact source resources, build, run strict replay, run all Node/Python tests and actual runtime probes. Obtain an independent final source review and resolve material findings.
- [ ] Package and install only a green foundation build with backup/signature/hash verification, preserving profiles. Repeat on/off probes and pinned unmodified libraries against `/Applications/Cloakfox.app`.
- [ ] Record installed results and honest unfinished acceptance gates. Do not mark the full pipeline complete.

## Dependent projects and release gate

The approved spec requires separate plans for canonical font shaping/rasterization, canonical image/SVG/media production, cross-API provenance, a canonical GPU backend, and final extraction cutover. Concrete repository findings: FreeType/HarfBuzz sources and31 licensed fonts exist; Cocoa does not compile a portable FT renderer; HB outline drawing is built but HB_NO_PAINT excludes color-glyph support. These projects cannot be represented as a completed backing-target switch. No public complete-pipeline setting or noise removal is permitted until they and cross-host acceptance pass.

Execution ruling: the user explicitly approved the architecture and requested implementation in this session. Proceed with this reversible experimental foundation without requesting the same authorization again. Preserve the approved full goal and its unfinished gates.


## Actual outcome

Tasks1/2 implemented, source built/replayed, actual native fixtures pass. Task3
installed tests executed; matrix regressions pass, but initial glyph probe38/40
is unresolved despite a40/40 diagnostic rerun. Full privacy acceptance fails
known-fill recovery. Prototype removed from active installation; previous app
restored, tested prototype retained. The full approved pipeline is unfinished.
See `docs/canonical-canvas-foundation/results.json` and `ledger.md`.
