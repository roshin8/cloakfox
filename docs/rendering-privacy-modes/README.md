# Optional canvas rendering and compatible GPU modes

Subsequent adversarial audit: known-fill calibration can reverse the existing
coordinate noise for a path/gradient image in HTML, Offscreen and worker canvases.
The consistency results below do not establish resistance to that recovery.
See `../canvas-pipeline-audit/installed-baseline.json` and the complete pipeline
specification. The canonical backing foundation retains the same known gap.

Settings: `about:cloakfox` → Optional hardening.

- **Additional canvas rendering protection** adds deterministic, site/container-bound
  subpixel variation before text rasterization. HTML, Offscreen, worker-created and
  transferred contexts capture their policy and seed at creation. It retains the
  existing extraction and metric protections, including non-text paths. This is
  experimental additive protection, not a full render-only replacement.
- **Use compatible GPU profile** selects one generic masked device cohort. It
  restricts actual allocation, shader resources, point raster size and line width;
  reporting follows those restrictions. Shared WebGL1/2 capabilities agree. Native
  extension support still applies. Unsupported backends refuse protected context
  creation rather than manufacture support or expose their model.

Both settings default off, persist independently and preserve saved personas,
manual overrides and identity seeds. Reload pages and restart workers after
changing either setting. Existing contexts retain their captured policy. The
headline describes the generic GPU when the GPU setting is on; saved persona
GPU fields remain available when it is off.

## Privacy boundary

Neither setting removes canvas extraction protection or relaxes strict GPU
integer/float/PBO readback controls. Permissions and network policy are unchanged.
The GPU implementation also fixes legacy worker GPU lookups that could previously
read the default container's tables, strings or extension configuration. Invalid
precision enums retain native validation; malformed tuples respect existing
blocking policy. Valid legacy masks are preserved, rather than newly clamped to
backend-dependent precision ceilings.

The shared GPU baseline requires 16 attributes, 32 combined texture units,
16 vertex/fragment units each, 256/224 vertex/fragment uniform vectors and 15
varying vectors in both versions. Texture/cube/renderbuffer maximum is 2048;
viewport maximum is 4096; point range is [1,63], line range [1,1]. WebGL2-only
limits and minimum requirements retain their version-specific validation.

## Limits

The canvas mode covers glyph drawing; it does not replace all image, filter,
composite, transfer or WebGL rendering paths. Existing pixel perturbation is
still observable by scripts that compare authored colors with readback.
The generic GPU profile is not complete driver emulation. Native extension
availability, unsupported operations, arithmetic and timing can still reveal
backend differences. Smaller capabilities may affect 3D applications or prevent
context creation on weaker devices. Added glyph variation may slightly alter text.
No claim of undetectability or universal privacy equivalence is made.

Final installed verification and upstream warnings are recorded in `results.json`.
Raw browser measurements use disposable profiles under
`tests/fingerprint/reports/rendering-privacy-modes/`; test fixtures are pinned,
unmodified upstream CreepJS and FingerprintJS. No assessment or personal media
session is used. The install manifest records the signed app, backup and hashes.

## Final installed verification

Installed Firefox158-based Cloakfox runtime build `20261015111523`;
application.ini build `20261015111550`. Signature verification passes; the app
contains no external symlinks. `install.json` identifies the backup and DMG.

| Installed configuration | Canvas consistency checks | Library executions | Library checks |
| --- | ---: | ---: | ---: |
| Both off | 589 | 48 | 456 |
| Canvas only | 589 | 48 | 456 |
| GPU only | 589 | 48 | 456 |
| Both on | 589 | 48 | 456 |

All matrix checks pass: 2,356 canvas checks and 192 library executions with
1,824 stability/isolation/policy checks. The installed app additionally passes
40 rendering-mode checks, 42 GPU mode checks, 13 UI/persistence checks,
30 legacy GPU consistency checks and the existing graphics privacy,
worker-canvas and WebGL-table probes. All 256 Node tests and 55 Python tests pass.

Strict replay applies all 138 ordered patches from pristine source without
fuzz, offsets or native source drift; all 353 target hashes match the built
source. Independent reviews are closed, with resolved findings in `review.md`.

Upstream CreepJS warnings remain in every protected configuration: pixel data
modified, suspicious pixel data, suspicious GPU and suspicious capabilities.
Protected geometry retains its earlier rotate/ghost rectangle warnings. Chrome-UA
cases retain the deferred SpiderMonkey/V8 mismatch. The native controls do not
report these warnings. The intermediate shared WebGL1/2 parameter mismatch is
absent from the final installed runs. No `measureText` metric-noise warning
returned. Warning details for all cases and modes are retained in `results.json`;
passing the regression checks does not mean detectors cannot recognize protection.
