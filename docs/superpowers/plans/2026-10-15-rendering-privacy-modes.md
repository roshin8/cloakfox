# Optional Rendering Privacy Modes Implementation Plan

**Goal:** Ship two opt-in graphics privacy modes without removing existing privacy guards.

**Architecture:** Central authoritative JS graphics policy feeds owning-container native
overlays. Canvas adds deterministic draw-time glyph protection; WebGL carries an
internal profile selection to the host to restrict real context capabilities.

**Tech stack:** Firefox 158 C++, privileged JS modules, Selenium/geckodriver, Node/Python.

**Spec:** `docs/superpowers/specs/2026-10-15-rendering-privacy-modes-design.md`.

## Global constraints

- Preserve all existing extraction, strict GPU readback and permission protections.
- Both new global preferences default false; preserve seeds and stored overrides.
- No native GPU name persistence or page-facing detector special cases.
- Context-owned policy/seed capture; new contexts apply toggles after reload.
- Do not overwrite prior uncommitted consistency fixes or unrelated user changes.

## Review focus

1. Wrong-type/stale overrides must not defeat authoritative graphics policy.
2. Worker/transferred contexts must use their own container/site identity.
3. Draw transform restoration and bounds must survive early returns/errors.
4. GPU profile values must affect actual allocation/compiler validation.
5. Optional modes must never disable legacy guards on uncovered paths.

## Task 1: Settings and persistence

- [x] Add failing Node tests for false defaults, startup/pref backfill, independence,
  corrupt configs, override precedence and byte-preserved seed/manual/network fields.
- [x] Implement field-only central graphics policy using the two exact pref/key pairs
  in the spec; wire startup and preference observers without identity regeneration.
- [x] Add two settings rows with bullet descriptions, experimental scope and reload
  requirements; add disposable-profile UI persistence test.
- [x] Run relevant Node tests and check source/installed-resource parity after staging.

## Task 2: Additional canvas rendering protection

- [x] Add failing actual-code/helper tests and runtime comparisons for the optional
  glyph draw perturbation, policy capture, author state restoration and isolation.
- [x] Implement a small deterministic glyph transform with context-owned selection
  and seed; keep all old extraction gates and uncovered drawing behavior intact.
- [x] Snapshot the pre-edit native files; generate a new ordered standalone patch.
- [x] Test text fill/stroke, RTL/maxWidth, clipping, copies/reset and all Offscreen paths.

## Task 3: Compatible GPU profile

- [x] Add failing policy/profile tests and actual resource-allocation probes.
- [x] Carry the validated opt-in bit through internal serialized context options.
- [x] Restrict host limits before initialization using a supported conservative
  whole profile, with version-correct capabilities and fail-closed backend rejection.
- [x] Route masked identity, configured capability/extension/precision reporting
  consistently; retain native validation, state, master-off and readback restrictions.
- [x] Generate a separate native patch; verify below/above-profile allocation and
  shader constraints, one-sided custom settings, workers and context restoration.

## Task 4: Review and installed verification

- [x] Independent source review, resolve actionable findings and freeze native edits.
- [x] Stage exact JS resources, append patches, build and replay from pristine archive.
- [x] Run Node/Python suites and development mode matrix; repair failures first.
- [x] Package and atomically install with backup, signature/hash/provenance manifest.
- [x] Rerun graphics/privacy probes and unmodified libraries on installed Cloakfox,
  including defaults, each toggle independently, both together and native controls.
- [x] Publish results, residual privacy/compatibility limitations and restart instructions.

Implementation is authorized by the user's explicit request; execute in this chat.
