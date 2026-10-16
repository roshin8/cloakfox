# First native Chromium canvas increment

The source-built Chromium 154 companion now has a **partial** native Canvas2D
readback/export transform. It is separate from the preserved binary SDK companion
and Gecko application. [Measured results](cef-canvas-privacy-20261015.json).

A browser-managed 256-bit secret belongs to each profile/container. Persistent
keys survive restart; private keys are recreated after the last private window
closes. HMAC-SHA256 derives a schemeful-site key from the document's committed
storage identity or the dedicated worker's inherited top-level origin. Pixel
coordinates and quantized RGB values select deterministic low bits. The operation
is idempotent at matching coordinates and modifies a readback copy, not the
rendering surface. Alpha is unchanged.

Covered: fully opaque sRGB/RGBA8 pixels in Canvas2D `getImageData`, canvas
`toDataURL`/`toBlob`, and OffscreenCanvas `convertToBlob` in documents and dedicated
workers, including nested workers. The controller can explicitly disable it with
`"privacy":{"canvas":false}`. An omitted policy inherits a live context's policy;
a conflicting explicit policy fails before navigation. Open acknowledgments report
`canvasEnabled`. The native capability is `canvasReadbackVersion:1`.

**Still uncovered:** shared/service workers, opaque top-level sites, translucent
pixels, float16/non-sRGB readback, raw WebGL/WebGPU, other privacy groups, persona
regeneration and the shared settings UI. Low-bit perturbation does not establish
resistance to arbitrary canvas fingerprinting. `privacyPatched` remains false.

## Verification

- 32 Python tests pass, including 13 canvas tests, plus one C++ CTest.
- Actual runtime checks cover container/site separation, port-independent site
  identity, repeatability/restart, private lifetime, disable/conflict rejection,
  cross-origin frames, dedicated/nested workers, crops, blank pixels, untouched
  drawing buffers and PNG exports. Exports are decoded in a canvas-disabled
  context, avoiding an idempotence-related false positive.
- The unpatched baseline fails the new container-bound output and policy tests.
  Its detached-frame canvas is cleared on removal; the corrected compatibility
  test preserves that behavior. The first full run had this one incorrect test
  expectation; the corrected full run passes.
- A fresh client linked to the old binary SDK reports capability zero, rejects
  both explicit canvas policies and opens normally with protection reported off.
- [Isolation/sandbox/Metal rendering](cef-canvas-isolation-20261015.json) and
  [pre-certificate TCP/QUIC transport](cef-canvas-transport-20261015.json) pass.
  Authenticated H2/H3 settings and ticket/connection isolation remain unverified.
- Source, SDK and embedded framework SHA256 match:
  `d96aa0093f25d53d2d34b6a54a2ed8d2402cc686912081ec8cb107c7347da35e`.
  Patch replay, idempotence, pinned hashes and rejection before mutation pass.

A small performance check measured a median **52.3 ms** protected versus **0.3 ms**
disabled for 512×512 software readback (three samples, concurrent Firefox build).
This is an illustrative development measurement, not a release benchmark. The
per-pixel HMAC cost needs optimization before treating frequent large readbacks
as suitable for daily use. Drawing itself is not transformed.

## Reproduction

Apply the native patch after upstream CEF patches and the macOS RNG repair:

```sh
python3 engines/chromium/apply_canvas_patch.py --source-root /path/to/chromium/src
# Rebuild cef_framework, package source SDK, then relink the companion.
CLOAKFOX_CHROMIUM_BIN=/path/to/CloakfoxChromium.app/Contents/MacOS/CloakfoxChromium \
  python3 -m unittest discover -s tests/engines -p 'test_*.py' -v
```

The tested application is under
`/Volumes/CloakfoxChromiumBuild/source-build/canvas-companion-build/Release/`.
Use `engines/chromium/launch_prototype.py --binary` to select its executable;
the launcher's default still selects the preserved binary SDK prototype. Runtime
fixtures use `--test-keychain`, so these results do not establish production
Keychain or packaged-release readiness.
