# Complete canvas pipeline integration

User authorization: finish remaining implementation, preserve a toggle and privacy, and test the installed browser. User clarified 2026-10-15: test on Mac for now. Windows/Linux differential verification is outside this run's acceptance scope; no cross-host guarantee.

Spec: ../specs/2026-10-15-complete-canvas-pipeline-design.md. Existing producer/provenance work is a prerequisite; do not redo it. Current source baseline is dirty codex/firefox-158-port; preserve all earlier changes and patch order.

## Non-negotiable gates

- Default-off policy is authoritative in every existing/new container and worker. No content option may enable a private renderer field.
- No removal of existing extraction/metric/GPU safeguards until implemented producer and transfer acceptance demonstrates replacement coverage. Never use a source label as a certificate.
- No host GPU fallback when canonical GPU requested; preserve native renderer otherwise. Dependencies pinned, licensed, bounded, reproducible and app-bundle-only.
- Native alpha/taint/CORS/errors and user media consent remain unchanged.
- Never suppress detector warnings or treat diagnostic process success as privacy acceptance.

## Independent implementation tasks

1. Fonts: sanitized author table faces; bundled deterministic script fallback; Mozilla bidi/script segmentation; HB outlines with shared metrics; pinned OFL color emoji with canonical PNG decode; styles/axes/spacing; rendering/compositing/outline ordering. Owner complete_font_renderer. Unit RED/GREEN, actual Gecko compile, window/worker/custom/RTL/emoji runtime corpus.
2. GPU: pinned ANGLE+SwiftShader isolated dylibs; Vulkan-only verified CPU ICD; frozen native WebGL config/IPC and CPU presentation; separate isolated WebGPU Vulkan adapter. Owner complete_gpu_backend. Native/default and missing/tampered backend failure tests, shader/texture/readback/presentation installed corpus. No Metal-as-canonical shortcut.
3. Provenance: value record with version/context/opaque128bit owner; conservative native merges; same-process ImageBitmap/Offscreen lifecycle; validated buffer/shared descriptor IPC; image/media transfer retention. Owner complete_surface_provenance. Actual C++ core/wire tests and Gecko IPDL generation. Unsupported platform handles remain Unknown, not upgraded.
4. Root: full-width HMAC owner derivation and immutable context policy; snapshot/import/pattern/capture/media/scaling propagation; canonical image/color producer routing and consumer graph; authoritative policy/settings/staging and integrated adversarial tests. Snapshot shared context nontext regions, preserve agent text edits.

## Root integration tasks and verification

- [x] Owner-key protocol RED/GREEN and old seed protocol regression.
- [x] Frozen context/offscreen ownership RED/GREEN; no receiver config recompute.
- [x] Preserve metadata before capture copies, image wrappers, resizing and optimization.
- [x] Canonical image/SVG/media producer paths and exact opaque author colors; preserve alpha and security semantics.
- [x] Full read/export/bitmap/worker/pattern/texture/VideoFrame/capture consumer corpus; no raw host-input fast path.
- [x] Authoritative opt-in bridge for canonical 2D/WebGL/WebGPU; stage pinned resources and license manifests through replay/build/package.
- [x] Integrate all append-only native patches; strict replay with zero fuzz/offset/drift; complete Node/Python tests.
- [x] Independent review of integration and fix material findings with regression tests.
- [x] Candidate semantic, isolation, adversarial recovery/amplification, memory/failure/presentation/capture/performance tests.
- [x] Package/sign/install with backup, validate exact binary hash/runtime, repeat complete Mac acceptance. Retain every CreepJS/FingerprintJS warning and distinguish identification of protection from recovery of host information.

## Review focus

No labels may upgrade an unknown or conflicting producer. Offscreen transfer precedes context creation and must keep sending policy. Structured clone policy must not weaken existing SameProcessScopeRequired. Glyph bitmap/outline overlap, font metrics and style/maxWidth/baseline semantics must agree. ANGLE process environment must not select an external ICD. Missing shader resources or sandbox JIT failures must not fall back to host graphics. Software labels do not prove canonical SVG/native media pixels. The known-fill native-path baseline alone is not proof of host leakage once paths are canonical; adversarial acceptance must distinguish known author pixels from host-dependent text/GPU inputs.

## Mac acceptance result

Completed and installed 2026-10-15, runtime BuildID20261015154131; XUL275455a276f84bc7f4f74802b18ab8df2ca206d0fb1bad91796be614d8555b42. All listed Mac gates passed. See docs/canvas-pipeline-completion/README.md and verified-evidence.json. Cross-host/Windows/Linux verification remains outside this user-approved Mac-only run, not implicitly passed. Legacy/fallback and refusal policies remain; no zero-detection guarantee.
