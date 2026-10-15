# Container Rendering Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce avoidable geometry/GPU warnings with independently owned, BrowserForge-compatible rendering profiles, without weakening privacy.

**Architecture:** Keep profile selection and activation privileged and owner-scoped. Enforce the selected profile in layout and GPU execution before changing page-facing measurements. Retain current protected behavior until feasibility, isolation and compatibility gates pass.

**Tech Stack:** Firefox 158 C++ layout/WebGL/WebGPU, privileged persona modules, native Settings UI, Selenium/geckodriver and pinned fingerprint libraries.

**Spec:** [Container-owned rendering profiles](../specs/2026-10-15-container-rendering-profiles-design.md).

## Global Constraints

- Rendering profiles remain separately owned by each container.
- Preserve deterministic top-level schemeful-site isolation inside each container.
- Profiles must be compatible with the saved BrowserForge persona.
- Apple, Intel, AMD and NVIDIA persona support is mandatory; SwiftShader-only support is insufficient.
- Keep the feature optional and off by default.
- Do not weaken privacy to reduce detector warnings.
- macOS arm64 installed testing is the current runtime scope.

This is the revised staged plan, not a claim that an enforceable per-persona layout/GPU implementation already exists. Stages 1–2 must produce concrete validated descriptors and a source-level layout design before native implementation steps are expanded; do not substitute guessed capability tables or a shared profile to skip those gates.

## Review Focus

- Identical personas in different containers: independent records and identity-bearing output, not coincidental random-persona differences.
- Mixed tabs/workers and restoration: retain original owner, never active-tab or container-zero resolution.
- Unsupported BrowserForge hardware/manual overrides: explicit rejection with all prior state preserved.
- Toggle transitions and partial migration: no silent identity rotation, partial global activation or policy mixture in existing contexts.
- Missing backend, fonts or descriptor: preserve protection and guards; never fall back to host identity.

## Task 1: Capture enforceable profile candidates

**Files:** existing `tests/fingerprint/probe_webgl_backend_profile.py`, `probe_canvas_canonical_gpu.py`, `probe_dom_geometry_consistency.py`; new evidence under `docs/container-rendering-profiles/`.

- [ ] Capture the complete actual software-backend capability/precision/extension tuple, with allocation and shader-validation results, rather than copying CreepJS hash lists.
- [ ] Compare candidate tuples with effective BrowserForge OS/hardware/display/font families. Record unsupported claims explicitly; do not rename the renderer to match them.
- [ ] Run identical-persona, distinct-container/site baseline probes, including WebGPU enabled/disabled and all existing guards. Save BuildID, binary hash, owner-policy state and raw detector results.
- [ ] Obtain complete versioned reference captures for at least one explicit model/driver profile in each required family (Apple, Intel, AMD and NVIDIA); family names alone are not sufficient. Record reference provenance and validate backend execution against these captures.
- [ ] Produce a validated candidate catalog and compatibility matrix. Stop this stage if independent container profiles cannot be enforced without host fallback or if all effective identities collapse.

## Task 2: Finalize owner-scoped selection and layout contracts

**Files:** new design addendum beside the spec; inspect `CloakfoxPersonas.sys.mjs`, `CloakfoxOverrides.sys.mjs`, `CloakfoxSeedSync.sys.mjs`, `CloakfoxSiteSeed` helpers, `CloakfoxGeometry.hpp`, `Element.cpp`, `AbstractRange.cpp` and native layout/font paths.

- [ ] Define the persisted versioned descriptor, owner/site runtime binding, validation result and lifecycle using the validated catalog from Task 1. Unique privileged identifiers must never become page-visible fingerprint fields.
- [ ] Map each layout input affecting Element/Range/SVG/offset results to its protected producer. Specify how fonts, intrinsic sizes, controls, zoom and transforms are enforced and how unsupported cases retain protection.
- [ ] Document that common authored geometry/API constants may coincide while identity-bearing profiles remain independent; include an explicit same-persona two-container separation example.
- [ ] Expand the native tasks into exact source edits and failing tests using those finalized contracts before writing production code. No getter-only randomization, detector exceptions or unvalidated physical-GPU labels.

## Task 3: Implement selection, compatibility and toggle atomically

