# First Chromium native canvas privacy patch

Implement without an additional approval gate, as requested by the user.

## Scope and ownership

The first increment covers RGBA8/sRGB Canvas2D getImageData and PNG/image exports
in documents and dedicated (including nested) workers. CEF supplies a secret
256-bit key from the owning Profile to each renderer process. Persistent profiles
retain their key; off-the-record profiles get a new in-memory key. A browser-only
canvas preference is fixed before any window in a context is created. Conflicting
open requests for a live context fail. The binary SDK cannot claim this capability.

Derive a site key with HMAC-SHA256 over the canonical schemeful top-level site.
Use the document’s committed browser-provided storage-key top-level site (also
after frame detachment); workers
inherit their creator's top-level origin. Do not use script URL or public container
IDs as secret material. Opaque origins and unsupported worker scopes are explicitly
outside this first increment, rather than assigning every opaque site the same key.

Readback transforms copies, never the drawing surface. Quantize one RGB bit and
replace it with keyed deterministic bits, preserving alpha and transparent pixels.
This is idempotent for matching coordinates, permitting PNG decode/readback checks
without accumulating noise. Absolute pixel coordinates preserve crop consistency.
Float16/non-sRGB readback, shared/service workers and raw WebGL/WebGPU readback
remain open bypasses. This is partial protection, not privacy parity or a claim
that arbitrary fingerprinting is prevented. The ready event retains privacyPatched
false and publishes a narrower native canvas capability version.

## Implementation and verification

1. Add owned loopback runtime tests; show the unpatched source binary fails
   different-container readback and explicit canvas policy requests.
2. Add profile prefs/key propagation and native Blink copy transformations,
   plus strict companion policy parsing and capability reporting.
3. Replay pinned patches, incrementally build the framework, preserve baseline
   SDK/app, package into a new SDK, compile the companion and compare framework hashes.
4. Run privacy runtime checks for deterministic reload/restart, containers, sites,
   worker inheritance, crops, transparent pixels, unchanged drawing buffers,
   exports and disabled behavior. Run the existing protocol/isolation/GPU checks.
5. Record actual coverage, focused code review, commit and push.
