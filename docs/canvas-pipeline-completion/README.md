# Canonical canvas pipeline — Mac acceptance

Completed and tested on the installed `/Applications/Cloakfox.app` on macOS
arm64. Runtime BuildID **20261015154131**, Firefox **158.0-beta.26**, XUL SHA256
`275455a276f84bc7f4f74802b18ab8df2ca206d0fb1bad91796be614d8555b42`.
The user limited this run to Mac. Windows/Linux and cross-host equality are
**not verified**.

## Setting and behavior

In Cloakfox Settings → Hardening, enable **Use canonical software rendering**.
It is a separate default-off toggle (`cloakfox.experimental.canvas_pipeline`).
Restart an already-running old browser after installation; reload pages and
recreate workers after changing the setting. Personal profiles/settings were not
changed during installation or testing; a signed app backup is in `install.json`.

The mode uses bundled FreeType/HarfBuzz fonts, fixed fallback/color emoji and
author-font shaping, explicit Skia 2D backing, pinned ANGLE/Vulkan/SwiftShader GPU
rendering, common software decoding and scalar color conversion. The compatible
GPU profile and precise GPU readback restriction are enforced while it is on;
the separate saved choices are retained when it is off. Missing verified GPU
resources refuse context/adapter creation rather than falling back to host GPU.

Source ownership follows the actual container and top-level site through
snapshots, ImageBitmap/Offscreen transfers, GPU uploads and media consumers. It
uses opaque HMAC-derived ownership records, not URLs or embedded secrets. A label
alone cannot certify pixels: actual producer execution and every incoming source
are checked. Qualified canonical pixels replace legacy extraction noise.
Unverified 2D inputs retain fallback protection; unverified/foreign GPU ingress
and unverified exact VideoFrame copies are refused. Unknown inputs cannot borrow
later producer markers. Missing seeds fail closed where fallback noise cannot
protect output. Default-off/master-off behavior and security/taint checks remain.

Per-site/container font geometry scaling remains deterministic and is applied to
both shaping and rendering. Pixel quantization can make two owners' individual
images equal; cross-owner pixel inequality is not itself a universal criterion.
Same-owner stability, owner metadata separation, metric isolation and native
output recovery are tested independently.

## Installed verification

| Checks | Result | Evidence |
| --- | --- | --- |
| 12 core probes: 2D, fonts, SVG/images, GL/WebGPU, video/capture, ownership, attacks, missing seeds and transfers | 944 passed | `installed-verified/results.json` and per-probe `result.json` |
| Pinned, unmodified CreepJS and FingerprintJS; 8 identities/site/control cases, 3 reloads, both libraries | 448 passed, 48 executions | `installed-verified-libraries/results.json`, `upstreams.json` |
| PNG/JPEG/WebP via toDataURL/toBlob/convertToBlob, window/Offscreen/worker | 31 passed | `installed-verified-encoders/result.json` |
| Actual installed FFVPX libraries, 8/10-bit H264/HEVC/VP9/AV1 fixtures, C versus available SIMD | 28 passed | `installed-verified-codecs.json` |
| Cold first-draw text, default asynchronous fallback, no warmup/retry | 4 fresh launches passed | `installed-verified-first-glyph/report.json` |
| Existing renderer-off consistency | 589 passed | `installed-verified-legacy/result.json` |
| Missing/tampered canonical libraries, signed disposable app copies with unchanged integrity manifests | 54 passed | `verified-gpu-missing/result.json`, `verified-gpu-tampered/result.json` |
| Editing, 30 animation frames and 4096×4096 encode/decode/copy, renderer off/on | Both passed | `installed-verified-load/result.json` |
| Node / Python unit regressions | 261 / 114 passed | `node-complete-final.log`, `unit-complete-final.log` |
| Strict ordered patch replay | 144 patches, 408 pristine targets; zero offsets/fuzz/source drift | `native-final-replay.json` |

Fourteen unrelated runtime-dependent Python tests were skipped in the unit run;
the explicit installed probes above ran separately. GPU acceptance runs in a
normal browser window: Firefox deliberately disables its GPU process/WebGPU in
headless mode. The diagnostic headless failure was not fixed with a production
blocklist bypass. Fingerprint-library runs retain their normal WebGPU privacy
block; the dedicated GPU corpus explicitly allows the API in its disposable
profile to exercise the real backend.

The known-fill adversarial test could not recover native glyph pixels: it found
10,925 differing channels out of 98,304 in each HTML, Offscreen and worker case.
That is evidence against the tested recovery method, not every possible attack.
Crops, alpha, image exports, text metrics and consumer transfers have separate
semantic checks. Canonical capture tests require no camera or screen access.

Observed load timings were approximately 0.54s/0.50s for 30 frames and
0.68s/0.10s for the large-image operation, renderer off/on. Peak summed process-tree
RSS was about 2.22/2.21GiB. Shared pages may be counted more than once and other
machine activity was present; these are recorded smoke measurements, not a
performance comparison or guarantee. A uniform canonical PNG compresses much
better than the legacy noisy image.

## Failures found and fixed

- Canonical export skipped the straight-RGBA conversion previously performed
  inside the legacy-noise branch. Translucent PNGs therefore differed from typed
  readback. Shared conversion now runs for both paths; the installed regression
  and all encoder routes pass.
- Canonical outline rendering reached WebRender's fake text collector, whose
  path API deliberately crashes. It reproduced in CreepJS and plain text-field
  typing. The collector now signals unsupported and Gecko repaints through Skia
  with the **same canonical font**, without selecting host fonts. Actual C++
  dispatch regression failed before the fix and passed afterward; independent
  review, typing/emoji/style repaint and installed CreepJS passed.
- Gecko packaging stripped a pinned GLES library and damaged its Mach-O load
  commands. The packager now preserves the three pinned libraries. Packaged bytes
  are verified, inner code signed, signed-library manifest hashes refreshed and
  outer resources sealed; strict signature verification passed.

Build evidence: `full-build-release.log`, `build-export-normalization.log`,
`build-font-collector-fix.log`, `package-font-collector-final.log`,
`package-gpu-final-verification.log`, `sign-verified.log`, `install-verified.log`.
Independent review confirmed the final normalization and collector fixes retain
extraction guards and canonical font production. Original failing reports are
retained as diagnostics, not counted as successful acceptance.

## Privacy and compatibility limits

CreepJS reported canvas `lied=false` for the protected test cases. It still flags
the generic GPU/capabilities and existing DOM rectangle behavior. Those warnings
were not suppressed. Full observations remain in the raw library reports and
`verified-detector-observations.json`. Recognizing privacy software is different
from recovering the real host's canvas/GPU identity; this run establishes neither
universal undetectability nor protection against every fingerprinting method.

Software rendering can increase CPU/battery use and changes font appearance.
Unsupported inputs can fail under the explicit refusal policy. Media/location
consent, CORS/taint, network isolation and the default renderer were not relaxed
to obtain passing results. Cross-platform rendering and hardware independence
beyond this Mac corpus still require additional machines.

`verified-evidence.json` records the installed app identity and SHA256 of the
final reports. Native integration is `patches/canvas-complete-renderer.patch`;
`source-patches/` retains independent development/review references. The plan,
spec and `.superpowers/sdd/2026-10-15-canvas-completion/progress.md` record the
implementation and the user-approved Mac-only acceptance boundary.
