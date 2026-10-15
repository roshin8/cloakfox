# Canonical canvas backing foundation — complete pipeline unfinished

This implements only the first backing/policy project from the approved complete
canvas pipeline design. It is not the complete renderer, does not remove extraction
noise, and does not fix the confirmed known-fill recovery attack. Do not describe
this build as complete rendering privacy or as protection undetectable by websites.

## Implemented

Internal toggle: `cloakfox.experimental.canvas_pipeline` in about:config, default
false. Reload pages/restart workers after changing it. No public complete-mode
checkbox is exposed. The existing text/GPU public toggles remain independent.

A newly created eligible content 2D context captures exact owning-container policy
before options parsing can return, including unused OffscreenCanvas contexts.
Resize/reset retain the captured policy. System and creation-time master-off
contexts retain normal allocation. The selected experiment allocates a basic
Skia target explicitly; it never tries accelerated/shared/platform-selected targets
when canonical allocation fails. Reborrow refuses accelerated/shared/non-Skia
backing. Existing provider clear/copy/path/clip/transform bookkeeping remains.

Authoritative policy defaults/malformed handling, startup repair and global updates
change only policy fields. Existing persona data, manual overrides, network policy
and seeds are preserved. Existing extraction noise, metric protection and strict
GPU integer/float/PBO controls are unchanged. This establishes retained guards,
not a general proof that every identity leak is prevented.

## Unfinished approved objective

Canonical fonts/shaping/raster, image/SVG/media producers, privacy provenance
through copies/bitmaps/workers/video/GPU transfers, canonical GPU rendering and
cross-host differential acceptance are not implemented. A normal Skia target
still uses platform font behavior and cannot erase entropy in imported pixels.
Extraction protection cannot safely be removed on this evidence.

The repository has31 licensed bundled fonts and vendored FreeType/HarfBuzz sources,
but Cocoa does not compile a portable FreeType stack. HarfBuzz outline drawing is
available, while HB_NO_PAINT excludes a ready color-font path. Simply changing
build guards is insufficient because existing FT implementations assume platform
font/WebRender/Cairo APIs. These are integration projects, not missing downloads.

## Review and verification

A fresh reviewer identified a backend check accidentally inserted in the filter
helper. The initial native build failed. The check was moved to BorrowTarget,
and an actual-code regression rejects shared/accelerated/non-Skia providers.
Policy, allocation routing, provider validation and creation freezing compile and
execute in native fixtures. The full Firefox build now passes. No content-facing
backend diagnostic was added; backend choice is verified by actual source-code
execution and build, not inferred solely from output pixels.

Strict replay applies139 ordered patches with no fuzz, offset or native source
drift;353 native hashes match built source. Node258 tests pass. The install
manifest records the packaged signed app, backup, DMG and hashes. Profiles are not
modified. Installed results, including the recovery gap, are in `results.json`.

## Installed test outcome and rollback

The prototype was installed and tested as runtime build `20261015120633`
(application.ini `20261015120736`). The off/on/all-three-toggle matrix passed:
1,767 canvas consistency checks,144 upstream library executions and1,368 library
policy/stability/isolation checks. Node258 and Python58 tests pass. Installed
policy12, settings13, GPU42 and graphics/worker readback probes pass.

The first installed glyph probe passed38/40 assertions: the initial HTML sample
had a different hash from later matching off/wrong-type samples. An instrumented
rerun passed40/40 but did not reproduce or explain the discrepancy. This is an
unresolved rendering observation; the rerun is not a fix and the original failure
is retained in `results.json` and raw logs.

The full privacy acceptance gate also FAILS: known-fill calibration still recovers
the native path/gradient raster exactly in all six recorded protected cases.
This was expected for an unchanged extraction guard but prevents calling the
prototype a complete privacy replacement. Existing CreepJS pixel/GPU warnings
remain, along with prior geometry and Chrome-UA/Gecko warnings.

Because full acceptance did not pass, the previous installed app was restored.
Current `/Applications/Cloakfox.app` XUL hash is
`356322cd14637d05ae3a6bc3b4c4e32a208ff4522d9f6fe46637ea28ac100484`.
The tested prototype is retained under the app-backups directory recorded in
`install.json`; its XUL hash is
`02f2f03c0ffea78c98c4516ac9ca2ff74337cdb8f8c5d9c4b2e94891d9c16b03`.
The internal toggle belongs to that prototype/source build, not the restored app.
No personal profiles were changed. The approved full implementation remains open.
