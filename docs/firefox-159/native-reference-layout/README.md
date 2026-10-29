# Native reference GPU and canonical layout — Firefox159

This continuation implements executable CPU-renderer capacity, native GPU
profile enforcement and actual document layout normalization. The earlier
[readiness investigation](../reference-geometry-readiness/README.md) remains a
historical negative baseline. It is not evidence for this new implementation.

The two new requests are independently saved in each selected container:

- `rendering:gpu_reference`: a complete recorded Apple, Intel, AMD or NVIDIA
  pair, with explicit Firefox159/privacy adaptations and native resource,
  precision, shader and framebuffer enforcement. Unsupported persona pairs are
  rejected rather than silently changing the saved identity.
- `geometry:canonical`: a document-owned 96DPI/60-app-unit layout context,
  canonical fonts and font preferences, fixed theme/control/scrollbar metrics,
  canonical UA-platform styling and native SVG paths. Physical output scaling
  uses the presentation/compositor path; it is not a rectangle getter override.

Both default off. The existing canonical software-rendering backing must be
enabled; reference GPU mode also requires the existing container GPU policy.
The controls live in Graphics for the selected container. Reload affected pages
and recreate workers after changing a mode. Saved requests can always be turned
off after a backing failure. Disabling restores the existing protected behavior.

The four reference records are derived from the pinned paired Firefox146 source
archive. The executable adaptation is recorded separately in
`additions/cloakcfg/gpu-reference-executable.json`. Full32-bit precision,
coherent limit relationships, canonical WebGPU buffer bounds, privacy-denied
debug/timing extensions and version-specific exclusions are explicit. These
records do not certify physical vendor-driver emulation or promise zero
CreepJS warnings.

Container records, secrets and seeds remain separate. Ordinary public profile
values and verified canonical authored pixels can coincide. Canonical rendering
removes host-dependent output rather than requiring post-readback noise; existing
protected fallback exports still use independent owner/site noise. Records are
never shared or copied as a substitute for ownership. Native window/worker validation rejects malformed/foreign metadata.
Existing protected readbacks, canvas input ownership, library integrity,
normal sandboxing and CPU-only renderer selection remain in force. No host-GPU
fallback, hardware inventory or network discovery is introduced.

Canonical geometry is admitted only after a completed normalization generation.
Relevant live policy, identity, owner, zoom or parent-generation changes revoke
admission until a fresh document is built. Unsupported print/RDM, nonunit
browser full/text zoom and remote child-frame paths retain the existing geometry
protection. Same-process owned child frames inherit the normalized parent output
scale without applying it twice. External SVG resources share the parent layout
metrics while retaining their own query-admission checks.

## Evidence and reproducibility

- `backend.json` and `staged-backend-execution.txt`: exact signed staged CPU
  libraries, manifest-v2 provenance and real raster/shader/resource execution.
- `build-status.json`: native Firefox159 build state; failed attempts are retained.
- `patch-replay.json`/`.log`: complete ordered patch replay and source agreement.
- `native-helper-tests.txt`, `node-tests.txt`, `probe-policy-tests.txt`: focused
  native, manifest, policy and settings regression results.
- `code-review.md`: independent whole-change review and any outstanding findings.
- `run-runtime.py`: explicit self-contained app, headless environment, native
  acceptance, regression, library and full Python phases. Browser results are
  recorded in the corresponding `*-runtime.json` receipts.

The new app is staged separately at
`firefox-src/.tools159/acceptance-native-reference-layout/Cloakfox.app`.
Installed applications, personal profiles, all prior checkpoints and Chromium
build inputs/processes are preserved. Large raw probe outputs remain under the
ignored `tests/fingerprint/reports/firefox159-native-reference-layout` directory.

## Final acceptance

[Acceptance summary](acceptance-summary.json) identifies the rebuilt app by XUL
SHA-256 `7a54287b1c98ea8525472228ae0514f0708f59c865ff628db837abd330b6a343`.
All five native acceptance probes and 22 broader regression probes pass on this
artifact. GPU enforcement passes 1,035 checks; privileged/content touch policy
passes 32; real settings handlers pass 66. Geometry passes 32 samples, including
10 actual widget-paint/native-input samples, live fractional/2x scaling, both
scrollbar sides, frames, real ruby shaping, reload and restart.

The complete suites pass 190 Python tests, 381 JavaScript tests and 16 build
helper tests. Unmodified CreepJS/FingerprintJS audits pass 472 checks in the
existing protected mode and 471 in reference/canonical mode, with WebGPU enabled
in both. Each mode executes both libraries across eight cases, three times.
Firefox-identity canonical cases have no reported CreepJS rectangle or pixel lie;
GPU/capability warnings remain, and Chrome-UA cases retain their engine mismatch.
See [the retained warnings](creepjs-warnings-current.json). These results do not
claim undetectability, physical-driver emulation or cross-platform pixel parity.

The independent source reviews have no open actionable findings. Runtime
failures, fixture repairs and prior build receipts remain preserved separately.
All 167 ordered patches replay successfully and match the built source. The
Chromium committed input key and earlier Git checkpoints are unchanged. No
installed application, personal profile or native desktop UI was used or changed.
