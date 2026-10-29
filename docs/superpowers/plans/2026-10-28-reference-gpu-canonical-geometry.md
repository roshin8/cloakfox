# Reference GPU profiles and canonical geometry implementation plan

> Execute with superpowers:subagent-driven-development; independent task and final reviews are required.

**Goal:** Add opt-in, independently owned per-container GPU reference profiles and canonical geometry on Firefox159, preserving privacy and all checkpoints without modifying Chromium build inputs/processes.

**Spec:** The user's2026-10-28 request to implement GPU reference profiles and canonical geometry, toggleable and separate per container, without weaker privacy, tested on159 and reviewed. Existing physical-driver emulation is outside the agreed acceptance target; coherent executable profiles with canonical rendering remain required.

**Architecture:** Recorded paired WebGL1/2 records are separate from admitted executable profiles. Imported data is immutable, pinned and provenance-tagged. Native shader/resource/backend guards must validate real support; unsupported reference vectors cannot be relabelled as supported after silently clamping. Geometry must come from canonical layout, not exemptions for detector fixtures or merely disabling presentation protection. Native fonts already use the canonical backend; other layout inputs require explicit normalization/admission and live-transition safety.

**Tech stack:** C++ Gecko/privileged settings, Python offline importer, headless Selenium, native compiled helpers, unmodified CreepJS/FingerprintJS.

## Global constraints

- Preserve commits36aef7ee7f/ec1f1158d3 and all earlier checkpoints; no resets/cleans.
- No edits or builds in Chromium framework inputs/output trees or the separate158worktree. Read-only inspection of its pinned canonical backend source is permitted.
- Keep installed apps/personal profiles unchanged; use a separate self-contained159 test app.
- Per-container keys must use exact ownership, existing secrets and schemeful-site derivation. No secret rotation or default-container fallback.
- Defaults off; disabling a new mode restores the existing protected behavior, not native host values.
- No host GPU/driver fallback or getter-only claims. Integrity and readback/import guards remain required.
- Geometry may bypass additive presentation only after actual canonical layout prerequisites are established. Font selection alone is insufficient.
- No detector hash exceptions or changes to upstream detection fixtures.

## Tasks

- [x] Pin/import complete paired Firefox WebGL1/2 reference data from upstream fpgen model2/2026 (archive6530b8322cdaa4ec042921c8d9a0369a0e6e0269ba636c01a7203e4a2f109936). Check archive/file hashes, decode conditional GPU/GL1/GL2 ownership and retain source provenance. Test corrupt/cross-paired inputs. Keep executable admission separate.
- [x] Evaluate complete references against canonical backend, including precision/ranges/extensions, actual resource/shader operations and API error semantics. Implement native admission/enforcement and descriptors with strict ownership; mark unsupported references accurately rather than using native values. Add per-container setting/persistence and activation preflight.
- [x] Implement canonical geometry policy and actual layout prerequisites: bundled/author canonical fonts, theme/control metrics, font-size preferences, zoom/device rounding and SVG path/transform behavior. Freeze or safely reconstruct mode/identity during updates. Unsupported paths retain protection; no native fallback. Test Element/Range/SVG, caret/empty/fragments, controls and hit-testing/painting agreement.
- [x] Wire per-container settings descriptions/dependencies and typed keys. Test state persistence, reset/import/malformed settings, atomic rejection and isolation.
- [x] Run task reviews and repair findings before rebuilding. Stage only owned source additions; replay patches against159 without drift. Rebuild2low-priority jobs with own-process disk guard.
- [x] Stage separate test app; test both modes/off controls, all four families, owned records/sites/workers, reload/restart, native bounds, geometry semantics and unmodified library audits. Run appropriate broader regression suites; retain warnings/failures.
- [x] Final independent review, evidence, and local checkpoint. Do not declare success for unsupported references or unnormalized geometry paths.

## Review focus

- Source data and executable support are different facts; documented source integrity is not physical-driver certification.
- Native themes, font minimums, device units, SVG/stroke/clip/markers and inherited metrics must not escape geometry prerequisites.
- Query-time toggles cannot reveal an old native layout before reconstruction.
- Malformed owner descriptors and unsupported references must not expose host values.
- Shared public capability/geometry values do not imply shared container records/secrets.

Current evidence: [native implementation and integration](../../firefox-159/native-reference-layout/README.md). The source-derived GPU mode passes1,035 actual Firefox159 checks and the UI passes66 checks. Canonical geometry passes its actual layout, widget painting and native input checks on the final159 app. All native, regression and unmodified-library phases pass on that artifact. The earlier readiness report is preserved as a historical negative baseline.

Ruling: preserve verified canonical pixel exports as exact/common output. Separate container records, secrets and contexts do not require identical authored pixels to differ. Existing fallback noise remains partitioned; new tests distinguish these policies rather than adding readback noise to satisfy a mistaken test assumption.
