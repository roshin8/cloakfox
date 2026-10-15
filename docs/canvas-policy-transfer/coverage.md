# Native canvas policy transfer

The native value `gfx::CanvasPrivacyMetadata` carries renderer policy version,
container id, opaque 128-bit owning policy key, and contributor bits. It contains
no origin strings or raw fingerprint secret. Ownership and contributors are
separate from origin-clean, author permissions, and extraction permission.
No provenance label bypasses extraction protection.

The surface sidecar is synchronized. The first assignment establishes identity;
subsequent writes union contributors. Conflicting identities permanently become
unknown rather than selecting the receiver's context or ambient container zero.
Malformed or unsupported versions, invalid source bits, and missing owner keys
are normalized conservatively. Native IPC deserialization validates the record
before attaching it to pixels. It cannot authorize origin-clean or permissions.

Native transfer coverage:

- SourceSurface crop/copy and ImageBitmap backing/clone records retain the entire
  record, including bitmaprenderer transfer and replacement snapshots.
- OffscreenCanvas captures policy before a context exists and retains it across
  worker transfer. The receiving global cannot recalculate ownership.
- layers::Image retains a synchronized record through capture/media queues and
  rebuilds. SourceSurfaceImage takes its initial record from its source surface.
- SurfaceDescriptorBuffer and SurfaceDescriptorShared carry the validated record
  over IPC; shared wrappers, native RGB readback and remote image import restore
  it. YUV/NV exports and conversion add the Media contributor.
- Existing Gecko same-process restrictions on ImageBitmap and OffscreenCanvas
  structured clone remain unchanged. Page objects cannot supply native metadata.

Platform texture descriptors and untracked native producers remain Unknown.
Texture serialization that has no native owner record sends Unknown. This is a
conservative fallback, not evidence that GPU arithmetic, media conversion,
platform rasterization, or image decoding is canonical. Complete-mode acceptance
still requires producer coverage and testing of all exposed fast paths.

Verification: the executable C++ metadata/wire harness tests identity roundtrip,
conflicting owners, malformed versions/bits, truncated wire records, no relabeling
after unknown, and concurrent contributor union. The test transport signature
matches Gecko's lvalue ReadParams API. Focused canvas Python tests exercise these
helpers; they do not replace a native compile or installed browser acceptance.