**Files:** `CloakfoxPersonas.sys.mjs`, `CloakfoxOverrides.sys.mjs`, `CloakfoxSeedSync.sys.mjs`, `content/settings.js` and its existing markup, `settings/cloakfox.cfg`; persona/Settings tests.

- [ ] Add failing tests for identical-persona independent containers, site derivation, restart persistence, single-container regeneration and unchanged seeds/manual overrides.
- [ ] Add failing tests for malformed/stale records, missing owners, conflicting hardware overrides, unsupported backends, rejected edits/persona generation while enabled and partial-activation rejection.
- [ ] Implement selection/validation against the finalized catalog, with no ambient-container lookup or shared-profile fallback.
- [ ] Add the default-off toggle `cloakfox.opt.container_rendering_profiles`; validate every affected owner before activation, preserve selections on disable, and explain reload/worker-restart requirements.
- [ ] Verify failed activation leaves all settings, personas and records unchanged. Verify master-off and existing mode controls retain their behavior.

## Task 4: Enforce each profile in native rendering

**Files:** exact layout paths finalized in Task 2; `ClientWebGLContext.cpp`, `WebGLContextValidate.cpp`, WebGPU adapter/device enforcement, authoritative additions and ordered native patches.

- [ ] Implement the finalized protected layout producers and cross-API consistency tests before replacing current readout noise. Cover intrinsic text, custom/system fonts, multiline bounds, zero-area boxes, carets, transforms and SVG.
- [ ] Enforce the owning descriptor in GPU allocation, shaders, precision/extensions and WebGL/WebGPU limits; test rejection just above each controlled boundary.
- [ ] Test main-thread and worker creation, blank frames, simultaneous containers, canvas transfer, context restoration and owner-unavailable cases. Preserve captured policy and existing unknown-input/readback guards.
- [ ] Verify missing/tampered backend/font dependencies cannot trigger a host renderer/identity fallback or another container's profile.
- [ ] Replay authoritative patches on pristine source and check against the compiled native tree. Review native implementation before package/install.

## Task 5: Installed acceptance and detector comparison

**Files:** existing fingerprint/GPU/geometry probes plus new same-persona isolation cases; evidence under `docs/container-rendering-profiles/`.

- [ ] Run mode off/on, WebGPU off/on, at least two supported BrowserForge families, actual containers/default and two sites through repeated reloads and restart.
- [ ] Run full renderer/provenance/import/transfer regressions, actual allocation/shader tests and unchanged pinned fingerprint libraries. Record every warning, not only pass counts.
- [ ] Require independent code review, successful build/replay, strict package signing/integrity verification and reruns on installed `/Applications/Cloakfox.app` using disposable profiles.
- [ ] Publish a privacy/separation acceptance table and before/after warnings. Block release on host identity fallback, mixed profile behavior, container coupling or weakened guards. Never declare zero warnings unless observed.

No product code, app installation or settings changes are authorized by this documentation-only update itself; implementation is the next separately requested step. No new branch publication is performed here.

## Native GPU enforcement implementation update —2026-10-15

The user's follow-up authorizes native enforcement for all four physical-family personas. The implemented contract is bounded virtual resource execution on canonical software graphics, not physical-driver parity. Exact native edits cover WebGLTypes IPC profile code, ClientWebGLContext immutable owned descriptors/config and transfer provenance, WebGL host cap/shader restrictions, WebGPU Instance ownership, Adapter actual limits and IPC adapter rejection. GPU identity uses an independent HMAC domain; profile selection never bypasses readback exceptions or guards.

- [x] Default-off native/Settings toggle and all-owner activation preflight; preserve identities on disable.
- [x] Transactional complete preset validation; unsupported initial new personas keep non-GPU masking and reject GPU creation.
- [x] Actual bounded resource enforcement for Apple/Intel/AMD/NVIDIA; same-persona real container/site/worker checks.
- [x] Captured context metadata and conservative overrides retained through live changes/restoration; container/site transfer guard.
- [x] Independent code review, pristine native replay, signed candidate and installed Mac acceptance, WebGPU enabled/disabled library runs.

Broader protected layout producer expansion and complete physical driver execution parity are not claimed by this GPU change. Current DOM geometry protection remains enabled; detector warnings are documented without suppression. Evidence and exact acceptance scope: `docs/container-rendering-profiles/README.md`.
