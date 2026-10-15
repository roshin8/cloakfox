# Chromium worker and GPU privacy implementation plan

> Execute with the design, test-driven and parallel-investigation workflows; the
> user has explicitly requested implementation without another plan approval.

**Goal:** Extend the native Chromium privacy increment to shared/service-worker
canvas, WebGL pixel readback and GPU identification, with an explicit safe WebGPU
readback policy.

**Architecture:** Keep per-profile secrets and immutable per-context policy. Shared
and service workers use the effective browser StorageKey partition owner; unlike
per-page workers, an intentionally unpartitioned shared pool cannot belong to one
embedding page. Do not pick the first client or infer ownership from script URL.
Use existing native canvas hooks and no page wrappers. WebGL transforms CPU pixel
reads and PIXEL_PACK_BUFFER destinations after successful native validation,
leaving framebuffer/texture contents unchanged. WebGPU identifying adapter strings
are reduced while truthful features/limits stay intact. Arbitrary GPU mapped data
is never noised; a separate opt-in blockWebGPUReadback flag denies READ maps.
Default WebGPU compute remains exact. Safe selective WebGPU canvas-to-buffer noise
requires validated Dawn/GPU-service provenance and is explicitly deferred.

## Constraints and review focus

- Preserve prior canvas SDK/app, original binary SDK app, Gecko and the separate
  Firefox 158 worktree. Incremental framework build only; no duplicate jobs.
- Native errors, pack skips/row strides, destination element/byte offsets, row
  orientation, partial reads, padding and unrelated buffer bytes must survive.
- A failed GL read must not transform old destination bytes. Existing GL errors
  must remain observable. Zero-length and invalid calls preserve native semantics.
- PBO writes change only the readback destination, not framebuffer/texture storage;
  subsequent buffer copies/subreads must expose the protected result.
- Shared/SW storage-access/unpartitioned pools use the effective pool owner, not a
  claimed top-level site. Nonce/opaque identities remain unsupported.
- Worker first-script execution, restarts and private lifetime must apply owner
  before canvas use. Active-worker shutdown must not crash the companion.
- WebGPU map blocking is explicit and immutable before context creation, includes
  synchronous paths if exposed, and does not break WRITE maps/mapped-at-creation.
- Runtime capabilities remain partial; privacyPatched stays false.

## Tasks

- [x] Write failing owned runtime probes for shared/SW first-script canvas,
      partition/container/restart/private/disable behavior; implement native key
      transport and install SW ownership before script readiness.
- [x] Write failing WebGL1/2 direct/PBO probes; implement validated RGBA8 readback
      transforms, orientation/pack handling and debug renderer extension privacy.
- [x] Write failing actual WGSL render/compute probes; implement adapter/device
      info privacy and explicit READ-map denial, preserving exact default compute.
- [x] Add strict companion policy/capability negotiation and pinned follow-up
      patch replay metadata; verify unsupported SDK behavior and conflicting policy.
- [x] Incrementally build, package separately, verify all framework hashes and run
      full engine/unit/isolation/GPU/transport probes. Fix failures, focused review,
      record precise limitations/performance and commit/push.

Verified results: [worker/GPU report](../../dual-engine/cef-worker-gpu-privacy-20261015.json). This completes the scoped increment; selective WebGPU image noise and full parity remain deferred as described above.
