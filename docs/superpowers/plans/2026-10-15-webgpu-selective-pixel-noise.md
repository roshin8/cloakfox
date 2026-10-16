# Selective WebGPU pixel noise implementation plan

**Goal:** Apply existing container/site-keyed canvas noise to validated WebGPU
RGBA8/BGRA8 opaque image readbacks without changing arbitrary compute buffers.
The user requested implementation and tests without another approval gate.

**Architecture:** Derive the existing native site key in Blink and transport it
through a dedicated internal Dawn device descriptor, never labels or page JS.
Dawn copies it at device creation. The Metal backend compiles a private HMAC-SHA256
pipeline before exposing the device, and dispatches it immediately after eligible
validated texture-to-buffer copies. Transform actual destination bytes in command
order; do not maintain buffer provenance tags. Later copies and overwrites have
normal byte semantics. Canvas/source texture storage remains unchanged.

**Scope:** Metal; RGBA8Unorm/BGRA8Unorm and their sRGB storage equivalents; alpha255
only, pixel coordinates, explicit offsets/strides/layers. Same HMAC as Canvas2D,
RGB canonicalization for BGRA. Other formats, transparent pixels and computational
extraction through custom shaders remain outside scope. Descriptor ownership is
trusted renderer engine state, matching existing canvas hooks, not a new defense
against a compromised renderer. Strict all-READ-map denial remains independent.

- [x] Trace native submit validation and Metal execution; write owned image,
      buffer-copy, overwrite, validation and presentation regression probes.
- [x] Run RED against prior worker/GPU framework; preserve failure log.
- [x] Implement internal descriptor transport, immutable device key, private Metal
      HMAC pipeline and execution-time transform. Reject unsupported backend keys;
      route protected BGRA away from optional compute-copy emulation.
- [x] Verify same output as Canvas2D, worker/private/restart/site ownership,
      padding/subranges/layers, exact compute/failed submissions and disabled
      controls. Preserve earlier SDKs/apps and package a separate source SDK.
- [x] Run full engine/C++/sandbox/transport suite, patch replay/hash checks, focused
      review; record limitations/performance; commit and push.

Verified evidence: [dated result](../../dual-engine/cef-webgpu-pixel-privacy-20261015.json).
