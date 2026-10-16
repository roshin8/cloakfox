# Chromium worker and GPU privacy increment

For the newer selective Metal image-copy transform, see
[WebGPU pixel privacy](cef-webgpu-pixel-privacy.md). This page records the earlier
worker/GPU increment.

This is an extension of the experimental native canvas patch, not full privacy
parity. Runtime evidence is recorded in
[the dated report](cef-worker-gpu-privacy-20261015.json).

## Worker ownership

Shared workers receive the complete browser-selected StorageKey. Service workers
install their persisted registration key before the first script evaluation.
The native canvas helper uses that effective storage partition's schemeful owner
with the existing profile secret. Shared/service-worker canvas output now has the
same owner as documents and dedicated workers in ordinary partitioned contexts.
Persistent identities survive restart; private contexts retain separate secrets.

An intentionally unpartitioned worker pool can serve multiple embedding sites.
Its identity follows its **actual storage pool owner**, rather than whichever
client happened to start it. This does not add per-embedding-site isolation to an
unpartitioned pool or override storage-access grants. Nonce and opaque identities
remain unsupported; they are never collapsed into a common `"null"` seed.

The worker tests also reproduced a baseline private/shutdown crash: Performance
Manager removed a service-worker node from its lookup map before disconnecting
clients, then asserted that it could still identify that node. The patch keeps
ownership in the map through disconnection and moves it to deletion afterward.
Every assertion remains enabled; no shutdown delay or profile merging is added.

## WebGL

Native WebGL1/2 `readPixels` protects RGBA/UNSIGNED_BYTE opaque pixels. WebGL2
PIXEL_PACK_BUFFER destinations receive protected bytes before any later
`getBufferSubData` or GPU buffer copy. General buffer data is not transformed.
Framebuffer/texture storage is unchanged. Default framebuffer coordinates match
canvas exports; custom framebuffer reads retain stable GL image coordinates.

Two CPU-owned scratch reads begin with opposite sentinels. Their invariant bits
identify which pixels the native driver actually wrote, including clipped reads
from arbitrary framebuffer attachments. Only those runs reach the destination.
This preserves existing bytes outside the framebuffer, row padding, pack skips,
typed-array offsets and PBO prefixes/suffixes. Failed calls leave the destination
unchanged and preserve observable GL errors. The PBO path becomes synchronous
under protection; additional reads, copies and HMAC work have a performance cost.

`WEBGL_debug_renderer_info` is unavailable under native canvas privacy, removing
its unmasked vendor/renderer query. Disabling the setting restores native behavior.
Float/integer/packed formats, translucent pixels, transform-feedback/other
computational extraction and general GPU capability fingerprinting remain outside
this readback increment. It is not comprehensive GPU fingerprint resistance.

## WebGPU

Native adapter/device info omits vendor, architecture and optional identifying
diagnostics under canvas privacy. Supported features/limits, subgroup information
and fallback status remain truthful. Actual render and integer compute work are
exercised; default mapped data remains byte-exact.

A separate opt-in `blockWebGPUReadback` policy denies **all READ maps** with
`NotAllowedError`, including compute-result readback. Rendering, WRITE maps and
mapped-at-creation uploads remain available. The native guards cover async and
experimental sync entry points; the default runtime tests exercise async mapping.
This is readback denial, **not WebGPU pixel noise**. Selective canvas-to-buffer
noise needs validated Dawn/GPU-service provenance; encoder-only tags could label
old arbitrary data after a rejected submission and corrupt applications.

## Controls and capabilities

The existing `privacy.canvas` boolean controls canvas/WebGL readback transforms
and GPU identifier reduction. `privacy.blockWebGPUReadback` defaults to false and
is independent. Both must be configured before the first window in the context.
Omitted fields inherit live settings; explicit conflicts and unknown/unsupported
fields fail. The shared Gecko settings UI is still not integrated.

```json
{"version":1,"id":1,"command":"open","container":"1","url":"https://example.com","privacy":{"canvas":true,"blockWebGPUReadback":true}}
```

Ready capabilities are `workerCanvasPrivacyVersion:1`, `webglPrivacyVersion:1`,
`webgpuPrivacyVersion:1`, alongside `canvasReadbackVersion:1`.
`privacyPatched` remains false. Open replies report `canvasEnabled` and
`webgpuReadbackBlocked`. Old SDKs cannot claim these new capabilities.

For disposable development windows, select the new executable explicitly:

```sh
python3 engines/chromium/launch_prototype.py \
  --binary '/Volumes/CloakfoxChromiumBuild/source-build/worker-gpu-companion-build/Release/CloakfoxChromium.app/Contents/MacOS/CloakfoxChromium' \
  --block-webgpu-readback
```

`--disable-canvas-privacy` turns off the canvas/WebGL/metadata group independently.
The launcher default still uses the preserved binary SDK prototype. Test Keychain
mode is for owned fixtures and development, not real accounts.

## Source replay

Apply upstream CEF patches and the macOS RNG repair, then the two privacy stages:

```sh
python3 engines/chromium/apply_canvas_patch.py --source-root /path/to/chromium/src
python3 engines/chromium/apply_worker_gpu_patch.py --source-root /path/to/chromium/src
python3 engines/chromium/apply_worker_gpu_patch.py --source-root /path/to/chromium/src --check
```

The follow-up verifier checks its pinned inputs and untouched parent hooks.
Its final hashes supersede overlapping v1 canvas hashes; running the v1 verifier
alone after this extension is intentionally insufficient. Preserve earlier SDKs
and rebuild/package the source framework before relinking the companion.

## Verification — 2026-10-15

The rebuilt companion passes all 53 Python engine tests (13 canvas, eight worker,
seven WebGL, six WebGPU and 19 existing tests), one C++ test, native sandbox and
storage isolation, and pre-certificate TCP/QUIC probes. Real WGSL rendering and
256-integer compute workloads pass in documents and dedicated/shared/service
workers. Default compute and pixel buffers are exact; strict mode rejects both
READ maps while WRITE mapping and mapped-at-creation still work. The worker
shutdown and clipped-read failures were reproduced before their fixes.

The final source/SDK/embedded framework SHA256 is
`ffc338312fc1a809c33d611b95bbd1069dd11a2bdc3f3e51d6e1054c13d3ce59`.
Clean patch replay/idempotence and rejection of changed inputs pass. Negative
controls against unpatched and v1 canvas SDKs reject unsupported new policies.
The combined launcher flags start and exit cleanly. Prior SDKs/apps are preserved.

A small 512×512 GL2 readback sample measured a protected median of 58.8 ms versus
0.8 ms disabled (three samples, Apple M2 Pro). The synchronous scratch reads and
per-pixel hashing are expensive; this is an illustrative measurement, not a
release benchmark. Broader GPU privacy and shared settings remain pending.

Evidence: [test log](cef-worker-gpu-units-20261015.txt),
[C++ test](cef-worker-gpu-ctest-20261015.txt),
[actual GPU workloads and timing](cef-worker-gpu-runtime-20261015.json),
[isolation and graphics](cef-worker-gpu-isolation-20261015.json),
[transport](cef-worker-gpu-transport-20261015.json),
[source replay and hashes](cef-worker-gpu-source-20261015.json), and
[clipped-read RED control](cef-worker-gpu-clipping-red-20261015.txt).
The graphics isolation diagnostic explicitly disables canvas privacy to identify
the native Metal renderer; separate protected-render tests exercise privacy on.
Authenticated H2/H3 SETTINGS and ticket/connection isolation remain unverified.
