# Observed GPU compatibility implementation plan

> Execute with superpowers:subagent-driven-development. Implementer and independent final review are required. The user explicitly requested implementation of the described compatible recognized profiles; proceed without another approval round.

**Goal:** Admit complete observed profiles that retain both CreepJS recognition and genuine native behavior in Firefox159, as an optional exact-owner mode, without weakening privacy or changing Chromium inputs/processes.

**Spec:** User request2026-10-28 and preceding explanation: find complete observed recognized records, validate software-backend compatibility, enforce actual limits/behavior, preserve container/site ownership, readbacks and all checkpoints; test headlessly on159 and independently review.

**Architecture:** Preserve existing protected and reference modes. Add an independently saved `rendering:gpu_observed` request requiring the reference mode, canonical CPU backing and supported complete paired persona. Generate a separate observed catalog from the immutable pinned source, with explicit native semantic requirements; production uses full records, never CreepJS hashes or fixture exceptions. Shader bias is constrained in native typed translation, stencil state is initialized through real GL calls, and element-index reporting agrees with native fixed-restart validation. Reject unsupported records before persistence/context creation. Recognition is tested offline and through unchanged libraries.

**Global constraints:** Baseline65117fec36 and all earlier checkpoints remain; no reset/clean/checkpoint deletion. Reuse159worktree; native changes only owned Gecko/additions/patches. No Chromium source, builds, locks or processes touched. Keep installed apps/profiles unchanged. Headless disposable test app only. Two low-priority build jobs with own-process disk guard. Separate owner descriptors/secrets; no native hardware fallback, debug/timing enablement or weaker readback/import guards. Defaults off; disabling/recovery remains possible. Existing reference mode remains available. Unsupported observed persona families are rejected explicitly; no relabelling or silent fallback. Canonical public values may coincide; private records remain independently owned. Physical vendor-driver emulation is outside the accepted target.

## Tasks

- [x] Pin projection of unmodified CreepJS and audit every complete observed record, recording source provenance, recognition and actual semantic differences. Independently review candidate compatibility, especially Apple precision/varying/timeout behavior. Only admit profiles with a truthful native implementation.
- [x] Add source-generated observed catalog/policy with exact ownership, BrowserForge identity compatibility, immutable complete pairs and atomic dependency validation. Keep old descriptors valid; reject malformed/foreign/default-owner confusion and impossible overrides. RED/GREEN native and JS tests.
- [x] Implement and test native observed behavior: real initial stencil masks; native non-restart index bound; typed shader texture-bias clamping including all supported builtins/extension overloads and dynamic/uniform/constant arguments. Preserve API state changes, ordinary paths, cache ownership, context restoration and shader validity. Review before building.
- [x] Wire selected-owner optional control/dependencies/recovery and clear/import behavior. Test real settings handlers, other-owner invariance, restart and unsupported-persona rejection.
- [x] Replay all maintained patches exactly against159; build/stage a new independent app preserving prior apps/checkpoints. Headless native execution/resource/shader/state/context/worker ownership tests plus unchanged CreepJS/FingerprintJS with WebGPU enabled and both modes, broader graphics regressions, full Python/Node tests.
- [x] Final independent whole-change review, retain remaining detector warnings/unsupported profiles honestly, verify Chromium committed input key unchanged, local checkpoint and concise evidence.

## Review focus

- Recorded state must remain author-mutable and actually affect native drawing.
- Bias overload detection and new builtin resources must survive compiler reuse/caches and GLSL100/300 extension forms without rewriting author-defined functions.
- UINT32_MAX is WebGL2 fixed primitive restart; must not become an illegal element.
- Profile eligibility cannot change identities, leak actual GPU values or promote unsupported source limits.
- Recovery ordering, missing dependencies, owner-zero, imports and malformed booleans must fail closed without trapping enabled requests.

Research outcome: 55 complete observed projections are recognized in pinned CreepJS. Three Windows Intel/AMD/NVIDIA records retain their exact numeric vectors through native stencil initialization, typed texture-bias clamping and fixed-restart index behavior. Apple records require precision/varying/timeout behavior that the canonical backend does not faithfully provide; observed Apple activation is rejected. Existing four-family reference records remain byte-equivalent as parsed objects. No production detector hashes or special cases were introduced.

Build/replay: all 168 patches replay without fuzz or source differences. A new independent Firefox159 app was built and staged; prior app/checkpoints and installed apps remain unchanged. Full Python: 196 passed. Full JavaScript: 392 passed. CI helpers: 16 passed. Final native/regression/library acceptance passed; see acceptance-summary.json. Independent final source/evidence review passed. Local checkpoint records this completed implementation and its acceptance evidence.
