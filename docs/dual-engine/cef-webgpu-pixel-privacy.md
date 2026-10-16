# Selective WebGPU pixel privacy

This native follow-up to [worker/GPU privacy](cef-worker-gpu-privacy.md) targets
Metal RGBA8Unorm/BGRA8Unorm texture-to-buffer readback, including their sRGB storage
variants. Only opaque pixels change. Other formats, nonopaque pixels, arbitrary
compute buffers and shader-based extraction are outside this increment.

## Execution and ownership

Blink derives the existing container/site canvas key before device creation and
passes it through a dedicated internal Dawn device descriptor. It never uses a
page-visible label, wrapper or script. Dawn copies that key into native device
state. This follows the existing trusted renderer ownership model; it is not a
new defense against a compromised renderer. Worker ownership follows the browser's
effective storage partition, as described in the worker/GPU report.

The Metal device compiles a private HMAC-SHA256 pipeline before accepting device
work. Failure rejects device creation. After a validated texture-to-buffer copy,
Dawn dispatches it over only the destination's pixel footprint, with the original
source coordinates, byte offset, row pitch and image pitch. BGRA is canonicalized
to RGB for the same HMAC input as Canvas2D. Alpha, padding and source textures stay
unchanged. Noise is deterministic and idempotent for matching pixels/coordinates.
The optional BGRA compute-copy emulation cannot skip the native protection path.

No map-time provenance tags are kept. Rejected submissions never execute this
transform. Subsequent buffer copies carry their actual bytes; subsequent compute,
clear and queue writes replace them normally. Reading the same buffer again does
not apply additional noise. A readback buffer reused as input naturally contains
its protected bytes. Applications expecting exact RGBA8 image data can disable
canvas privacy before context creation; arbitrary integer compute output remains
exact by default.

The separate strict `blockWebGPUReadback` policy still rejects all READ maps,
including compute results. Selective pixel noise uses the existing `privacy.canvas`
policy. `webgpuPixelReadbackVersion:1` reports the native Metal implementation;
`privacyPatched` remains false. General GPU limits/features and full Chromium
privacy parity remain open. Other WebGPU backends are not covered by this patch.

## Build and replay

Apply the pinned upstream/macOS repairs, then canvas, worker/GPU and this extension:

```sh
python3 engines/chromium/apply_canvas_patch.py --source-root /path/to/chromium/src
python3 engines/chromium/apply_worker_gpu_patch.py --source-root /path/to/chromium/src
python3 engines/chromium/apply_webgpu_pixel_patch.py --source-root /path/to/chromium/src
python3 engines/chromium/apply_webgpu_pixel_patch.py --source-root /path/to/chromium/src --check
```

The final verifier checks inherited prerequisites after accounting for files
superseded by later stages. Rebuild the framework, package into a fresh SDK and
relink the companion. Keep all earlier SDKs/apps for independent controls.

The native Metal shader has been exercised independently against a CPU HMAC-SHA256
reference, with byte-exact output and unchanged padding. The source-linked browser results are recorded below.

## Verification — 2026-10-15

All 68 Python engine tests (15 selective-pixel tests), one C++ test, native
isolation/sandbox and pre-certificate transport probes pass. RGBA/BGRA and sRGB
copies match Canvas2D's native pixel output. Dedicated/shared/service workers,
restart/private ownership, crops, layered layouts, subrange maps and GPU buffer
copies pass. Integer texture/compute results and nonopaque pixels stay exact;
partial overwrites replace only their intended bytes. A valid command buffer with
a subsequently destroyed source is rejected without touching old destination data.
The compositor screenshot matches the disabled control byte-for-byte after readback.
Eight old/new, protection on/off and copy/no-copy controls confirm a baseline
compositor green-channel rounding difference; the fixture uses an exact control
comparison rather than a protected-pixel tolerance.

The source, SDK and embedded framework hashes match. Earlier SDKs/apps remain
unchanged. Clean replay/idempotence and changed-input rejection pass. Linking the
new client to the older worker/GPU SDK reports pixel capability zero. The original
all-READ-map block and combined launcher flags still work.

See [dated result and performance](cef-webgpu-pixel-privacy-20261015.json),
[engine tests](cef-webgpu-pixel-units-20261015.txt),
[C++ test](cef-webgpu-pixel-ctest-20261015.txt),
[actual runtime and timing](cef-webgpu-pixel-runtime-20261015.json),
[isolation](cef-webgpu-pixel-isolation-20261015.json),
[transport](cef-webgpu-pixel-transport-20261015.json),
[source replay/hashes](cef-webgpu-pixel-source-20261015.json), and
[paired presentation controls](cef-webgpu-pixel-presentation-controls-20261015.json).
Authenticated H2/H3 isolation and full browser privacy parity remain unverified.

A local 512×512 copy-and-map sample measured medians of 6.3 ms protected and 0.8 ms disabled (three samples, excluding device/pipeline creation). This is not a release benchmark.
